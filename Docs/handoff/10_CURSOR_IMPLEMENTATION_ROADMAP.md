# 10 — Cursor Implementation Roadmap

Change IDs are specified in doc 11. Tests (`T01`…`T14`, `EXP-*`) are in doc 12. Complexity: S ≤ 1 day, M 2–4 days, L 1–2 weeks of focused work (estimates, **UNVERIFIED**).

## 0. Universal-scope delta (applied in place)

This roadmap was updated for the product correction in doc 16. Eight tasks are NEW, nineteen MODIFIED (amendments in doc 11), the rest UNCHANGED; one switch (`use_book_rag` inside BASE-003) is SUPERSEDED. The per-task status is the last column of the index in doc 11 and the table in doc 16 §E. No task was duplicated: new work sits in the phase where its prerequisite already was.

| New task | Phase | After | Before |
|---|---|---|---|
| GEN-001 Project config, production modes, `create-podcast` | 1 | BASE-003 | STORYOS-001 |
| GEN-003 Project isolation (Mem0, voices, metadata) | 1 | STORYOS-001 | anything that writes memory |
| REF-001 Reference registry | 1 | GEN-001, GEN-003 | REF-002, REF-003 |
| REF-002 Technique profiles and influence control | 1 | REF-001 | NARRATIVE-003 |
| REF-003 Claims, citations, conflicts | 2 | REF-001, QUALITY-003 | GEN-002 |
| REF-004 Authorised world building and adaptation | 2 | REF-001, CANON-001 | — |
| REF-005 Reference lifecycle and snapshots | 2 | REF-002 | PUB-003 |
| GEN-002 Nonfiction pipeline (segment cards, factual editorial) | 4 | GEN-001, NARRATIVE-001, REF-003 | Phase 11 |

Serialized fiction keeps every capability of the original plan; with `mode = serialized_fiction` the phases below behave as first written, plus project scoping.

## 1. Dependency graph

```
BASE-001 ─► BASE-002 ─► BASE-003 ─► GEN-001 ─► STORYOS-001 ─► GEN-003 ─► REF-001 ─► REF-002
                │                                   │                          ├──► REF-003 ─► GEN-002
                ├──► NARRATIVE-001 (pull-forward)   │                          └──► REF-005
                ▼                                   ▼            (REF-004 also needs CANON-001)
          (as before)                      STORYOS-002 ─► STORYOS-003
                │              │
                │              └────────────► PLAN-001 ─► PLAN-002 ─► PLAN-003
                ▼                                 ▲            ▲
          CANON-001 ─► CANON-002 ─► CANON-003     │            │
                           │   └──► CANON-004 ────┘            │
                           │   └──► CANON-005                  │
                           ▼                                   │
          CHAR-001 ◄── NARRATIVE-001 ─► NARRATIVE-002 ─► NARRATIVE-003
                           │
                           ▼
          QUALITY-003 ─► QUALITY-001 ─► WRITERS-001 ─► QUALITY-002 ─► (EXP-ABLATE, EXP-ORIG)
                                             └── needs PLAN-002

  Audio track (independent of CANON/PLAN/QUALITY; needs BASE-001 and STORYOS-001 only for paths):
          AUDIO-001 ─► AUDIO-002 ─► AUDIO-003 ─► AUDIO-004
                           │             ▲
                           ▼             │
                       AUDIO-005 ────────┘──► AUDIO-007
          AUDIO-006 (independent)        AUDIO-008 (needs AUDIO-005; canon link needs CANON-001)

          AUTO-001 (needs NARRATIVE-001, AUDIO-003) ─► PUB-003 ─► PUB-001 ─► PUB-002
```

**Can be done independently / in parallel:** the whole audio track vs the story track; `AUDIO-006` at any time; `QUALITY-003` (judge) any time after `BASE-002`; `CANON-005` any time after `CANON-001`; `BASE-003` alongside `STORYOS-001`.

**Do not parallelise:** `STORYOS-001` with anything that writes show files; `CANON-001/002`; `AUDIO-002/003`.

## 2. Phases

### Phase 0 — Baseline and repository safety

| | |
|---|---|
| Objectives | A green, recorded baseline; model names and franchise text out of code; nothing behavioural changes yet |
| Tasks | Record commit, Python and package versions in `Docs/handoff/PROGRESS.md`; run the suite (expect 6/6); `BASE-001`; `BASE-002`; `BASE-003`; snapshot one legacy episode's `structure.json`/`script.json` as a golden fixture |
| Files | `tests/test_story_structure.py`, `story_structure.py`, `quality_checker.py`, `script_editor.py`, `book_knowledge.py`, `show_os/*.py`, `story_pipeline_agent.py`, `audio_pipeline.py`, `tts_engine.py`; new `story_os/llm.py`, `data/llm_config.json`, `data/shows/<id>/show_profile` fields |
| Prerequisites | None |
| Complexity | S + M + M |
| Risks | Prompt wording changes alter output; mitigated by keeping the Star Trek show's profile reproducing the old strings exactly |
| Tests | `pytest tests -q` → 12 pass after `BASE-001`; new tests per change; golden prompt test for `BASE-003` |
| Acceptance | Suite green; `grep -rn "claude-opus\|gpt-4o" --include=*.py .` returns only `story_os/llm.py` defaults; `grep -rni "star trek" --include=*.py .` returns nothing outside tests and migration code |
| Rollback | `git revert` per change; no data migration in this phase |

### Phase 1 — Unified Story OS

| | |
|---|---|
| Objectives | Projects with production modes and one-sentence creation; one show store keyed by `show_id` inside a project; strict project isolation; optional, purpose-typed references with influence control; one plan model per mode; honest flags; one context assembler |
| Tasks | `GEN-001`, `STORYOS-001`, `GEN-003`, `REF-001`, `REF-002`, `STORYOS-002`, `STORYOS-003` |
| Files | New `story_os/store.py`, `story_os/roadmap.py`, `story_os/assembler.py`; `story_os/io.py`, `context.py`, `flags.py`, `show_os/new_show.py`, `show_os/seasons.py`, `story_structure.py`, `cli_entrypoint.py`, `book_knowledge.py`, `data/feature_flags.json` |
| Prerequisites | Phase 0 |
| Complexity | M + M + M + M + M + M + M |
| Risks | Path migration; episodes created under the old slug; two `show_state.json` shapes; a Mem0 call left without `project_id`; technique extraction leaking names (guarded, T16) |
| Tests | T01 (planning) partially; store round-trip; migration dry-run on the committed `star_trek_horizon` and `test_series` data; T15, T16, T17, T18, T20 |
| Acceptance | `migrate-shows --dry-run` reports no conflicts on committed data; after migration a legacy episode still generates a script with identical prompts (golden test); creating a second show does not change the first show's prompts |
| Rollback | Migration writes a backup tarball and a manifest; `migrate-shows --rollback <manifest>` restores; code revert |

### Phase 2 — Canonical memory

| | |
|---|---|
| Objectives | Ledger as source of truth; evidence-checked extraction; beliefs; promises; Mem0 demoted |
| Tasks | `CANON-001` → `CANON-002` → `CANON-003`, `CANON-004`, `CANON-005`; `REF-003`, `REF-004`, `REF-005` (canon tasks run only for modes whose `continuity` capability needs them) |
| Files | New `story_os/canon_models.py`, `canon_store.py`, `canon_extract.py`, `beliefs.py`, `promises.py`; `episode_memory.py`, `mem0_client.py`, `quality_checker.py`, `story_structure.py` (hook after script), `cli_entrypoint.py` |
| Prerequisites | Phase 1; `BASE-002` |
| Complexity | M + L + M + M + S |
| Risks | Extraction accuracy; cost; line-ID churn on regeneration |
| Tests | T03, T04, T05, T06, T08; rebuild determinism; "only canon_store writes the ledger" grep test |
| Acceptance | On the annotated fixture: precision ≥ 0.9 of verified records, recall ≥ 0.8 of annotated consequential facts (targets; see doc 12); deleting `index.sqlite` and `state/` and rebuilding reproduces them byte-identically; continuity context works with `STARDOCK_DISABLE_MEM0=1` |
| Rollback | Flag `USE_CANON_LEDGER=false` restores legacy extraction; the `canon/` folder is additive and can be deleted |

### Phase 3 — Rolling season planning

| | |
|---|---|
| Objectives | Roadmap with commitment levels, mystery solutions, validation, versioned replanning |
| Tasks | `PLAN-001`, `PLAN-002`, `PLAN-003` |
| Files | `show_os/seasons.py`, `story_os/roadmap.py`, new `story_os/episode_planner.py`; `cli_entrypoint.py` |
| Prerequisites | `STORYOS-002`; `CANON-004` for obligations; `QUALITY-003` for premise selection |
| Complexity | M + L + S |
| Risks | Replanner drift; over-editing guided milestones |
| Tests | T01, T07, `EXP-REPLAN` |
| Acceptance | Validator rejects the seeded bad roadmaps; replanning never changes a frozen or locked field (property test); every change has a reason and trigger |
| Rollback | `roadmap_history/` keeps every version; `roadmap restore --version K`; flag `USE_ROLLING_PLAN=false` |

### Phase 4 — Advanced narrative intelligence

| | |
|---|---|
| Objectives | Causal scenes, framework variety, character briefs and derived state |
| Tasks | `NARRATIVE-001` (already prototyped — doc 11), `NARRATIVE-002`, `NARRATIVE-003`, `CHAR-001`, `GEN-002` |
| Files | New `story_os/scene_cards.py`, `frameworks.py`, `characters.py`; `story_structure.py`, `script_editor.py`, `show_os/new_show.py` |
| Prerequisites | Phase 0 for `NARRATIVE-001`; phases 1–2 for the rest |
| Complexity | M + M + M + M |
| Risks | Card JSON failures; scene length drift; fallback path masking failures |
| Tests | `tests/test_scene_cards.py` (9 tests, supplied); T02; framework-rotation property test |
| Acceptance | With `USE_SCENE_CARDS=1`, a generated episode has `metadata.outline_mode == "cards"`, every scene prompt after the first contains the previous hand-off, and scene count is no longer fixed at 17 |
| Rollback | Flag off → legacy path, which is untouched |

### Phase 5 — Writers' room and originality

| | |
|---|---|
| Objectives | Lint, editor, bounded revision, pairwise judge, premises, originality metrics, ablation |
| Tasks | `QUALITY-003`, `QUALITY-001`, `QUALITY-004`, `WRITERS-001`, `QUALITY-002`; run `EXP-ABLATE` and `EXP-ORIG` |
| Files | New `story_os/judge.py`, `writers_room.py`, `originality.py`, `metrics.py`; `quality_checker.py`, `story_pipeline_agent.py`, `script_editor.py` |
| Prerequisites | Phase 4 |
| Complexity | S + M + S + M + M |
| Risks | Cost; judge bias; editor flattening voices |
| Tests | T09; judge order-swap test; revision cap test |
| Acceptance | Ablation report written and its decision rules applied; passes that fail them ship disabled |
| Rollback | `USE_WRITERS_ROOM=false`; each pass has its own config switch |

### Phase 6 — Audio-first storytelling

| | |
|---|---|
| Objectives | Sound cues with anchors in scripts; sound identities tied to canon |
| Tasks | `AUDIO-002` (cue parser part), `AUDIO-008`; writer prompt cue syntax (in `NARRATIVE-003`) |
| Files | `story_structure.py` (`_parse_script_lines`), new `audio_timeline.py`, `data/shows/<id>/sound/identities.json` |
| Prerequisites | Phase 1; `AUDIO-005` for assets |
| Complexity | M + M |
| Risks | Models produce malformed cues → tolerant parser with legacy fallback |
| Tests | Cue parser table test (20 forms, incl. legacy parentheticals); identity registry round-trip |
| Acceptance | 100% of cues in a generated script parse to an anchor or are reported; a recurring sound resolves to the same asset hash across two episodes |
| Rollback | Parser falls back to legacy `sound_effect` lines |

### Phase 7 — Modern audio-generation stack

| | |
|---|---|
| Objectives | Provider interfaces; licence gate; benchmark; SFX and music generation |
| Tasks | `AUDIO-006`, `AUDIO-007`; run `EXP-TTS` |
| Files | `tts_engine.py`, `dialogue_engine.py`, `voice_registry.py`, new `audio_providers/` |
| Prerequisites | Phase 0 |
| Complexity | M + M |
| Risks | Dependency conflicts between model runtimes → run each provider in its own process/venv behind a small CLI or HTTP boundary |
| Tests | T10; provider contract tests with a fake engine; licence gate test |
| Acceptance | `Docs/decisions/TTS-BENCHMARK-<date>.md` exists; default engine set by its decision rule; XTTS refuses to run when `publishable=true` |
| Rollback | `engine_order` back to previous value |

### Phase 8 — Production audio engine

| | |
|---|---|
| Objectives | Line cache and alignment; multitrack mix; mastering; QA |
| Tasks | `AUDIO-001`, `AUDIO-002` (resolver), `AUDIO-003`, `AUDIO-004`, `AUDIO-005` |
| Files | New `audio_align.py`, `audio_timeline.py`, `audio_mix.py`, `audio_master.py`, `audio_assets.py`; `audio_pipeline.py`, `audio_qa.py`, `export_timeline.py`, `needed_audio_report.py` |
| Prerequisites | Phase 0 |
| Complexity | M + M + L + M + M |
| Risks | Aligner model licence and accuracy; render time; memory for long episodes (render per scene, then overlap-add) |
| Tests | T11, T12; determinism; legacy mixer must fail T11 assertion 1 |
| Acceptance | T11 and T12 pass; final file −16 ±1 LUFS, ≤ −1 dBTP; one lossy encode |
| Rollback | `USE_TIMELINE_MIXER=false` → legacy `_mix_scene_audio` |

### Phase 9 — End-to-end automation

| | |
|---|---|
| Objectives | `produce-episode`, `produce-season`; resumable jobs |
| Tasks | `AUTO-001` |
| Files | New `story_os/jobs.py`; `cli_entrypoint.py`; `scripts/*.sh` |
| Prerequisites | `NARRATIVE-001`, `AUDIO-003` (can start with legacy stages) |
| Complexity | M |
| Risks | Hash inputs incomplete → stale outputs; mitigated by hashing config and code version |
| Tests | T13 |
| Acceptance | Kill during `write` and during `tts`; rerun completes without regenerating finished scenes or lines (counts asserted) |
| Rollback | Old per-stage commands remain |

### Phase 10 — Branding and publication

| | |
|---|---|
| Objectives | Rights gate; publish assets; host interface; dry run; live publish on explicit request |
| Tasks | `PUB-003`, `PUB-001`, `PUB-002` |
| Files | New `publish/` package; `episode_metadata.py`, `export_timeline.py`, `cli_entrypoint.py` |
| Prerequisites | Phase 8 for exact times; phase 2 for descriptions |
| Complexity | S + M + M |
| Risks | Host API differences; accidental live publish → dry-run default and a second confirmation |
| Tests | T14 |
| Acceptance | Dry run produces a valid feed and request log; `--live` refuses with any unknown licence |
| Rollback | Nothing is sent without `--live`; published episodes are unpublished on the host by the user |

### Phase 11 — Production validation

| | |
|---|---|
| Objectives | Evidence that the whole system holds over a season |
| Tasks | Run T01–T22; produce an 8-episode season of an original serialized show **and** one episode each of a horror anthology, an educational show and a conversational show from one-sentence ideas; run `EXP-ORIG`; human listen-through; record costs |
| Files | `experiments/`, `Docs/decisions/` |
| Prerequisites | All |
| Complexity | M |
| Risks | Cost of a full season; subjective disappointment despite green checks — that is a finding, record it |
| Acceptance | All objective tests pass; zero unpaid season promises; a signed-off listening report |
| Rollback | n/a |

## 3. Suggested order when time is short

1. `BASE-001`, `BASE-002` (half a day).
2. `NARRATIVE-001` — apply the supplied patches; biggest story gain per hour.
2a. `BASE-003` + `GEN-001` — the minimum that makes the tool universal (any idea, no books).
2b. `STORYOS-001` + `GEN-003` — isolation before a second project exists.
3. `AUDIO-001` → `AUDIO-003` — biggest audio gain.
4. `STORYOS-001/002`, then `CANON-001/002`.
5. Everything else in phase order.

## 4. Progress tracking

Cursor maintains `Docs/handoff/PROGRESS.md` in the repository:

```
| Change ID | Status (proposed/in progress/implemented/tested/blocked) | Commit | Tests run → result | Notes / deviations |
```

and one file per decision under `Docs/decisions/` when it departs from this handoff. A change is `tested` only when the commands in its Test procedure were run and their output pasted or summarised.
