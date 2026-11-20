# 00 — Executive Summary

**Project:** Stardock Podium — autonomous serialized audio-fiction studio
**Repository audited:** `https://github.com/enstest1/Stardock_Podium_v4` at commit `c32a96570512a5b56af96e05eb8b13ce95bb1eec` (2026-04-25), MIT
**Research date:** 2026-11-11
**Audience:** a Cursor session that has this folder and the repository, and nothing else.

## Product scope correction (added in the universal-scope delta)

Stardock Podium is a **universal AI podcast studio**: one sentence creates an original podcast in any genre or format — fiction of any kind, documentary, educational, conversational, anthology. Star Trek was the development example and remains only as a private legacy fixture. Nothing in this handoff requires a pre-existing universe, an EPUB or a reference library.

Consequences for reading the rest:

- Everything about season arcs, canon, character psychology and replanning is the **serialized-fiction configuration**. It is retained in full and is switched on by a project's production mode, not applied to every podcast.
- References are optional and purposeful (style, facts, authorised world, authorised adaptation), scoped to a project, weighted by the user.
- `16_UNIVERSAL_SCOPE_AND_REFERENCE_CONTROL.md` lists every correction, including two errors in my first audit, and holds the Creative Reference Control design. Documents 10, 11, 12 and 14 were updated in place.

## How to read claims in these documents

Every claim carries one of these labels, explicitly or by section:

| Label | Meaning |
|---|---|
| **OBSERVED** | I read the code or ran it at the commit above. |
| **VERIFIED-EXTERNAL** | I read it in an external repository cloned on 2026-11-11, or on a page fetched that day. |
| **INFERENCE** | Engineering reasoning from observed facts. Not tested. |
| **PROPOSED** | Design I am recommending. Nothing in the repository implements it yet. |
| **UNVERIFIED** | Could not be confirmed. Treat as a question, not a fact. |

Nothing in the repository was modified. No code was committed.

## What was and was not done

- **Done:** full source read of the story, planning, memory and audio modules; the existing test suite run in an isolated copy; two probes run against the real modules (beat distribution, memory extraction); 20 external repositories cloned and inspected at source level, including licence files; publishing and audio-spec pages fetched.
- **Done:** three pieces of reference code written and executed (`reference/canon_models.py`, `reference/mix_sketch.py`, `reference/replan_check.py`).
- **Not done:** no LLM generation was run (no API keys in the research environment), and no GPU was available. So the Part 7 replanning experiment is a deterministic fixture analysis plus a reproducible harness specification, not a prose comparison, and **no TTS model was listened to or benchmarked**. Both are flagged wherever they matter, and both have a runnable protocol in doc 12.

## A. Architectural assessment

Stardock has more infrastructure than its output quality suggests, and the gap has one main cause: **the pieces are not connected along the path a story actually travels.**

1. **Scenes are written blind (OBSERVED).** Scene outlines are generated concurrently, each knowing only its beat name (`story_structure.py:948–968`). Then each scene's script prompt is built from title, theme, beat, setting and a cast list (`story_structure.py:1287–1294`) — the outline's own `plot` field is never passed to the script writer, and neither is the previous scene's text. An episode is therefore 15–17 independently imagined scenes that share a title. No downstream editing can repair that.
2. **Every episode has the same shape (OBSERVED).** All 15 Save the Cat beats are applied to every episode (`story_structure.py:41–132, 257`). The season-level use of the same sheet silently drops beats: for 8 or 10 episodes the planner never assigns "Finale", and for 8 it also drops "Catalyst" (probe output in doc 01 §4.2).
3. **Two planners, two stores, no link (OBSERVED).** `show_os/seasons.py` writes rich LLM milestones under `data/shows/<show_id>/`; `story_os/planner.py` writes beat labels under `data/series/<slug>/`. They are keyed differently (show id vs. the `--series` string) and never read each other. The Story OS slot reaches prompts as the literal text `Primary beat id: stc_7` (`story_os/context.py:76–79`).
4. **Continuity memory is mostly noise (OBSERVED, measured).** `episode_memory.py` extracts with keyword heuristics. On a four-line test scene it produced 28 memories; 15 were the Save the Cat template descriptions stored as "plot points", every question became an "unresolved thread", and "How long until the n**am**e is decoded?" was stored as a character's emotional state because it contains `am`. The one fact that mattered (a character denied opening a log) was not captured as such.
5. **Semantic memory can rewrite history (OBSERVED + VERIFIED-EXTERNAL).** `mem0_client.add_memory` calls Mem0 without `infer=False` (`mem0_client.py:142–149`). Mem0's default is LLM fact inference with update and delete of existing memories (`mem0/memory/main.py:770, 790`). There is no canonical record that Mem0 cannot change.
6. **Sound effects cannot blend because the mixer has no time axis (OBSERVED).** SFX are appended to the same concat list as dialogue (`audio_pipeline.py:834–844`), so they can only play *between* lines. They are looked up by globbing the entire description (`:605–609`), which almost never matches, and nothing generates a missing one. Everything is folded to 24 kHz mono before mixing (`:850–865`).
7. **The committed example show is third-party IP, and the voice-clone path is non-commercial (OBSERVED).** The only show is "Star Trek: Horizon" with the USS Enterprise; franchise wording appears in 14 Python files, including the title, cast, scene and script prompts. XTTS v2 is first in `engine_order`, and the code auto-accepts Coqui's licence terms (`tts_engine.py:374–375`). Neither is compatible with publishing an original commercial podcast.
8. **Feature flags (OBSERVED).** All nine flags in `data/feature_flags.json` are `false`. Two (`USE_DIA2_DIALOGUE`, `USE_BARK_SFX`) have no code references at all. No script or doc in the repository sets an override.
9. **Tests (OBSERVED, run).** 12 collected, 6 pass, 6 fail. All six failures are one stale mock target (`tests/test_story_structure.py:48`). Nothing tests planning, context assembly, extraction, mixing or the CLI.

## B. Worth preserving

`show_os` show/season creation and its milestone JSON shape; the Story OS Pydantic models and I/O helpers; `story_os/flags.py`; `script_line_ids.py` (stable line IDs are the anchor for everything proposed here); `draft_store.py` pins; `generation_trace.py`; `_parse_script_lines`; `dialogue_engine.py` name resolution and engine fallback; `voice_registry.py`; `needed_audio_report.py`; `config/paths.py`; the intro/outro ffmpeg mixes; `_Mem0Disabled` degradation. Details in doc 01.

## C. The recommended design in one paragraph

Make `data/shows/<show_id>/` the single home of a show. Put an **append-only canon ledger** there (JSONL plus a rebuildable SQLite index) as the only source of truth; every fact must cite script `line_id`s and pass a Python quote check. Derive character knowledge, relationships and promises from it. Merge the two planners into one **versioned season roadmap** whose milestones are `locked`, `guided` or `open`; replan only unapproved episodes after each approval. Replace blind parallel scenes with **sequential scene cards** (goal, opposition, turn, value shift, hand-off), write each scene against its card and the previous hand-off, and choose an episode framework per episode. Add a small writers' room (three premises, pairwise choice, one editor pass by a different model) and keep only the passes an ablation shows are worth their cost. Replace the concat mixer with a **sample-accurate multitrack timeline** driven by forced word alignment, with sidechain ducking, crossfaded loops, stems, and one final loudness-normalised encode. Publish through an RSS host with an API; Spotify is a one-time manual submission of that feed.

## D. Decisions on the named repositories

| Repository | Decision | One-line reason |
|---|---|---|
| StoryDaemon | ADAPT SELECTED TECHNIQUES | Judged loop closure, loop horizons, evidence-checked consequences, tension curve owned by code. No licence file in repo. |
| NovelGenerator | USE AS INSPIRATION | Evidence-cited state extraction and scene rebase are the right ideas; Business Source Licence 1.1 forbids production use of the code. |
| longform-writing-bench | ADAPT SELECTED TECHNIQUES | Negative criteria, slop and repetition metrics. No licence file. |
| lechmazur/writing | ADAPT SELECTED TECHNIQUES | Pairwise, both orders, several judges; it abandoned absolute 0–10 scores. No licence file. |
| Graphiti | USE AS INSPIRATION | Bi-temporal fields adopted; the library needs a graph server and lets an LLM invalidate facts. |
| LangGraph | REJECT (for now) | The pipeline is linear with checkpoints; a 150-line job runner covers it. |
| MOSS-TTS family | ADAPT / benchmark candidate | Apache-2.0 code and weights; dialogue, voice design and 48 kHz SFX models. |
| Chatterbox | ADAPT / benchmark candidate | MIT; Turbo has laugh/cough tags; watermarks output; repo declared an unsupported archive. |
| Fish Speech | REJECT as default | Drama 3 needs ≥48 GB VRAM; S2-Pro weights are research-licensed. |
| VibeVoice | REJECT for TTS | TTS code removed upstream; ASR model is a possible QA tool. |
| soundbox | INTEGRATE (optional provider) | MIT, local HTTP API for SFX/music/speech; per-model licences shown. |
| ACE-Step 1.5 | INTEGRATE (music provider) | MIT, 10 s–10 min, runs from ≤6 GB VRAM. |

Full reviews, with files and steps, are in doc 02.

## E. Roadmap at a glance

| Phase | Outcome | Size |
|---|---|---|
| 0 | Green baseline, config for models, franchise text removed from prompts | S |
| 1 | Projects and production modes, one-sentence creation, one show store, project isolation, reference registry and influence control, one roadmap model | L |
| 2 | Canon ledger, evidence-checked extraction, beliefs, promises | L |
| 3 | Versioned roadmap, rolling replanning | M |
| 4 | Scene cards, sequential causal writing, framework selection, character state | L |
| 5 | Writers' room, editor pass, originality metrics, ablation | M |
| 6 | Sound design in the script, sound identities tied to canon | M |
| 7 | Provider interfaces; TTS/SFX/music benchmark and choice | M |
| 8 | Multitrack timeline, alignment, ducking, mastering, QA | L |
| 9 | One command idea-to-episode, persistent jobs, resume | M |
| 10 | Artwork, metadata, transcript, chapters, RSS, host upload | M |
| 11 | Long-run validation | M |

Phases 6–8 (audio) do not depend on phases 2–5 (story) and can run in parallel after phase 1. Start with phase 0, then `NARRATIVE-001` in phase 4 can be pulled forward: it is the single change with the largest effect on story quality and it depends only on phase 0.

## F. Where to go next

Read `14_CURSOR_MASTER_EXECUTION_PROMPT.md` first if you are Cursor. Read `01` for evidence, `04` for the target design, `11` for the change specifications.
