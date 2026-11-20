# 04 — Target System Architecture

Everything in this document is **PROPOSED**. It keeps the existing modules and CLI and adds to them; no rewrite.

## 0. Scope: genre-agnostic architecture (universal-scope delta)

A **project** is created from one sentence and has a **production mode**: `serialized_fiction`, `episodic_fiction`, `anthology`, `standalone_drama`, `documentary`, `educational`, `conversational` (or a custom row). The mode maps to capabilities in `MODE_CAPABILITIES` (`reference/reference_models.py`); code reads capabilities, never mode names. Genre (horror, comedy, history …) is free text on the project and steers prompts, framework bias and sound palette.

The nine levels in §2 are the `serialized_fiction` configuration and are unchanged. Other modes use a subset or a counterpart:

| Level | Fiction modes other than serialized | Documentary / educational / conversational |
|---|---|---|
| 1 Identity | Same | Same (hosts instead of an ensemble) |
| 2 Series planner | Optional | — |
| 3 Season director | Slate of premises (no arc), or none | Topic slate or curriculum |
| 4 Episode planner | Same steps, without arc obligations | Same steps over claims and objectives |
| 5 Writers' room | Same | Same loop, factual editorial profile |
| 6 Scene engine | Scene cards | Segment cards |
| 7 Canon memory | Light, per-episode or per-story ledger | Claim ledger with citations |
| 8 Quality | Fiction rules | Factual rules |
| 9 Audio | Same | Same |

Everything is scoped by `project_id` (layout in doc 16 §C2). References are optional, have explicit purposes and rights, and influence writing only through the Creative Reference Control (doc 16 §D).

## 1. Principles

1. **Files stay the storage.** JSON and JSONL under `data/` and `episodes/`, plus one rebuildable SQLite index. No servers.
2. **One source of truth per kind of fact.** Canon lives in the ledger. Plans live in the roadmap. Everything else (character state, Mem0, prompts) is derived and can be deleted and rebuilt.
3. **Nothing enters canon without a quotation.** Every extracted fact cites `line_id`s; Python checks the quote exists.
4. **Published history is immutable.** Corrections are new records that supersede old ones.
5. **Plans are not history.** A roadmap entry never becomes a fact until an episode containing it is approved.
6. **Code decides what can be decided by code.** The LLM writes and judges; Python validates structure, counts, IDs, timing.
7. **Each added LLM pass must earn its place** in an ablation (doc 07 §7).
8. **Every stage is resumable** by content hash.

## 2. The nine levels and where they live

| Level | Responsibility | Object(s) | File(s) | Module(s) | Changes when |
|---|---|---|---|---|---|
| 1 Series identity | Universe, themes, tone, rules, cast profiles, sonic identity | `SeriesIdentity`, `CharacterProfile`, `SoundIdentity` | `data/shows/<id>/series_bible.json`, `characters/C*.json`, `sound/identities.json` | `show_os/new_show.py`, `story_os/store.py` | By explicit `edit-show`; logged |
| 2 Series planner | Candidate multi-season directions; series-horizon promises | `SeriesPlan` | `series_plan.json` | `story_os/roadmap.py` | At season boundaries |
| 3 Season director | Dramatic question, milestones with commitment levels, mystery solutions | `SeasonRoadmap`, `EpisodeMilestone` | `seasons/<N>/roadmap.json` (+ `roadmap_history/`), `mystery_solutions.json` | `show_os/seasons.py`, `story_os/roadmap.py` | After each approved episode (unapproved episodes only) |
| 4 Rolling episode planner | Reads canon + roadmap, generates candidate directions, selects, outlines | `EpisodeOutline`, `SceneCard[]` | `episodes/<ep>/outline.json` | `story_os/episode_planner.py`, `story_os/frameworks.py` | Per episode |
| 5 Writers' room | Draft, edit, revise | script | `episodes/<ep>/script.json`, `drafts/` | `story_structure.py`, `story_os/writers_room.py`, `script_editor.py` | Per episode |
| 6 Scene causal engine | Card validation, hand-offs, causality links | `SceneCard`, `Handoff` | `outline.json`, `handoffs.json` | `story_os/scene_cards.py` | Per scene |
| 7 Canon memory | Events, beliefs, relationships, promises, corrections | `CanonEvent`, `Belief`, `RelationshipDelta`, `NarrativePromise` | `canon/*.jsonl`, `canon/index.sqlite`, `canon/state/` | `story_os/canon_store.py`, `canon_extract.py`, `beliefs.py`, `promises.py` | On extraction (draft) and approval (canon) |
| 8 Quality system | Objective checks, lint, pairwise judging, metrics | reports | `episodes/<ep>/quality/*.json`, `metrics/episodes.jsonl` | `quality_checker.py`, `story_os/judge.py`, `originality.py`, `metrics.py` | Per stage |
| 9 Audio production | Voices, SFX, music, timeline, mix, master, QA | `Timeline`, `TimelineClip` | `episodes/<ep>/audio/timeline.json`, `stems/`, `full_episode.*` | `audio_timeline.py`, `audio_align.py`, `audio_mix.py`, `audio_master.py`, `audio_assets.py`, `audio_providers/` | Per episode; never writes canon |

## 3. Directory layout

```
data/
  active_show.json                      # {"show_id": "..."} — replaces "the global bible is the active show"
  feature_flags.json                    # existing
  llm_config.json                       # new: role → provider/model/temperature
  series/                               # LEGACY, read-only after migration (global bible mirror stays for compatibility)
  shows/<show_id>/
    series_bible.json                   # existing shape + identity fields
    show_state.json                     # existing Show OS shape + episode index
    series_plan.json
    characters/C01.json ...             # CharacterProfile (stable IDs)
    sound/identities.json               # SoundIdentity[]
    seasons/<N>/
      season_plan.json                  # existing; kept as the v1 import source
      roadmap.json                      # SeasonRoadmap, current version
      roadmap_history/v0001.json ...
      mystery_solutions.json            # never included in writer prompts
    canon/
      events.jsonl  beliefs.jsonl  relationships.jsonl  promises.jsonl  corrections.jsonl
      index.sqlite                      # rebuildable from the JSONL files
      state/characters/C01.json ...     # derived CharacterState
    metrics/episodes.jsonl
    publish/feed_state.json
episodes/<episode_id>/
  structure.json  script.json           # existing
  outline.json  handoffs.json           # new
  memories.json                         # existing (legacy extractor output; kept)
  drafts/  pins.json                    # existing
  quality/*.json
  job.json                              # stage state for resume
  audio/
    lines/<line_id>.wav  lines/<line_id>.json   # audio + word timings + content hash
    timeline.json
    stems/dialogue.wav ambience.wav sfx.wav music.wav
    mix.wav  full_episode.m4a|mp3  loudness.json  audio_qa_report.json
  publish/metadata.json transcript.vtt transcript.json chapters.json cover.png
assets/
  library/<sha256>.wav + <sha256>.json  # content-addressed SFX/ambience/music cache with provenance
```

## 4. Data flow for one episode

```
           ┌────────────── Level 1–3: bible · characters · roadmap(vK) · mystery solutions ──────────────┐
           │                                                                                              │
 canon ledger (approved episodes) ──► context assembler ──► ① candidate premises (3) ──► pairwise select  │
           ▲                                │                          │                                  │
           │                                │                          ▼                                  │
           │                                │               ② framework selection                         │
           │                                │                          ▼                                  │
           │                                └────────────► ③ scene cards (one call, ordered)              │
           │                                                           ▼                                  │
           │                                              card validation + cut/merge (Python)            │
           │                                                           ▼                                  │
           │                                    ④ scene writing, sequential: card + previous hand-off     │
           │                                                           ▼                                  │
           │                                    ⑤ hand-off extraction per scene (evidence-cited)          │
           │                                                           ▼                                  │
           │                                    ⑥ lint (Python) → editor pass (different model) → patches │
           │                                                           ▼                                  │
           │                                    ⑦ canon extraction → DRAFT events/beliefs/deltas/promises │
           │                                                           ▼                                  │
           │                                    ⑧ consistency checks vs canon; promise closure judging    │
           │                                                           ▼                                  │
           │                                         HUMAN OR AUTO APPROVAL  (approve-episode)            │
           │                                                           ▼                                  │
           └────────── draft records promoted to CANON ◄───────────────┤                                  │
                                                                       ▼                                  │
                                         ⑨ roadmap replanning of unapproved episodes → roadmap v(K+1) ────┘
                                                                       ▼
                         ⑩ audio: lines → alignment → timeline → stems → mix → master → QA
                                                                       ▼
                         ⑪ publish assets → host upload (dry-run by default) → feed verification
```

Stage ⑩ may run before approval for review listening, but an episode cannot be published unless approved.

## 5. Context assembler (Level 4, steps 1–7 of the brief)

One function builds every planning and writing prompt's context, with a token budget per section, replacing the three independent context paths that exist today (`get_previous_episode_context`, `build_prompt_enrichment`, `arc_slot`).

| Section | Source | Budget (tokens, default) |
|---|---|---|
| Series identity digest | `series_bible.json` | 600 |
| Season: question, opposition, locked commitments | `roadmap.json` | 300 |
| This episode's milestone + next two milestones | `roadmap.json` | 400 |
| Previous episode consequences | canon events of episode N−1 with `consequences` | 500 |
| Relevant older events | SQLite query by participants/locations of this episode, then Mem0 semantic top-k (optional) | 600 |
| Character states for the focus cast | `canon/state/characters` | 150 each |
| Who knows what (only propositions relevant to this episode) | `beliefs.jsonl` via index | 400 |
| Open promises: due, ageing, series-horizon | `promises.jsonl` | 400 |
| Repetition guard: frameworks, openings, ending types, obstacle types used so far | `metrics/episodes.jsonl` | 200 |

`mystery_solutions.json` is included only for the **planner** role, never for the scene writer, so the writer cannot leak it.

## 6. Roles and models

`data/llm_config.json` (new) maps roles to models so that writer and judge can differ on purpose:

```json
{
  "roles": {
    "planner":   {"provider": "openrouter", "model": "<set by user>", "temperature": 0.7},
    "writer":    {"provider": "openrouter", "model": "<set by user>", "temperature": 0.8},
    "editor":    {"provider": "openrouter", "model": "<different family from writer>", "temperature": 0.3},
    "extractor": {"provider": "openrouter", "model": "<cheap, accurate>", "temperature": 0.0},
    "judge_a":   {"provider": "openrouter", "model": "<family A>", "temperature": 0.0},
    "judge_b":   {"provider": "openrouter", "model": "<family B>", "temperature": 0.0}
  },
  "fallback": {"provider": "openai", "model": "<set by user>"}
}
```

Model names are deliberately not prescribed: the right choice changes monthly, and the repository's current literals are already dated. `BASE-002` moves them into this file with today's values as defaults so behaviour is unchanged on day one.

## 7. Approval and immutability

Episode status: `planned → outlined → drafted → approved → published`.

- `drafted`: script exists; extraction produced **draft** records.
- `approved`: `approve-episode <id>` (manual) or auto-approval when all objective checks pass and `auto_approve=true` for the show. Draft records become `canon`. The roadmap is replanned for later episodes.
- `published`: the feed contains it. From here even corrections are additive (`corrections.jsonl`, `status='retconned'`, `superseded_by`).

Editing an approved-but-unpublished script requires `unapprove-episode`, which marks its canon records `draft` again and logs the action.

## 8. Feature flags after the change

Keep `story_os/flags.py`. New behaviour ships behind flags so the legacy path remains runnable for comparison:

| Flag | Default at introduction | Controls |
|---|---|---|
| `USE_STORY_OS` | false → true at end of phase 1 | Unified store and context assembler |
| `USE_SCENE_CARDS` | false → true at end of phase 4 | Sequential card-driven writing |
| `USE_CANON_LEDGER` | false → true at end of phase 2 | Evidence-cited extraction and ledger |
| `USE_ROLLING_PLAN` | false | Replanning after approval |
| `USE_WRITERS_ROOM` | false | Candidate premises + editor pass |
| `USE_TIMELINE_MIXER` | false → true at end of phase 8 | Multitrack mixer replaces concat |
| `USE_AUDIO_QA_BLOCK` | existing | Now also blocks on loudness |
| `USE_DIA2_DIALOGUE`, `USE_BARK_SFX` | **remove** | Dead |

`USE_AGENTIC_PIPELINE`, `USE_SHOW_STATE_DIFF_PROMPTS`, `USE_DIRECTOR_INLINE`, `USE_BIBLE_RAG`, `USE_GENERATION_TRACE` keep their meaning.

## 9. What audio may and may not do

Audio reads the approved script, the sound-design cues on scene cards, and `sound/identities.json`. It writes only under `episodes/<ep>/audio/` and `assets/library/`. If audio needs a text change (a line that cannot be voiced, a cue that cannot be realised), it writes a **change request** to `episodes/<ep>/audio/change_requests.json`; applying one goes through the script editor and re-extraction. Audio never edits `script.json` or the ledger.

## 10. Architecture decision records

| ADR | Decision | Alternatives considered | Why |
|---|---|---|---|
| 001 | `data/shows/<show_id>/` is the single owner of show state; `data/series/<slug>/` is legacy | Keep both; move to series/ | Show OS already holds the richest plan and the only real example; one key (`show_id`) ends the slug mismatch (doc 01 §3B) |
| 002 | Canon is an append-only JSONL ledger with a rebuildable SQLite index | Graphiti; Mem0 only; a relational DB as primary | Human-readable, diffable, git-friendly, no server; SQLite (standard library) gives the temporal and per-character queries; Graphiti needs a graph server and LLM-decided invalidation (doc 02 B1) |
| 003 | Mem0 stays, as a derived semantic index written with `infer=False` | Remove Mem0; make Mem0 primary | Semantic recall of old events is useful; inference mode can rewrite facts (doc 02 B3) |
| 004 | One `SeasonRoadmap` replaces both season plans; structure is validated, not generated from a beat sheet | Keep both; Story OS only | Doc 01 §3A, §4.2 |
| 005 | Commitment levels `locked / guided / open` on milestones; replanning touches only unapproved episodes and never a locked field | Fixed plan; fully emergent | Doc 06 §7 experiment |
| 006 | Scene cards generated together and scenes written sequentially | Keep parallel generation; whole-episode single call | Causality requires order; a single call caps length and makes targeted revision impossible |
| 007 | Framework chosen per episode from a registry | Save the Cat everywhere | Brief requirement; doc 03 §2.1 |
| 008 | Evidence-cited extraction with Python quote verification; single-claim judges for irreversible changes and promise closure | Trust the extractor; keyword heuristics | Measured failure of heuristics (doc 01 §3C); doc 02 A1/A2 |
| 009 | Pairwise, order-swapped, two-family judging for all preference decisions; absolute scores only as lint | Single 0–10 score | Doc 02 A4, A5 |
| 010 | Writers' room is small and ablated: three premises, one editor pass | Many-agent room | Doc 02 A5: decomposition raises repetition and cost |
| 011 | Own multitrack mixer in numpy at 48 kHz stereo, WAV stems, one final encode | Fix the concat mixer; adopt a DAW-like library; pedalboard | Sample-accurate overlap is impossible in a concat; pedalboard is GPL-3 (doc 02 D3) |
| 012 | TTS, SFX and music behind provider interfaces; Kokoro remains default until a benchmark says otherwise; XTTS off for publishable builds | Pick a new default now | No model was auditioned in this research (doc 00); licences (doc 08 §2) |
| 013 | Plain job runner with content-hash stage cache | LangGraph; Celery | Linear pipeline; fewer moving parts (doc 02 B2) |
| 014 | Publish through an RSS host API or a self-generated feed on object storage; Spotify via one-time manual feed submission; dry-run default | Automate Spotify directly | No public Spotify ingest API found (doc 02 Part E) |
| 015 | Franchise-specific text leaves the code and lives in show data | Keep Star Trek prompts | Original fiction is the goal; rights (doc 09 §8) |

### ADRs added by the universal-scope delta

| ADR | Decision | Alternatives considered | Why |
|---|---|---|---|
| 016 | A project layer above shows; every store keyed by `project_id`; sharing is explicit and limited to references | Keep show as the top level; global libraries | Isolation between unrelated podcasts; reference libraries can serve several shows of one project. Refines ADR-001 |
| 017 | Production modes as a capability table read by code | Separate pipelines per format; mode-name conditionals | One pipeline with switches keeps the serialized-fiction design intact and makes new formats a data change |
| 018 | References are optional, purpose-typed and rights-gated; the existing ingestion path is extended, not replaced | A second ingestion system; a single "use books" flag | Doc 16 §A3: every gap is a missing field or filter |
| 019 | Style influence = closed-vocabulary trait profiles, per-trait weights, deterministic blending, band-to-instruction rendering | A percentage or author name in the prompt; free-text style notes | Interpretable, testable, cannot carry names or plot; avoids close imitation requests |
| 020 | Nonfiction uses a claim ledger with verified quotes; contradictory sources are kept as contested, never merged | Reuse the fiction canon ledger; average or pick silently | Different truth model: evidence, not invention |
| 021 | Reference changes never alter approved or published work; purge keeps provenance and cited facts | Cascade deletes | Published history and attribution must survive preference changes |

## 11. Glossary

| Term | Meaning |
|---|---|
| Approved | Episode status after which its extracted records are canon and its text is frozen unless unapproved |
| Arc step | A dated position of a character on their growth direction, with the causing event |
| Belief | One character's stance toward one proposition; may be false |
| Canon | Facts shown in approved episodes, recorded in the ledger with evidence |
| Commitment level | `locked` (must happen as stated), `guided` (intent holds, details may change), `open` (free) |
| Evidence | `episode_id` + `line_id`s + verbatim quote supporting a record |
| Framework | An episode-level structure template (Save the Cat, Story Circle, …) |
| Hand-off | What a finished scene leaves for the next: what changed, what the audience now knows, what is unresolved |
| Horizon | How long a promise is meant to stay open: scene, episode, season, series |
| Ledger | The append-only JSONL files under `canon/` |
| Milestone | What the season needs from one episode |
| Production mode | The format of a project; selects capabilities |
| Project | The isolation unit: one idea, one or more shows, one reference library |
| Promise | A setup the audience was given that requires development or payoff |
| Reference binding | How strongly, on which traits and in which scope one source influences style |
| Reference purpose | Why a source was supplied: techniques, research, world building, adaptation |
| Roadmap | The versioned season plan: question, commitments, milestones, revision log |
| Scene card | Structured plan for a scene: goal, opposition, turn, value shift, hand-off |
| Segment card | Nonfiction counterpart of a scene card: purpose, key points, claims, takeaway |
| Claim | A factual statement with citations and a support level |
| Style profile | Abstract traits (numbers and closed-list values) describing how something is written |
| Sound identity | A named, reusable sound tied to a canon entity |
| Stem | A full-length single-category audio track (dialogue, ambience, SFX, music) |
| Story time | In-world time as an ordinal plus a label |
| Timeline | The list of clips with anchors that the mixer renders |
| Value shift | The change a scene produces in a named value (trust, safety, knowledge, power) |
