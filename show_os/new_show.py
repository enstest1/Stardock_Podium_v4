#!/usr/bin/env python
"""
New Show Creation Module for Stardock Podium.

Handles Level 1 prompt: the concept that defines an entire podcast series.

Workflow:
    1. User provides concept prompt + podcast name
    2. Books already ingested are used for style + lore
    3. LLM analyzes concept and proposes cast size + composition
    4. User confirms or adjusts
    5. series_bible.json is written with:
         - concept (Level 1 prompt)
         - target_cast_size
         - cast_concept (composition reasoning)
         - main_cast (permanent characters)
         - Plus all existing bible fields from book extraction

Usage:
    python main.py new-show \\
        --name "Prophets and Gamma" \\
        --concept "A Star Trek podcast set in the Bajoran sector..."
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict

from openai import OpenAI

logger = logging.getLogger(__name__)

from config.paths import SHOWS_DIR  # noqa: E402  (keeps legacy name)


CAST_PROPOSAL_PROMPT = """
You are a showrunner designing a new science fiction podcast series.
Analyze the concept below and propose a main cast that serves it.

CONCEPT:
{concept}

REFERENCE STYLE (from source books):
{style_context}

Respond with ONLY valid JSON matching this schema:
{{
  "analysis": "2-3 sentence reasoning about what this show needs",
  "target_cast_size": <integer between 2 and 12>,
  "cast_concept": "paragraph explaining the cast composition and why",
  "suggested_main_cast": [
    {{
      "name": "string",
      "species": "string",
      "role": "string",
      "personality": "string \u2014 1-2 sentences",
      "backstory": "string \u2014 2-3 sentences",
      "voice_description": "string \u2014 specific vocal qualities"
    }}
  ]
}}

CRITICAL RULES:
- Cast size must match the show's needs, not a formula.
  A two-hander drama = 2. An ensemble = 8-10. A bottle show = 3-4.
- Each character must be necessary.
- Voice descriptions must be specific enough for audition.
- No preamble, no markdown fences. Only valid JSON.
"""


class ShowCreator:
    """Creates a new podcast show from a Level 1 concept prompt."""

    def __init__(self):
        self._init_llm()
        SHOWS_DIR.mkdir(parents=True, exist_ok=True)

    def _init_llm(self):
        openrouter_key = os.environ.get('OPENROUTER_API_KEY')
        openai_key = os.environ.get('OPENAI_API_KEY')

        if openrouter_key:
            self.client = OpenAI(
                base_url='https://openrouter.ai/api/v1',
                api_key=openrouter_key,
            )
            self.model = 'anthropic/claude-opus-4.5'
        elif openai_key:
            self.client = OpenAI(api_key=openai_key)
            self.model = 'gpt-4o'
        else:
            raise EnvironmentError(
                'No LLM API key \u2014 set OPENROUTER_API_KEY '
                'or OPENAI_API_KEY'
            )

    def create_show(
        self,
        name: str,
        concept: str,
        auto_accept: bool = False,
    ) -> Dict[str, Any]:
        """Create a new show from a concept prompt.

        Args:
            name:        Human-readable podcast name.
            concept:     Level 1 prompt \u2014 the show's core premise.
            auto_accept: Skip interactive confirmation.

        Returns:
            Dict with show_id, paths, and the generated bible.
        """
        from book_knowledge import (
            SERIES_BIBLE_PATH,
            get_knowledge_context,
            reload_knowledge_context,
        )

        knowledge = get_knowledge_context()
        if not knowledge.is_ready():
            raise RuntimeError(
                'Books not ingested yet. Run '
                '`python main.py ingest` first so the show can '
                'use book lore and style.'
            )

        logger.info('Creating new show: %s', name)
        logger.info('Concept: %s...', concept[:200])

        style_ctx = json.dumps(
            knowledge.style_profile, indent=2)[:2000]

        proposal = self._get_cast_proposal(concept, style_ctx)
        if not proposal:
            raise RuntimeError(
                'LLM failed to produce a valid cast proposal')

        self._display_proposal(proposal)

        if not auto_accept:
            proposal = self._interactive_adjust(
                proposal, concept, style_ctx)

        show_id = self._slugify(name)
        bible = self._merge_bible(
            existing_bible=knowledge.series_bible,
            show_id=show_id,
            name=name,
            concept=concept,
            proposal=proposal,
        )

        show_dir = SHOWS_DIR / show_id
        show_dir.mkdir(parents=True, exist_ok=True)
        show_bible_path = show_dir / 'series_bible.json'
        with open(show_bible_path, 'w', encoding='utf-8') as f:
            json.dump(bible, f, indent=2, ensure_ascii=False)

        with open(SERIES_BIBLE_PATH, 'w', encoding='utf-8') as f:
            json.dump(bible, f, indent=2, ensure_ascii=False)

        show_state_path = show_dir / 'show_state.json'
        with open(show_state_path, 'w', encoding='utf-8') as f:
            json.dump({
                'show_id': show_id,
                'name': name,
                'current_season': None,
                'episodes_produced': 0,
                'active_threads': [],
                'character_states': {},
                'world_facts': [],
                'unresolved_hooks': [],
                'past_guests': [],
                'created_at': time.time(),
            }, f, indent=2)

        reload_knowledge_context()

        logger.info("Show '%s' created at %s", name, show_dir)
        return {
            'show_id': show_id,
            'name': name,
            'bible_path': str(show_bible_path),
            'show_state_path': str(show_state_path),
            'bible': bible,
        }

    # ── LLM helpers ──────────────────────────────

    def _get_cast_proposal(
        self, concept: str, style_context: str,
    ) -> Dict[str, Any]:
        """Ask LLM to propose cast size + composition."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': (
                            'You are a precise showrunner. '
                            'Return only valid JSON.'
                        ),
                    },
                    {
                        'role': 'user',
                        'content': CAST_PROPOSAL_PROMPT.format(
                            concept=concept,
                            style_context=style_context,
                        ),
                    },
                ],
                temperature=0.4,
                max_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
            return json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error('Could not parse cast proposal JSON: %s', e)
            return {}
        except Exception as e:
            logger.error('Cast proposal LLM call failed: %s', e)
            return {}

    # ── Display / interactive ────────────────────

    def _display_proposal(self, proposal: Dict[str, Any]) -> None:
        """Print the proposal to console."""
        print('\n' + '=' * 64)
        print('  CAST PROPOSAL')
        print('=' * 64)
        print(
            f"\n  Analysis:\n   {proposal.get('analysis', 'N/A')}")
        print(
            f"\n  Proposed cast size: "
            f"{proposal.get('target_cast_size', '?')}")
        print(
            f"\n  Cast concept:\n   "
            f"{proposal.get('cast_concept', 'N/A')}")
        print('\n' + '-' * 64)
        print('  PROPOSED CHARACTERS')
        print('-' * 64)
        for i, char in enumerate(
            proposal.get('suggested_main_cast', []), 1
        ):
            print(
                f"\n{i}. {char.get('name', 'Unnamed')} "
                f"\u2014 {char.get('species', '?')}")
            print(f"   Role:        {char.get('role', '?')}")
            print(
                f"   Personality: {char.get('personality', '?')}")
            print(
                f"   Voice:       "
                f"{char.get('voice_description', '?')}")
        print('\n' + '=' * 64)

    def _interactive_adjust(
        self,
        proposal: Dict[str, Any],
        concept: str,
        style_context: str,
    ) -> Dict[str, Any]:
        """Prompt user to accept, resize, or reject."""
        while True:
            print('\nOptions:')
            print('  [a] Accept this cast')
            print('  [r] Resize cast (enter a new number)')
            print('  [n] Reject and regenerate with feedback')
            print('  [q] Cancel')
            choice = input('Choice: ').strip().lower()

            if choice == 'a':
                return proposal
            elif choice == 'r':
                try:
                    new_size = int(
                        input('New cast size (2-12): ').strip())
                    if not 2 <= new_size <= 12:
                        print('Size must be between 2 and 12.')
                        continue
                    print(
                        f'\nRegenerating with cast size '
                        f'{new_size}...')
                    forced_concept = (
                        f'{concept}\n\nIMPORTANT: Use exactly '
                        f'{new_size} main cast members.'
                    )
                    new_proposal = self._get_cast_proposal(
                        forced_concept, style_context)
                    if new_proposal:
                        self._display_proposal(new_proposal)
                        proposal = new_proposal
                except ValueError:
                    print('Invalid number.')
            elif choice == 'n':
                feedback = input(
                    'Feedback for regeneration: ').strip()
                if feedback:
                    print('\nRegenerating with your feedback...')
                    new_concept = (
                        f'{concept}\n\nPREVIOUS ATTEMPT '
                        f'FEEDBACK:\n{feedback}'
                    )
                    new_proposal = self._get_cast_proposal(
                        new_concept, style_context)
                    if new_proposal:
                        self._display_proposal(new_proposal)
                        proposal = new_proposal
            elif choice == 'q':
                raise KeyboardInterrupt(
                    'Show creation cancelled')
            else:
                print('Invalid choice.')

    # ── Merge / save ─────────────────────────────

    def _merge_bible(
        self,
        existing_bible: Dict[str, Any],
        show_id: str,
        name: str,
        concept: str,
        proposal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge show-specific metadata into the book-derived bible."""
        bible = dict(existing_bible) if existing_bible else {}
        bible.update({
            'show_id': show_id,
            'show_name': name,
            'concept': concept,
            'target_cast_size': proposal.get('target_cast_size'),
            'cast_concept': proposal.get('cast_concept'),
            'main_cast': proposal.get('suggested_main_cast', []),
            'created_at': time.time(),
        })
        return bible

    @staticmethod
    def _slugify(name: str) -> str:
        """Convert 'Prophets and Gamma' -> 'prophets_and_gamma'."""
        slug = re.sub(r'[^\w\s]', '', name.lower())
        slug = re.sub(r'\s+', '_', slug.strip())
        return slug[:50]
