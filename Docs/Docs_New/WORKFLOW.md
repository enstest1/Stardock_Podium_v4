# Stardock Podium — End-to-End Workflow (v4+)

This document describes the **current** production path after the Kokoro-first
and Story OS refactor. Older references to **Coqui** (historical local TTS) and
**ElevenLabs** as the default dialogue engine are **obsolete** for the main
audio pipeline.

---

## 1. High-level stages

| Stage | Module / entry | Output |
|--------|------------------|--------|
| Ingest reference | `epub_processor`, `reference_memory_sync` | `books/`, Mem0 |
| Episode shell | `story_structure.generate_episode_structure` | `episodes/<id>/structure.json` |
| Cast | `story_structure.generate_character_cast` | `structure.json` characters |
| Scenes | `story_structure.generate_scenes` | Scene outlines |
| Script | `story_structure.generate_script` / `generate_episode_script` | `script.json` |
| Memory extract | `episode_memory.extract_memories_from_episode` | Mem0 + `memories.json` |
| Quality | `quality_checker`; optional `audio_qa` (flags) | `quality_check.json`, `audio/audio_qa_report.json` |
| Voice lines (CLI) | `cli/generate_voices.py` | WAV per line |
| Full mix | `audio_pipeline.generate_episode_audio` | `episodes/<id>/audio/` |

---

## 2. Story generation (text)

1. **Structure** — Save the Cat **episode** beats, metadata, empty scenes.
2. **Characters** — LLM cast; names must match `voices/voice_config.json` keys
   (or role mapping in `audio_pipeline`).
3. **Scenes** — Beat-driven outlines. For episode number &gt; 1, continuity
   context comes from `episode_memory.get_previous_episode_context` (Mem0 +
   `series` metadata; legacy rows **without** `series` still match).
4. **Script** — Per-scene dialogue. With **`USE_AGENTIC_PIPELINE`**, run
   **`story_pipeline_agent.run_agentic_episode_script`**: LLM beat plan → same
   per-scene writer with plan as preamble → optional **`draft_store`** snapshot
   → script **`quality_checker`** pass. Otherwise a single **`generate_episode_script`**
   pass. CLI: **`python cli_entrypoint.py generate-script <episode_id>`**.
5. **Memory** — After script save, heuristics push categorized memories; every
   write includes **`series`** when the episode record has it.

### Story OS (optional, flags)

- **`data/feature_flags.json`** and env vars (e.g. `USE_STORY_OS=1`,
  `USE_AGENTIC_PIPELINE=1`, `USE_DIRECTOR_INLINE`, `USE_BIBLE_RAG`,
  `USE_GENERATION_TRACE`, `USE_AUDIO_QA_BLOCK`).
- On-disk layout under **`data/series/<series_id>/`** (`series_id` = slug from
  series name): **`series_bible.json`**, **`show_state.json`**, optional
  **`series_arc.json`**, **`season_plan.json`**, **`episode_slots/<N>.json`**
  (one file per planned episode index **`N`**, matched to
  **`episode_number`**).
- **Planner** — `story_os.planner.plan_and_write`; CLI **`plan-season`**.
- **Bible RAG** — `story_os.bible_rag` + CLI **`ingest-series-bible`**; snippets
  are injected when **`USE_BIBLE_RAG`** is on.
- **Show state** — `story_os.show_state.update_show_state_after_script` runs
  after each successful script save when **`USE_STORY_OS`** is on.
- **Prompt wiring** — `story_os.context.build_prompt_enrichment` is appended in
  **`generate_scenes`** (outlines) and **`_generate_scene_script`** (lines).
- **Collaboration** — `episodes/<id>/pins.json` (`line_overrides`) and
  **`drafts/`** snapshots via **`draft_store`**.
- **Director** — `director_pass.augment_script_with_director` when
  **`USE_DIRECTOR_INLINE`** (adds per-line **`director`** metadata).
- **Tracing** — `generation_trace.log_step` → **`logs/generation/<run>.jsonl`**
  when **`USE_GENERATION_TRACE`**.
- **Exports** — `export_timeline.export_episode_timeline` →
  **`episodes/<id>/exports/timeline.json`**; CLI **`export-timeline`**.
- Schemas: **`story_os/models.py`** (Pydantic). Init templates: CLI
  **`init-story-os`**.

---

## 3. Script JSON format

Episodes use `episodes/<episode_id>/script.json` with scenes and lines:

- **`type`**: `description` | `dialogue` | `narration` | `sound_effect`
- **`content`**: line text
- **Dialogue**: `speaker` or `character` (both supported)
- **Optional** (recommended for future ADR / pins): **`line_id`** (UUID),
  **`director`** object (pause, sfx cue, etc.). Use **`script_line_ids`** to
  assign missing ids before save.

---

## 4. Voices and dialogue TTS (Kokoro)

1. **Samples** — Mono **16 kHz** WAV, ~**5–10 s**, under `voices/samples/`.
2. **Config** — `voices/voice_config.json`:
   - `"engine_order": ["kokoro"]` for local-only dialogue.
   - Each character: **`speaker_wav`**, **`language`** (e.g. `"en"`).
   - **`narrator`** entry required for narration, intro, and outro lines.
3. **Synthesis** — `dialogue_engine.KokoroDialogueSynthesizer` wraps
   `tts_engine.KokoroEngine`. **`audio_pipeline`** and
   **`cli/generate_voices.py`** use this path for speech.
4. **Validation** — `python cli/validate_voices.py --config voices/voice_config.json`

**ElevenLabs** is optional (legacy `voice_registry` cloud APIs). It is **not**
required for `audio_pipeline` dialogue.

---

## 5. Sound effects and ambience (library-first)

1. Place files under **`assets/sound_effects/`**, **`assets/ambience/`**,
   **`assets/music/`**.
2. The pipeline **does not** generate SFX/ambience from cloud APIs.
3. If no file matches a cue, the run appends to
   **`episodes/<id>/needed_audio_assets.json`** so you can add assets and
   re-run.

---

## 6. Audio pipeline run

```bash
python main.py
# or programmatically:
from audio_pipeline import generate_episode_audio
generate_episode_audio('<episode_id>', {})
```

- Scene dialogue → **Kokoro** WAV stems → mix (ffmpeg).
- Intro/outro narration → **Kokoro** to `assets/music/intro_narration.wav`
  and `outro_narration.wav` (WAV), then combined with theme music if present.

---

## 7. Environment

| Variable | Role |
|----------|------|
| `OPENAI_API_KEY` or `OPENROUTER_API_KEY` | LLM for story generation |
| `MEM0_API_KEY` | Optional Mem0 cloud |
| `ELEVENLABS_API_KEY` | **Optional** — only for legacy voice-registry cloud |

Kokoro needs local **PyTorch** + **kokoro-tts** per `requirements.txt` and the
**checkpoint** file expected by `tts_engine` (`kokoro-tts-base-ft.pt`).

---

## 8. Roadmap (short)

Optional work (LUFS, agentic patches, vector bible RAG, `series_arc` CLI,
pytest/CI, Dia2/Bark) is tracked in detail here:

**[`BACKLOG.md`](BACKLOG.md)**

---

## 9. Quick command reference

```bash
pip install -r requirements.txt
python main.py --help
python cli_entrypoint.py init-story-os --series "Main Series"
python cli_entrypoint.py plan-season --series "Main Series" --season s1 --episodes 10
python cli_entrypoint.py ingest-series-bible --series "Main Series" ./Docs/bible_md
python cli_entrypoint.py generate-script <episode_id>
python cli_entrypoint.py export-timeline <episode_id>
python cli/validate_voices.py --config voices/voice_config.json
python cli/generate_voices.py --script episodes/<id>/script.json --output ...
```

For project layout see `Docs/Docs_New/PROJECTSTRUCUTRE.md`.
