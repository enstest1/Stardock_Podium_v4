# 01 — Current Repository Audit

Commit `c32a96570512a5b56af96e05eb8b13ce95bb1eec` (2026-04-25). 133 tracked files, 18,395 lines of Python. Everything here is **OBSERVED** unless labelled otherwise. Line numbers refer to that commit.

Classifications used: WORKING AND TESTED · IMPLEMENTED BUT UNVERIFIED · PARTIAL · BROKEN · MISSING · DEPRECATED.

"UNVERIFIED" at runtime means: the code path is complete on reading, but I could not execute it (it needs an LLM key, Mem0, a GPU or ffmpeg).

---

## 1. Summary table

| Subsystem | Files | Classification |
|---|---|---|
| Episode structure and beat timing | `story_structure.py` (`generate_episode_structure`, `_calculate_beat_durations`) | IMPLEMENTED BUT UNVERIFIED — its 6 tests fail on a stale mock |
| Cast generation | `story_structure.py` (`generate_character_cast`, `_generate_with_permanent_cast`, `_parse_characters`) | IMPLEMENTED BUT UNVERIFIED |
| Scene outlining | `story_structure.py` (`generate_scenes`, `_generate_scene_outline`, `_parse_scene`) | PARTIAL — runs, but scenes are generated independently |
| Scene scripting | `story_structure.py` (`generate_episode_script`, `_generate_scene_script`, `_parse_script_lines`) | PARTIAL — runs, but the scene outline is not passed to the writer |
| Agentic pipeline | `story_pipeline_agent.py` | PARTIAL — plan → script → QA metadata; no revision loop; flag off |
| Script editing | `script_editor.py` | IMPLEMENTED BUT UNVERIFIED |
| Director pass | `director_pass.py` | PARTIAL — pause metadata is written but only `export_timeline.py` reads it |
| Drafts and pins | `draft_store.py`, `script_line_ids.py` | IMPLEMENTED BUT UNVERIFIED |
| Quality checker | `quality_checker.py` | PARTIAL — continuity branch is dead code; scoring is one absolute 0–10 LLM score |
| Generation trace | `generation_trace.py` | IMPLEMENTED BUT UNVERIFIED — flag off |
| Show creation (Show OS) | `show_os/new_show.py` | IMPLEMENTED BUT UNVERIFIED |
| Season arc (Show OS) | `show_os/seasons.py` | IMPLEMENTED BUT UNVERIFIED — one committed example plan exists |
| Season beats (Story OS) | `story_os/planner.py` | PARTIAL — deterministic; drops beats; slots carry no content |
| Story OS models and I/O | `story_os/models.py`, `story_os/io.py` | WORKING AND TESTED (2 model tests pass); I/O untested |
| Story OS context | `story_os/context.py` | PARTIAL — flag off; emits beat IDs without text |
| Story OS show state | `story_os/show_state.py` | PARTIAL — keyword heuristics only |
| Bible RAG | `story_os/bible_rag.py` | IMPLEMENTED BUT UNVERIFIED — token overlap; flag off |
| Feature flags | `story_os/flags.py`, `data/feature_flags.json` | WORKING (read) — all off; two flags dead |
| Episode memory | `episode_memory.py` | PARTIAL — runs; extraction quality is poor (measured) |
| Mem0 client | `mem0_client.py` | IMPLEMENTED BUT UNVERIFIED — degrades to a no-op stub |
| Book knowledge | `book_knowledge.py`, `reference_memory_sync.py`, `epub_processor.py` | IMPLEMENTED BUT UNVERIFIED — prompts are franchise-specific |
| TTS engines | `tts_engine.py`, `dialogue_engine.py` | IMPLEMENTED BUT UNVERIFIED — Kokoro default, XTTS optional |
| Voice registry | `voice_registry.py`, `voices/*.json` | IMPLEMENTED BUT UNVERIFIED |
| Scene mixing | `audio_pipeline.py` (`_mix_scene_audio`) | PARTIAL — sequential concat; no overlap, ducking or loudness control |
| SFX and ambience | `audio_pipeline.py` (`_get_sound_effect`, `_add_scene_ambience`), `needed_audio_report.py` | PARTIAL — library lookup only; tracker WORKING AND TESTED |
| Audio QA | `audio_qa.py` | PARTIAL — duration and sample peak only; flag off |
| Timeline export | `export_timeline.py` | PARTIAL — estimates from word count, not from audio |
| Music | `generate_theme_music.py`, `assets/music/` | PARTIAL — paid ElevenLabs endpoint; three committed files |
| CLI | `cli_entrypoint.py`, `main.py` | IMPLEMENTED BUT UNVERIFIED — per-stage commands, no end-to-end command |
| Resume / job state | — | MISSING |
| RSS feed | `episode_metadata.py` (`generate_episode_feed`, `:604–662`) | PARTIAL — minimal RSS 2.0 string with hard-coded channel text and relative enclosure URLs (corrected in the universal-scope delta; I first listed this as missing) |
| Hosting upload, artwork, transcript, chapters | — | MISSING |
| Reference ingestion | `epub_processor.py`, `reference_memory_sync.py`, `book_style_analysis.py`, `ingest_all.py` | IMPLEMENTED BUT UNVERIFIED — EPUB only; one global library and namespace; no purpose, rights or project scope (doc 16 §A3) |
| Tests | `tests/` | 6 pass, 6 fail |
| ElevenLabs paths | `tts_engine.py`, `audio_pipeline.py:24–32, 141–152` | DEPRECATED (kept optional) |

---

## 2. Test baseline (run 2026-11-11)

Command, in a scratch copy with `pytest`, `pydantic`, `openai`, `mem0ai` 2.2.1, `python-dotenv` on Python 3.13:

```bash
STARDOCK_DISABLE_MEM0=1 python -m pytest tests -q -p no:cacheprovider
```

Result: **6 failed, 6 passed.**

- Pass: `test_story_os_models.py` (2), `test_episode_memory_series_filter.py` (2), `test_needed_audio_report.py` (2).
- Fail: all 6 in `tests/test_story_structure.py`, in `setUp`, with `AttributeError: <module 'story_structure'> does not have the attribute 'search_references'`. Line 48 patches a name that `story_structure.py` no longer imports (it imports `get_knowledge_context` instead, line 28).
- `test_episode_memory_series_filter.py` tests a copy of the filter logic pasted into the test file, not the production function.
- `tests/check_episode_speakers.py` is a script, not a test.

Not covered by any test: `planner`, `context`, `show_state`, `bible_rag`, `seasons`, `new_show`, extraction, `quality_checker`, `_parse_script_lines`, the mixer, the CLI.

---

## 3. Known areas A–F

### A. Two season planners — how they actually interact

They do not interact.

| | Show OS (`show_os/seasons.py`) | Story OS (`story_os/planner.py`) |
|---|---|---|
| CLI | `new-season --show <id> --season N --arc "..."` (`cli_entrypoint.py:845`) | `plan-season --series "<name>" --season s1 --episodes N` (`:708`) |
| Method | One LLM call, `ARC_BEATS_PROMPT` (`seasons.py:34–74`) | Index arithmetic over `StoryStructure.BEAT_SHEET` (`planner.py:39–54`) |
| Output | `data/shows/<show_id>/seasons/<N>/season_plan.json` with `arc_title`, `arc_summary`, `episode_beats[{episode_number, arc_beat, tension_level, arc_importance}]` | `data/series/<slug>/season_plan.json` (one file per series, season ignored on load — `io.py:64–68`) and `episode_slots/<n>.json` with `primary_beat_id`, empty `must_plant`, empty `must_payoff` (`planner.py:68–75`) |
| Key | `show_id` slug from the show name | slug of the episode's `series` string (default `Main Series`) |
| Reaches prompts via | `episode['arc_slot']`, copied at episode creation (`story_structure.py:265–295`), injected only into scene **script** prompts (`:1300–1311`) | `build_prompt_enrichment` (`context.py:72–84`), only when `USE_STORY_OS` is on, as `Primary beat id: stc_N` |
| Flag | none — always on if a show and season exist | `USE_STORY_OS` (off) |

Consequences:

1. The Show OS milestone is never seen by scene **outlining** (`_generate_scene_outline` prompt, `:1008–1040`), so the scenes are plotted without knowing what the season needs from the episode. It arrives only when dialogue is being written, with no plot to attach it to.
2. `arc_slot` is a snapshot. Editing the season plan later does not change existing episodes.
3. The Story OS slot contributes a label with no description. `must_plant` and `must_payoff` are always empty because nothing fills them.
4. `plan-season` for a second season overwrites the first (`io.save_season_plan` writes `season_plan.json` regardless of `season_id`).

They can be unified: the Show OS milestone is the right content, the Story OS slot is the right container. See `STORYOS-002`.

### B. Two storage structures — authoritative ownership

| Path | Written by | Read by |
|---|---|---|
| `data/series/series_bible.json`, `style_profile.json`, `extraction_stamp.json` (global, one per installation) | `SeriesBibleExtractor` (`book_knowledge.py:178–187`); overwritten by `ShowCreator.create_show` (`new_show.py:164–165`) | `KnowledgeContext` at `StoryStructure.__init__` (`book_knowledge.py:308–309`) — this is what every prompt uses |
| `data/shows/<show_id>/series_bible.json`, `show_state.json`, `seasons/<N>/season_plan.json` | `ShowCreator`, `SeasonPlanner` | `SeasonPlanner.get_episode_slot`; `past_guests` in `story_structure.py:646–661, 748–781` |
| `data/series/<slug>/series_bible.json`, `show_state.json`, `season_plan.json`, `episode_slots/`, `bible_chunks.json` | `init-story-os`, `plan-season`, `ingest-series-bible`, `update_show_state_after_script` | `story_os/context.py`, `_load_bible_cast` path 2 |
| `episodes/<episode_id>/structure.json`, `script.json`, `memories.json`, `drafts/`, `pins.json`, `audio/` | `story_structure.py`, `episode_memory.py`, `draft_store.py`, `audio_pipeline.py` | everything |

Findings:

- In the committed data, `data/series/series_bible.json` is byte-identical to `data/shows/star_trek_horizon/series_bible.json`. The global file is "the active show". Creating a second show silently repoints every prompt.
- There are two `show_state.json` shapes: the Show OS one (`current_season`, `episodes_produced`, `past_guests`, plus empty thread/fact lists) and the Story OS one (`ShowState` model). `episodes_produced` is written once as `0` and never updated (only reference: `new_show.py:173`).
- `structure.json` embeds the full script (`story_structure.py:1212`) and `script.json` holds it again. Edits through `script_editor` change `script.json` only.
- Episodes are stored flat under `episodes/` with random IDs; show and season membership exist only as fields inside the file.

**Recommended owner (PROPOSED):** `data/shows/<show_id>/` owns everything about a show. `data/series/<slug>/` becomes a read-only legacy location with a migration. The global bible becomes a derived mirror of the active show. See `STORYOS-001`.

### C. Rolling continuity — quality, persistence, reliability

Persistence: extraction writes each memory to Mem0 and all of them to `episodes/<id>/memories.json` (`episode_memory.py:104–114`). It runs automatically after script generation (`story_structure.py:1219–1226`). With Mem0 disabled, the JSON file is written but nothing reads it back for continuity (`get_previous_episode_context` reads only from Mem0, `:751`), so **continuity silently returns nothing** on hosts without Mem0.

Quality, measured with a probe against the real class on a 2-character, 1-scene, 4-line script:

```
plot      16   15 are "In episode 'T', during the '<beat>' beat: <Save the Cat description>"
chardev    3   "Character Development for ILEN: I think the team is tired" + 2 introductions
cont       2   "Continuity reference from ILEN: Same as before, Captain"
rel        0
state      4   "Final state of MARA: How long until the name is decoded?" (matched "am" in "name")
threads    3   every line containing "?" and a wh-word
```

Root causes, by line:

- `:130–139` stores beat *template* text as plot points for every episode.
- `:189–190` treats any line containing "I think", "I feel", "I believe" as character development.
- `:411–412` uses substring tests for `am`, `look`, `feel`, `seem` — `am` matches "name", "team", "same".
- `:462–481` stores every question as an unresolved thread; nothing ever closes one.
- `:359–366` detects a relationship only if a character says another *already-speaking* character's exact script name.
- `:589` re-reads the episode from disk once per memory added.

Retrieval: `get_previous_episode_context` loads **all** episode memories, keeps those with a lower episode number, sorts by episode number, and takes the first `limit` (15 from the scene generator, `story_structure.py:911–915`). Because one episode yields 15+ template "plot points", the 15 retrieved items are dominated by them. Scene outlining then shows the first 5 plot points, 3 threads and 5 states (`:918–928`).

`story_os/show_state.py` adds `last_seen_episode_id` per character and up to three "hooks" taken from the last five lines of the script when they end in `...` or contain one of five phrases such as "distress call" (`:16–43`). `active_threads` and `world_facts` are never written by any code.

**Verdict:** PARTIAL. Plumbing exists end to end; the content is not usable for continuity.

### D. Feature flags

`data/feature_flags.json` at this commit:

```json
{"USE_STORY_OS": false, "USE_AGENTIC_PIPELINE": false, "USE_SHOW_STATE_DIFF_PROMPTS": false,
 "USE_DIRECTOR_INLINE": false, "USE_BIBLE_RAG": false, "USE_GENERATION_TRACE": false,
 "USE_DIA2_DIALOGUE": false, "USE_BARK_SFX": false, "USE_AUDIO_QA_BLOCK": false}
```

- Resolution (`story_os/flags.py:27–45`): environment variable of the same upper-case name wins (`1/true/yes/on`), then the JSON file, then the default. The JSON path is relative to the working directory (`Path('data/feature_flags.json')`), not to `STARDOCK_DATA_DIR`.
- Overrides found: none. No script under `scripts/`, no `.env.example` entry. Only `Docs/Docs_New/WORKFLOW.md:44–45` mentions them.
- Code references: `USE_STORY_OS` ×6, `USE_AGENTIC_PIPELINE` ×2, `USE_DIRECTOR_INLINE`, `USE_SHOW_STATE_DIFF_PROMPTS`, `USE_BIBLE_RAG`, `USE_GENERATION_TRACE`, `USE_AUDIO_QA_BLOCK` ×1 each. `USE_DIA2_DIALOGUE` and `USE_BARK_SFX`: **zero** references.

Other environment switches (all `os.environ.get`): `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `MEM0_API_KEY`, `ELEVENLABS_API_KEY`, `STARDOCK_DISABLE_MEM0`, `STARDOCK_DISABLE_XTTS`, `STARDOCK_LINE_GAP_SEC`, `STARDOCK_INTRO_MUSIC_SEC`, `STARDOCK_INTRO_NARRATION_START_SEC`, `STARDOCK_INTRO_NARRATOR_FILTERS`, `STARDOCK_INTRO_MUSIC` / `STARDOCK_OUTRO_MUSIC`, `KOKORO_MODEL_PATH`, `KOKORO_*` tail-cleanup values, `HF_HOME`, `COQUI_TOS_AGREED`, `EDITOR`, and the seven `STARDOCK_*_DIR` paths.

Model choice is not configurable: `anthropic/claude-opus-4.5` (via OpenRouter) and `gpt-4o` are string literals in 7 files, 10 times in `story_structure.py` alone. `quality_checker.py:715` and `script_editor.py:351` always use `gpt-4o`, so the judge can be a different model from the writer by accident, never by design.

### E. Existing season examples

Two exist.

1. `data/shows/star_trek_horizon/seasons/1/season_plan.json` — "The Architects of Silence", 10 episodes, LLM-authored.
   - Strengths: a clear season question (is exploring this far courage or recklessness), a midpoint false victory with a cost (episode 6 activates a database and sends a signal), three non-central episodes (3, 5, 7), a finale that answers the question conditionally and opens another.
   - Weaknesses: milestones describe events, not character change or decisions; no setups are named for later payoff; the antagonist has no want; episodes 8–10 are one escalation in three steps; no commitment levels; nothing says what must not change.
   - Rights: it is set in the Star Trek universe aboard the USS Enterprise. It cannot be published as an original work.
   - Use in generation: copied to `episode['arc_slot']`, shown to the scene script writer only (see A).
2. `data/series/test_series/season_plan.json` — 3 episodes mapped to "Opening Image", "Fun and Games", "Final Image". A fixture, not a plan.

### F. Why sound effects do not blend

See §6.3. In short: the mixer is a concatenation, so an effect cannot overlap speech; almost no effect is ever found; there is no ducking, no crossfade, and no loudness control.

---

## 4. Story generation

### 4.1 `story_structure.py` (1,788 lines)

**Purpose.** Create an episode record, cast, scene outlines and script.
**Class.** `StoryStructure`; module-level wrappers `generate_episode`, `generate_characters`, `generate_scenes` (async), `generate_script`, `get_episode`, `list_episodes`.
**Callers.** `cli_entrypoint.py` commands; `story_pipeline_agent.py`; `audio_pipeline.py`, `quality_checker.py`, `script_editor.py` (`get_episode`).
**Dependencies.** `openai`, `book_knowledge`, `episode_memory`, `mem0_client`, `script_line_ids`, `config.paths`, lazily `show_os.seasons`, `story_os.*`, `draft_store`, `director_pass`.
**Inputs/outputs.** `episodes/<id>/structure.json`, `script.json`.

Flow and problems:

| Step | Lines | What happens | Problem |
|---|---|---|---|
| Create | 219–303 | ID, number, title, beats from `_calculate_beat_durations`, optional `arc_slot` | `self.episodes_dir` is `Path("episodes")` (134–141), ignoring `STARDOCK_EPISODES_DIR`, while `EpisodeMemory` uses `config.paths.EPISODES_DIR`. `mkdir(exist_ok=True)` without `parents`. Whole structure JSON is sent to Mem0 as a memory (418–444). |
| Title | 343–416 | LLM call | Prompt is "Generate a Star Trek-style podcast episode title" (358). |
| Cast | 466–783 | Permanent cast from the bible, optional guests | Fresh random `character_id` per episode for permanent cast (613–616) — IDs are not stable. Free-text parsing by regex (785–861). |
| Scenes | 863–979 | `asyncio.gather` over one prompt per scene (948–968) | **Scenes do not know about each other.** Each prompt has title, theme, beat name and description, scene N of M, cast list, RAG text, previous-episode noise. `scenes_per_beat` gives every beat at least one scene, so a 30-minute episode has 17 scenes regardless of story. |
| Outline parse | 1085–1145 | Regex for `Setting:`, `Characters:`, `Plot:` … | Fails on Markdown headings; falls back to raw `content`. |
| Script | 1147–1244 | Sequential loop over scenes (1188–1194) | Each call is independent of the previous scene's output. |
| Scene prompt | 1246–1423 | Context = title, theme, beat, setting, scene number, `name: species - role` list (1287–1294) | **`scene['plot']`, `dialogue`, `atmosphere`, `sound_effects` from the outline are not included.** Personality, backstory and voice notes are not included. `max_tokens=2000` caps a scene at roughly 1,300 words. |
| Post | 1196–1237 | line IDs, pins, optional director pass, save, memory extraction, optional show-state update | Script is saved inside `structure.json` and again in `script.json`. |

**Reusable.** `BEAT_SHEET` as one framework among several; `complete_text` as the seed of an LLM client; `_parse_script_lines` (robust, two formats); the save/load layout; the `extra_preamble` hook.
**Missing.** A causal outline; framework choice; revision; any knowledge of what characters know.
**Recommended.** `BASE-002`, `BASE-003`, `NARRATIVE-001`, `NARRATIVE-002`, `NARRATIVE-003`.

### 4.2 `story_os/planner.py`

Probe output (real function):

```
 8 → Opening Image, Setup, Debate, B Story, Midpoint, All Is Lost, Break into Three, Final Image
10 → Opening Image, Setup, Catalyst, Break into Two, B Story, Midpoint, Bad Guys Close In, Dark Night of the Soul, Break into Three, Final Image
13 → Opening Image, Theme Stated, Setup, Debate, Break into Two, B Story, Fun and Games, Midpoint, Bad Guys Close In, All Is Lost, Break into Three, Finale, Final Image
```

An eight-episode season has no Catalyst and no Finale; its last episode is "Final Image". The mapping samples beat *indices* evenly (`planner.py:43–44`); it does not group beats into acts. **PARTIAL.**

### 4.3 `story_pipeline_agent.py`

One planning call ("Scene N — goal — conflict — turn", ≤400 words, `:58–71`), then the normal script generator with that plan as a preamble on every scene, then a draft snapshot and a quality check whose result is stored in metadata (`:89–118`). The plan is written *after* scenes already exist and is not reconciled with them. Nothing is revised. The plan is, however, the only thing in the current system that gives the scene writers a shared account of the episode. **PARTIAL.** The function name `run_agentic_script_placeholder` (`:123`) is accurate.

### 4.4 `script_editor.py`

Load/save with revisions, line updates, scene regeneration, an external-editor round trip. `regenerate_scene` (`:271–385`) rebuilds the same thin context as the original writer and tells the model to keep "the same setting and beat"; it has no access to neighbouring scenes. It has its own older `_parse_script_lines` (`:387`), different from the one in `story_structure.py`. **IMPLEMENTED BUT UNVERIFIED**; reuse the revision store.

### 4.5 `director_pass.py`, `draft_store.py`, `script_line_ids.py`, `generation_trace.py`

- `director_pass.augment_script_with_director` sets `pause_after_ms` from punctuation and extracts `[sfx: ...]` (`:31–50`). The audio pipeline reads neither (grep: only `export_timeline.py:48` reads `pause_after_ms`). The `[sfx:` form is not what the script writer is asked to produce (it produces parenthesised lines).
- `draft_store` saves timestamped drafts and applies `pins.json` line overrides by `line_id`. Sound.
- `script_line_ids.ensure_script_line_ids` gives each line a UUID. Regenerating a scene creates new IDs, so pins and (future) evidence references to the old lines break — handled in `CANON-002`.
- `generation_trace` appends JSONL under `logs/generation/` when its flag is on. Path is relative to the working directory.

### 4.6 `quality_checker.py`

- `_check_continuity` (`:310–419`): reads `event["metadata"]` from `EpisodeMemory.get_timeline()` (`:357–362`), but timeline rows have no `metadata` key (`episode_memory.py:721–729`). `previous_characters` is always empty; the first half of the check never fires. The second half flags a "possible contradiction" when two texts share a capitalised word and exactly one has a negation within three words (`:421–462`).
- `_evaluate_script_with_ai` (`:665–743`): one `gpt-4o` call, absolute score 0–10, "Star Trek-style" in the prompt, requires `OPENAI_API_KEY` even when generation used OpenRouter.
- `check_episode_quality` writes results and calls `update_metadata`.
- Audio checks: integrity and properties through ffmpeg probe.

**PARTIAL.** Keep the structure, pacing and dialogue heuristics as cheap lint; replace continuity and scoring.

---

## 5. Show, season and knowledge

### 5.1 `show_os/new_show.py`

`ShowCreator.create_show` proposes a cast (JSON), lets the user accept/resize/regenerate, merges the result into the book-derived bible, writes it to both the show folder and the global path, and initialises `show_state.json`. It **requires ingested books** (`:124–130`): an original show with no source books cannot be created. Cast entries have no stable ID. **IMPLEMENTED BUT UNVERIFIED.**

### 5.2 `show_os/seasons.py`

Covered in §3A/E. JSON is parsed after stripping a code fence; any parse failure returns `{}` and raises "Failed to generate arc beats". No schema validation, no retry.

### 5.3 `story_os/models.py`, `io.py`, `context.py`, `show_state.py`, `bible_rag.py`

- Models: `ShowState`, `SeriesBible`, `CastMember`, `SeasonPlan`, `EpisodeSlot`, `SeriesArc`, `PlotThread`, `WorldFact`, `Hook`, `CharacterState`. Clean and small. `SeriesArc` has I/O helpers and no producer.
- `io.series_dir` creates the directory as a side effect of every read.
- `context.build_prompt_enrichment` is called once per scene outline and once per scene script, re-reading the same files each time.
- `bible_rag`: 900-character chunks, 120 overlap, set-overlap score. Works without embeddings; adequate for small bibles.

### 5.4 `book_knowledge.py`, `reference_memory_sync.py`

Three-tier design (bible always injected; RAG per scene; raw text stays in Mem0). The extraction prompts and the eight sampling queries are written for Star Trek (`:50–108, 202–211`). `get_rag_context` injects up to six **full book chunks** into every scene prompt (`:387–422`), under the heading "Reference Material". For an original show this is a route by which source-novel plot and phrasing enter the output; see doc 07 §2.

### 5.5 `mem0_client.py`

Wrapper over `mem0.MemoryClient` (managed, when `MEM0_API_KEY` is set) or `mem0.Memory.from_config` (local Qdrant + OpenAI embeddings). `add_memory` does not pass `infer` (`:142–149`). `get_all_memories` has no pagination. On any init failure the singleton becomes `_Mem0Disabled`, which returns empty results — robust, but silent. `requirements.txt` pins `mem0ai>=1.0.0`; the version that installs today is 2.2.1 (OBSERVED in the probe environment), so behaviour depends on install date.

---

## 6. Audio

### 6.1 `tts_engine.py`, `dialogue_engine.py`

`TTSEngine` abstract base with `KokoroEngine` (24 kHz mono, tail clean-up), `XTTSEngine` (Coqui TTS 0.22, reference clip resampled to 24 kHz), `ElevenLabsEngine` (legacy). `dialogue_engine` resolves a script speaker to a `voice_config.json` entry through exact key, canonical key, a 35-entry hand-maintained alias map, then lower-case; then tries engines in `engine_order` (committed value: `["xtts", "kokoro"]`).

- Both engines run text through `normalize_trek_tts_text` (`tts_engine.py:268, 417`).
- `tts_engine.py:374–375` sets `COQUI_TOS_AGREED=1` when it is unset, accepting the Coqui Public Model Licence on the user's behalf. That licence is non-commercial (doc 08 §2).
- The synthesiser reloads `voice_config.json` on every line (`dialogue_engine.py:207, 274, 293`).
- Voices are keyed by name slug, not by a character ID.
- No emotion, pace or style input reaches any engine.

### 6.2 `voice_registry.py`

Registry JSON plus sync into `voice_config.json`, health checks, smoke tests, character-to-voice mapping. Reusable as the persistence for stable voice identity.

### 6.3 `audio_pipeline.py` — exact reasons effects do not blend

| # | Cause | Evidence |
|---|---|---|
| 1 | Effects are sequenced, not layered. An SFX line becomes an entry in the same concat list as dialogue, separated by the inter-line gap. It can never start during a word. | `_mix_scene_audio` `:834–844` |
| 2 | Effects are rarely found. The search key is the whole description with spaces replaced (`the_gentle_hum_of_the_starships_engines`) used as `*key*.mp3|wav`. | `_get_sound_effect` `:605–609` |
| 3 | Nothing generates a missing effect. It is recorded in `needed_audio_assets.json` and skipped. `USE_BARK_SFX` is unused. | `:637–643` |
| 4 | Effects are reduced to 24 kHz mono 16-bit before mixing, then the scene is upsampled to 44.1 kHz stereo. Content above 12 kHz and all stereo width are lost. | `:812–828, 850–865` |
| 5 | `AudioClip.volume` (1.2 for SFX) and `AudioClip.start_time` are never used for line clips. | `:102–112, 631`; grep |
| 6 | Ambience plays at a fixed gain with no ducking under speech. | `:913–916` |
| 7 | `amix … normalize=1` scales both inputs down when ambience exists; scenes without ambience are not scaled. Dialogue level jumps between scenes. | `:913–916` vs `:945–958` |
| 8 | Ambience shorter than the scene is repeated with `aloop` and no crossfade: an audible seam on anything that is not a perfect loop. The file extension is built as `ambience..mp3` (double dot). | `:889–903, 708` |
| 9 | Ambience is chosen by matching 13 fixed keywords against the setting text; unmatched settings fall back to files named `background`/`ambience`. | `:660–693` |
| 10 | Scenes are joined by hard concatenation. Ambience stops dead at each scene boundary. | `_assemble_episode` `:1465–1505` |
| 11 | Lossy generations: dialogue PCM → MP3 256k → scene MP3 (no bitrate given in the ambience branch) → episode MP3 256k → metadata rewrite that re-encodes with no codec arguments. | `:866–879, 909–918, 1491–1505, 1514–1532` |
| 12 | No loudness measurement or normalisation anywhere; no true-peak control. | grep: no `loudnorm`, `ebur128` |
| 13 | Timing data does not exist. No word or line timestamps are recorded; `export_timeline.py` estimates at 2.4 words/second. | `export_timeline.py:15` |
| 14 | Script-side cues are free prose in parentheses with no anchor ("during", "after", "under"). | `_parse_script_lines` `:1584–1590` |

Other observations:

- Scenes render in a 4-thread pool (`:308`); each line is synthesised every run. There is no check for an existing line file, so an interrupted run starts over. `reassemble_episode_audio` (`:1542–1619`) rebuilds only intro/outro/concat.
- Intro narration text is hard-coded: "Captain's log, Starship Celestial Temple … Gamma Quadrant" (`:992–997`), as is the outro (`:1036–1039`). Intro narration is written to `assets/music/intro_narration.wav`, a shared path.
- `role_to_character` (`:159–165`) maps five roles to names from an older show; unused by the current resolver.
- Description lines are never voiced (`:498–500`), which is right, but it means anything the writer put in a description is lost to the listener. Scripts are not checked for audio-only clarity.

### 6.4 `audio_qa.py`, `export_timeline.py`, `needed_audio_report.py`

- `audio_qa`: for the first 200 WAVs under the episode's audio directory, records duration and sample peak; flags `< 0.05 s` and `peak > 0.99`. It scans WAVs, but the scene and episode mixes are MP3, so the final mix is never examined. **PARTIAL.**
- `export_timeline`: `exports/timeline.json` from word counts. Useful shape (`chapters` with `start_s`), wrong numbers. **PARTIAL.**
- `needed_audio_report`: thread-safe tracker, merges into an existing report. **WORKING AND TESTED.** Each re-run appends duplicates.

### 6.5 Music

`generate_theme_music.py` calls ElevenLabs' music endpoint (paid). `assets/music/` holds `Cosmic_Odyssey_Main_Theme.wav`, `theme_intro.mp3`, `theme_outro.mp3`; their origin and licence are not recorded in the repository (**UNVERIFIED** — confirm before publishing).

---

## 7. CLI and entry point

`main.py` checks the environment, creates directories, prints a banner ("optimized for Windows 10") and dispatches to `cli_entrypoint.main`. Commands are registered by decorator. The production path is five manual commands: `generate-episode` → `generate-characters` → `generate-scenes` → `generate-script` → `generate-audio`. `generate-episode` only creates the structure (`cli_entrypoint.py:297–309`). There is no command that runs a show, a season or an episode end to end, and no record of which stage an episode reached other than which files exist.

---

## 8. Documentation state

`Docs/` and `Docs/Docs_New/` contain 25 files, several duplicated across the two folders (`HOWTORUN.md`, `WORKFLOW.md`, `PROJECTSTRUCTURE.md`/`PROJECTSTRUCUTRE.md`, `KocoroTTS.md`/`KokoroTTS.md`). `Docs/Docs_New/BACKLOG.md` is accurate about what is stubbed. `MEMORY_CONTINUITY_SYSTEM.md` (685 lines) describes the memory categories as working continuity; the measurements in §3C do not support that. `Docs/TODO.md` is empty.

---

## 8a. Added in the universal-scope delta

- Mem0 uses three installation-wide namespaces: `user_id="reference_materials"`, `"episodes"`, `"characters"` (`mem0_client.py:270–387`). Shows are separated only by a `series` metadata string.
- `episode_metadata.py` keeps its own series and tag registries under `data/metadata` — a third place where a "series" is defined.
- `book_style_analysis.py` mixes technique statistics with character, setting and plot extraction in one analysis.
- A widened franchise scan finds franchise wording in 17 non-test Python files; the per-line table is in doc 16 §A4.

## 9. Things that are easy to miss

1. `StoryStructure` requires `OPENAI_API_KEY` or `OPENROUTER_API_KEY` only for generation, but `quality_checker` and `script_editor.regenerate_scene` require OpenAI specifically.
2. Fresh `character_id`s per episode mean nothing can be joined on character ID today.
3. `series` on an episode defaults to `"Main Series"`; a show created with `new-show` and episodes generated without `--series` land in different Story OS folders.
4. The Story OS flag changes *who is in the cast*: with the global bible present, path 1 of `_load_bible_cast` wins regardless of the flag.
5. `voices/samples/` contains one committed MP3; the nine `speaker_wav` paths in `voice_config.json` point to files that are not in the repository. Provenance and consent for those reference voices are not documented.
