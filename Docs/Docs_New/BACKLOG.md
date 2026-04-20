# Enhancement backlog (optional / later)

This file is the canonical place for **follow-up work** that is not required
for the current Kokoro-first + Story OS pipeline. Pick items when you want
deeper quality, scale, or automation—not before.

---

## 1. Audio QA (publish-grade)

**Today:** `audio_qa.py` + `USE_AUDIO_QA_BLOCK` — per-file duration via ffmpeg
probe, optional peak hints when `soundfile` / `numpy` are available.

**Later:**

- **LUFS** — integrated loudness (e.g. **-16 LUFS** stereo podcast target, or
  your house standard); fail or warn stems and full mix.
- **Clipping** — true full-waveform clip detection across the **final mix**,
  not only per-scene WAVs.
- **Speaker consistency** — short embedding per dialogue stem vs reference;
  flag likely wrong-voice takes before publish.

**Touch points:** `audio_qa.py`, `audio_pipeline.generate_episode_audio` (after
assemble), optional thresholds in `data/` or env.

---

## 2. Agentic script loop (critique → patch)

**Today:** `story_pipeline_agent` — **plan →** `generate_episode_script` with
preamble **→** script-only `quality_checker` **→** metadata on episode.

**Later:**

- Parse `quality_checker` issues that reference **`line_id`** or scene index.
- **Critique pass** — LLM returns structured patches
  (`{ "line_id": "...", "new_content": "..." }`).
- Apply patches, re-run targeted checks, optional **scene-level retry** if a
  scene fails thresholds.

**Touch points:** `story_pipeline_agent.py`, `quality_checker.py` output shape,
`draft_store` / `pins.json` for human override alongside auto patches.

---

## 3. Bible RAG (vector search)

**Today:** `story_os/bible_rag.py` — chunked text + **token overlap** scoring;
`ingest-series-bible` CLI; snippets injected when `USE_BIBLE_RAG` is on.

**Later:**

- **Mem0** or local embeddings for `data/series/<id>/` bible chunks.
- Hybrid: keyword pre-filter → top-k vectors; dedupe and cite `source` paths
  in prompts.

**Touch points:** `story_os/bible_rag.py`, optional `mem0_client` series-scoped
collection, same `build_prompt_enrichment` contract.

---

## 4. `series_arc.json` (explicit series arc)

**Today:** Pydantic **`SeriesArc`** and I/O helpers in `story_os/io.py`; primary
planning path is **`season_plan.json`** + **`episode_slots/<N>.json`**.

**Later:**

- CLI to **init / edit / validate** `series_arc.json`.
- **Planner hooks** — when generating a season, merge arc obligations into
  slots or episode metadata.
- Optional export for writers’ room (markdown / Notion).

**Touch points:** `story_os/planner.py`, `story_os/io.py`, `cli_entrypoint.py`.

---

## 5. Ops — tests and CI

**Today:** `requirements.txt` includes **pytest** and **pytest-asyncio**;
`tests/` holds unit tests. Some environments only run `unittest` if pytest is
not installed.

**Later:**

- Document in onboarding: **`pip install -r requirements.txt`** before
  `pytest tests/ -q`.
- Optional **GitHub Actions** (or other CI): install deps, run
  `python -m pytest tests/ -q`, cache pip.

**Touch points:** root `README.md`, `.github/workflows/` (if you add CI).

---

## 6. Other flags (already stubbed in config)

- **Dia2** / **Bark** — `USE_DIA2_DIALOGUE`, `USE_BARK_SFX` in
  `data/feature_flags.json`; wire when backends are chosen and packaged.

---

*Last aligned with repo behavior: Story OS + Kokoro workflow. For the live
runbook see **`WORKFLOW.md`** in this folder.*
