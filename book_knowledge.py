#!/usr/bin/env python
"""
Book Knowledge Module for Stardock Podium.

Implements the 3-tier book knowledge system:

  Tier 1 — Series Bible (always injected, ~3K tokens)
            Extracted ONCE from all books on ingest.
            Structured lore: species, tech, dialogue rules, tone.
            Saved to data/series/series_bible.json

  Tier 2 — RAG Context (per-scene, ~3-4K tokens)
            6 full Mem0 chunks retrieved per query.
            No character truncation — full chunk text.
            Better query construction per scene.

  Tier 3 — Raw Book Text (never in prompts)
            Stays on disk / in Mem0 as source of truth.
            Only read during the one-time extraction pass.

Drop this file into the repo root.
Then apply the patches in story_structure_patch.py and
reference_memory_sync_patch.py.
"""

import os
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Paths — resolved via config.paths so cloud deployments can
# redirect these onto a persistent volume via STARDOCK_DATA_DIR.
# ─────────────────────────────────────────────
from config.paths import SERIES_DIR

SERIES_BIBLE_PATH = SERIES_DIR / "series_bible.json"
STYLE_PROFILE_PATH = SERIES_DIR / "style_profile.json"
EXTRACTION_STAMP_PATH = SERIES_DIR / "extraction_stamp.json"


# ─────────────────────────────────────────────
# Series Bible Extractor
# ─────────────────────────────────────────────

BIBLE_EXTRACTION_PROMPT = """
You are a lore archivist for a Star Trek podcast series.

Below are excerpts from Star Trek reference books and novels.
Extract a comprehensive series bible as a JSON object.
Return ONLY valid JSON — no preamble, no markdown fences.

JSON schema:
{
  "universe": "string — e.g. Star Trek",
  "era": "string — which era/timeline these books represent",
  "technology": ["list of canonical technology names and brief descriptions"],
  "species": [
    {
      "name": "string",
      "traits": "string — key cultural/biological traits",
      "speech_patterns": "string — how they speak (contractions, cadence, formality)"
    }
  ],
  "locations": ["list of canonical locations with one-line descriptions"],
  "starships": ["list of ship classes/names mentioned"],
  "command_hierarchy": ["ordered list of ranks/roles"],
  "recurring_themes": ["thematic elements that recur in this universe"],
  "dialogue_rules": [
    "concrete rule about how characters speak — be specific"
  ],
  "tone": "string — overall narrative tone and feel",
  "moral_framework": "string — the ethical worldview of this universe",
  "forbidden": ["things that should NOT appear — anachronisms, wrong tech, etc."]
}

Reference material:
{reference_text}
"""

STYLE_EXTRACTION_PROMPT = """
You are a literary analyst studying the writing style of Star Trek fiction.

Below are excerpts from Star Trek reference books and novels.
Extract a concrete style profile as a JSON object.
Return ONLY valid JSON — no preamble, no markdown fences.

JSON schema:
{
  "sentence_rhythm": "string — short/punchy or long/flowing, typical structure",
  "dialogue_style": "string — how subtext works, what goes unsaid",
  "scene_openings": "string — how scenes typically begin",
  "pacing": "string — how tension and release are managed",
  "vocabulary_register": "string — technical, literary, accessible, formal etc.",
  "description_density": "string — sparse or rich, what gets described",
  "character_interiority": "string — how much inner thought appears",
  "conflict_style": "string — how conflict is expressed and resolved",
  "recurring_motifs": ["list of recurring images, metaphors, symbols"],
  "what_to_avoid": ["list of writing habits that would break the style"]
}

Reference material:
{reference_text}
"""


class SeriesBibleExtractor:
    """
    Runs once after book ingest to produce series_bible.json and style_profile.json.
    These are the Tier 1 artifacts — injected into every prompt.
    """

    def __init__(self):
        self._init_llm()

    def _init_llm(self):
        """Load whichever LLM client is available."""
        from openai import OpenAI

        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        if openrouter_key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key,
            )
            self.model = "anthropic/claude-opus-4.5"
            logger.info("BibleExtractor using OpenRouter / Claude Opus")
        elif openai_key:
            self.client = OpenAI(api_key=openai_key)
            self.model = "gpt-4o"
            logger.info("BibleExtractor using OpenAI GPT-4o")
        else:
            raise EnvironmentError("No LLM API key found (OPENROUTER_API_KEY or OPENAI_API_KEY)")

    # ── Public entry point ──────────────────────────────────────────────────

    def extract_from_all_books(self, force: bool = False) -> Dict[str, Any]:
        """
        Pull all synced book sections from Mem0, run extraction, save results.

        Args:
            force: Re-extract even if outputs already exist.

        Returns:
            {"series_bible": {...}, "style_profile": {...}}
        """
        if not force and self._already_extracted():
            logger.info("Series bible already extracted. Use force=True to re-run.")
            return self._load_existing()

        logger.info("Starting series bible extraction from all books...")
        reference_text = self._gather_representative_chunks()

        if not reference_text:
            logger.error("No reference text available — sync books first.")
            return {}

        logger.info(f"Gathered {len(reference_text)} chars of reference text for extraction")

        series_bible = self._extract_json(
            BIBLE_EXTRACTION_PROMPT.replace(
                '{reference_text}', reference_text),
            label="series_bible",
        )
        style_profile = self._extract_json(
            STYLE_EXTRACTION_PROMPT.replace(
                '{reference_text}', reference_text),
            label="style_profile",
        )

        # Save both
        SERIES_BIBLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._save_json(SERIES_BIBLE_PATH, series_bible)
        self._save_json(STYLE_PROFILE_PATH, style_profile)

        # Write extraction stamp so we don't re-run unnecessarily
        self._save_json(EXTRACTION_STAMP_PATH, {
            "extracted_at": time.time(),
            "bible_path": str(SERIES_BIBLE_PATH),
            "style_path": str(STYLE_PROFILE_PATH),
        })

        logger.info("Series bible extraction complete.")
        return {"series_bible": series_bible, "style_profile": style_profile}

    # ── Internal helpers ────────────────────────────────────────────────────

    def _gather_representative_chunks(self, max_chars: int = 80_000) -> str:
        """
        Pull chunks from Mem0 across multiple broad queries to get a
        representative sample of all synced books.
        We use broad queries because we want coverage, not specificity.
        """
        from reference_memory_sync import search_references

        queries = [
            "Star Trek starship command crew",
            "Star Trek alien species culture",
            "Star Trek technology warp drive",
            "Star Trek moral dilemma ethics",
            "Star Trek dialogue conversation",
            "Star Trek planet exploration mission",
            "Star Trek conflict battle strategy",
            "Star Trek history timeline federation",
        ]

        seen_ids: set = set()
        chunks: List[str] = []
        total_chars = 0

        for query in queries:
            if total_chars >= max_chars:
                break
            results = search_references(query, limit=8)
            for r in results:
                mem_id = r.get("id") or r.get("memory_id") or r.get("memory", "")[:40]
                if mem_id in seen_ids:
                    continue
                seen_ids.add(mem_id)
                text = r.get("memory", "")
                if text:
                    chunks.append(text)
                    total_chars += len(text)
                    if total_chars >= max_chars:
                        break

        logger.info(f"Gathered {len(chunks)} unique chunks ({total_chars} chars) for extraction")
        return "\n\n---\n\n".join(chunks)

    def _extract_json(self, prompt: str, label: str) -> Dict[str, Any]:
        """Send prompt to LLM, parse JSON response."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise analyst. Return only valid JSON with no extra text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=4000,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error for {label}: {e}")
            return {}
        except Exception as e:
            logger.error(f"LLM error during {label} extraction: {e}")
            return {}

    def _already_extracted(self) -> bool:
        return (
            SERIES_BIBLE_PATH.exists()
            and STYLE_PROFILE_PATH.exists()
            and EXTRACTION_STAMP_PATH.exists()
        )

    def _load_existing(self) -> Dict[str, Any]:
        return {
            "series_bible": self._load_json(SERIES_BIBLE_PATH),
            "style_profile": self._load_json(STYLE_PROFILE_PATH),
        }

    @staticmethod
    def _save_json(path: Path, data: Dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved: {path}")

    @staticmethod
    def _load_json(path: Path) -> Dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return {}


# ─────────────────────────────────────────────
# Runtime Knowledge Context (used in story_structure.py)
# ─────────────────────────────────────────────

class KnowledgeContext:
    """
    Loaded once at StoryStructure init.
    Provides:
      - build_system_prompt()  — Tier 1 injection for every LLM call
      - get_rag_context()      — Tier 2 per-scene RAG retrieval
    """

    def __init__(self):
        self.series_bible: Dict = self._load_json(SERIES_BIBLE_PATH)
        self.style_profile: Dict = self._load_json(STYLE_PROFILE_PATH)

        if self.series_bible:
            logger.info("KnowledgeContext: series bible loaded (ok)")
        else:
            logger.warning(
                "KnowledgeContext: series_bible.json not found. "
                "Run `python main.py ingest` to generate it."
            )

        if self.style_profile:
            logger.info("KnowledgeContext: style profile loaded (ok)")
        else:
            logger.warning("KnowledgeContext: style_profile.json not found.")

    # ── Tier 1 ─────────────────────────────────────────────────────────────

    def build_system_prompt(self, base_prompt: str) -> str:
        """
        Append series bible and style profile to any system prompt.
        Called once per LLM request — cheap, always correct.
        """
        sections = [base_prompt]

        if self.series_bible:
            sections.append(self._format_bible())

        if self.style_profile:
            sections.append(self._format_style())

        return "\n\n".join(sections)

    def _format_bible(self) -> str:
        b = self.series_bible
        lines = ["═══ SERIES BIBLE (follow strictly) ═══"]

        if b.get("tone"):
            lines.append(f"TONE: {b['tone']}")
        if b.get("moral_framework"):
            lines.append(f"MORAL FRAMEWORK: {b['moral_framework']}")
        if b.get("dialogue_rules"):
            lines.append("DIALOGUE RULES:")
            for rule in b["dialogue_rules"]:
                lines.append(f"  • {rule}")
        if b.get("species"):
            lines.append("SPECIES SPEECH PATTERNS:")
            for sp in b["species"]:
                lines.append(f"  • {sp['name']}: {sp.get('speech_patterns', '')}")
        if b.get("forbidden"):
            lines.append("DO NOT include:")
            for item in b["forbidden"]:
                lines.append(f"  ✗ {item}")

        return "\n".join(lines)

    def _format_style(self) -> str:
        s = self.style_profile
        lines = ["═══ WRITING STYLE GUIDE (match this voice) ═══"]

        for key, label in [
            ("sentence_rhythm", "Sentence rhythm"),
            ("dialogue_style", "Dialogue style"),
            ("pacing", "Pacing"),
            ("vocabulary_register", "Vocabulary"),
            ("description_density", "Description density"),
        ]:
            if s.get(key):
                lines.append(f"{label}: {s[key]}")

        if s.get("what_to_avoid"):
            lines.append("Avoid:")
            for item in s["what_to_avoid"]:
                lines.append(f"  ✗ {item}")

        return "\n".join(lines)

    # ── Tier 2 ─────────────────────────────────────────────────────────────

    def get_rag_context(
        self,
        scene_beat: str = "",
        scene_setting: str = "",
        episode_theme: str = "",
        limit: int = 6,
    ) -> str:
        """
        Retrieve contextually relevant book chunks for a specific scene.
        Returns full chunk text (no character truncation).
        Uses a richer query than the old 'Star Trek {theme}' approach.
        """
        from reference_memory_sync import search_references

        # Build a specific query from scene context
        query_parts = [p for p in [scene_beat, scene_setting, episode_theme] if p]
        query = " ".join(query_parts) if query_parts else "Star Trek scene"

        try:
            results = search_references(query, limit=limit)
            if not results:
                return ""

            chunks = []
            for r in results:
                text = r.get("memory", "").strip()
                source = r.get("metadata", {}).get("book_title", "")
                if text:
                    header = f"[Source: {source}]" if source else ""
                    chunks.append(f"{header}\n{text}".strip())

            return "\n\n---\n\n".join(chunks)

        except Exception as e:
            logger.warning(f"RAG retrieval failed (non-critical): {e}")
            return ""

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _load_json(path: Path) -> Dict:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            return {}

    def is_ready(self) -> bool:
        """True if both bible and style profile are loaded."""
        return bool(self.series_bible) and bool(self.style_profile)


# ─────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────

_knowledge_context: Optional[KnowledgeContext] = None


def get_knowledge_context() -> KnowledgeContext:
    """Get the singleton KnowledgeContext instance."""
    global _knowledge_context
    if _knowledge_context is None:
        _knowledge_context = KnowledgeContext()
    return _knowledge_context


def reload_knowledge_context() -> KnowledgeContext:
    """Force reload — call this after running extraction."""
    global _knowledge_context
    _knowledge_context = KnowledgeContext()
    return _knowledge_context
