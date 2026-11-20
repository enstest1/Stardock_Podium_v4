# 13 — Migration, Deployment and Rollback

**PROPOSED.** Nothing here has been executed against real user data.

## 1. Ground rules

1. Every migration has a `--dry-run` that writes nothing and a manifest-based rollback.
2. Migrations are idempotent: a second run reports "nothing to do".
3. Originals are never deleted. Legacy locations become read-only fall-backs.
4. Every new behaviour has a flag; turning the flag off is the first rollback step, before any `git revert`.
5. Back up before the first migration: `data/`, `episodes/`, `voices/`, `assets/` → one dated archive outside the repository.
6. One change per branch and pull request; the suite must be green before merge.

## 2. What existing data becomes

| Existing | After migration | Reader behaviour if not migrated |
|---|---|---|
| `data/series/series_bible.json` (global) | Mirror of the active show's bible; `data/active_show.json` names the show | Used as today |
| `data/shows/<id>/series_bible.json` | Gains `character_id` per cast member and `show_profile` | Cast gets IDs lazily in memory; default profile |
| `data/shows/<id>/show_state.json` | Unchanged keys; `episodes_produced` maintained; `legacy_story_os` block if merged | Unchanged |
| `data/shows/<id>/seasons/<N>/season_plan.json` | Kept; `roadmap.json` v1 imported beside it | Read directly |
| `data/series/<slug>/…` | Left in place; indexed in `data/shows/index.json`; copies under `seasons/legacy/` | Read as fall-back |
| `episodes/<id>/structure.json` | Gains `show_id`, `season_number`; permanent-cast IDs rewritten (old kept as `legacy_character_id`) | Resolved through slug index / active show |
| `episodes/<id>/script.json` | Unchanged; line IDs preserved | — |
| `episodes/<id>/memories.json` | Unchanged; still written in the same shape | — |
| Mem0 contents | Untouched; new writes use `infer=False` | — |
| `voices/voice_config.json` | Entries gain `voice_id`; `engine_order` default `["kokoro"]`; XTTS entries flagged non-publishable | Works as today |
| `assets/sound_effects`, `ambience`, `music` | Ingested into `assets/library/` with `license: unknown`; originals stay | Legacy mixer reads originals |
| `data/feature_flags.json` | Two dead flags removed; new flags added, all `false` | Missing flags default to `false` |

## 2a. Universal-scope additions (delta)

| Existing | After migration | If not migrated |
|---|---|---|
| Each show folder | One project per show (`data/projects/<show_id>/project.json`, `mode: serialized_fiction`); `project_id` written into the bible and episodes | Treated as a project with the same ID and the serialized-fiction mode |
| `books/<book_id>/`, `analysis/` | Registered by `reference import-legacy --project <id>` as legacy references (purposes `writing_techniques` + `world_building`, rights `unspecified`) of the legacy project only | Not visible to any other project; never used by new projects |
| Mem0 namespaces `reference_materials`, `episodes`, `characters` | Read only by the project flagged `legacy_namespace: true`; new writes go to `<project_id>:<kind>` | Same |
| `voices/voice_config.json` | Copied to `data/shows/<legacy show>/voices.json`; global file kept as fallback for that show | Same |
| `data/series/style_profile.json` (free text) | Kept for the legacy project; new projects use `style_baseline.json` + bindings | — |
| `data/metadata` series/tag registries (`episode_metadata.py`) | Entries gain `project_id` | Read as legacy |

Order: `migrate-shows` (creates projects) → `reference import-legacy` → tests T15, T18, T20. Rollback: the same manifest restores everything; `data/projects/` can be deleted, since nothing published depends on it until an episode is approved under a project. New flag roll-out rows are not needed: projects, modes and references are structural and have no legacy alternative, but the legacy project keeps its old behaviour through its migrated configuration.

## 3. Migration procedures

### M1 — Shows and IDs (`STORYOS-001`, `BASE-003`, `STORYOS-002`)

```bash
python main.py migrate-shows --dry-run            # read the plan
python main.py migrate-shows                      # writes backups/migrate-<ts>.tar.gz and a manifest
python main.py roadmap import --show <id> --season 1
python main.py migrate-shows --dry-run            # must print: nothing to do
STARDOCK_DISABLE_MEM0=1 python -m pytest tests -q
```

Checks after M1: the golden prompt test passes (legacy episode produces byte-identical prompts); `list-shows` shows each show once; `roadmap show` lists the imported milestones.

Rollback: `python main.py migrate-shows --rollback backups/migrate-<ts>.manifest.json`.

### M2 — Canon backfill (`CANON-002`) — optional

```bash
python main.py canon backfill --show <id> --episode <episode_id>     # draft records + report
python main.py canon show --episode <episode_id> --status draft      # review
python main.py approve-episode <episode_id>                           # promote to canon
```

Backfill costs LLM calls (one per scene). Skip it for episodes that will not be continued. For the committed Star Trek show, backfill is only useful as a test; the show cannot be published.

Rollback: `python main.py unapprove-episode <id>`; or delete `data/shows/<id>/canon/` (derived from scripts; can be regenerated).

### M3 — Voices (`AUDIO-006`)

```bash
python main.py voices migrate --dry-run
python main.py voices migrate
python main.py doctor                   # existing command (voice/engine health); extend it to list clones without consent records
```

Rollback: restore `voices/voice_config.json` from the backup.

### M4 — Assets (`AUDIO-005`)

```bash
python main.py assets ingest --legacy --dry-run
python main.py assets ingest --legacy
python main.py assets rights            # lists unknown licences to resolve before publishing
```

Rollback: delete `assets/library/`.

### M5 — Profiles (`CHAR-001`) — interactive

```bash
python main.py character enrich --show <id> --all     # proposes want/need/wound/…; nothing saved until accepted
```

## 4. Flag roll-out order

| Step | Turn on | After | Verify | Turn off if |
|---|---|---|---|---|
| 1 | `USE_SCENE_CARDS` | `NARRATIVE-001` | T02 criteria on one episode; human read | Card JSON fails on more than 1 in 5 attempts with the chosen model |
| 2 | `USE_STORY_OS` | Phase 1 | Golden prompt tests; two-show isolation test | Any legacy episode fails to load |
| 3 | `USE_CANON_LEDGER` | `CANON-002` | T03–T05 | Extraction reject rate above 30% or cost unacceptable |
| 4 | `USE_ROLLING_PLAN` | `PLAN-002` | T07 | Replanner proposes changes on empty deltas |
| 5 | `USE_WRITERS_ROOM` | Phase 5 + `EXP-ABLATE` | Ablation decision | Ablation says the passes do not pay |
| 6 | `USE_TIMELINE_MIXER` | Phase 8 | T11, T12; listen | Any blocking QA finding that the legacy mixer does not have |
| 7 | `USE_AUDIO_QA_BLOCK` | `AUDIO-004` | T12 | — |

Flags can be set per run by environment variable (`USE_SCENE_CARDS=1 python main.py …`), which is the safe way to trial one.

## 5. Deployment

### 5.1 Local Windows (default)

1. Python 3.10+ in a virtual environment; `pip install -r requirements.txt`; ffmpeg on `PATH` (as today).
2. Optional audio extras: `pip install -r requirements-audio.txt` *(new: numpy, scipy, soundfile, pyloudnorm, aligner)*.
3. `.env`: `OPENROUTER_API_KEY` or `OPENAI_API_KEY`; optional `MEM0_API_KEY`; `STARDOCK_DISABLE_XTTS=1` for publishable work.
4. Model runtimes that conflict with the main environment live in their own virtual environments and are called as worker processes (`AUDIO-006`).
5. File locking for the ledger uses `msvcrt` on Windows; test T04 on Windows specifically.
6. Paths: keep the project on a local disk, not a synced cloud folder (atomic replace and locks behave badly there) — **INFERENCE**.

### 5.2 RunPod GPU worker (optional)

- Use the existing scripts as the base. Persistent volume holds `voices/`, `assets/library/`, model caches (`HF_HOME`).
- Send only stage inputs (`script.json`, voice config, cue list); fetch only stage outputs (`audio/lines/`, new library assets). Content hashes make repeated syncs cheap.
- Shut the pod down from the script when the stage completes.
- Verify on the pod, before a long render: `python main.py doctor`, a 3-line smoke render, and `job status`.

### 5.3 Scheduler host (optional, later)

A container that runs `produce-season --resume` on a timer with `STARDOCK_*_DIR` pointing at a mounted volume or synced object storage. Requirements: the same Python environment without GPU packages; secrets as environment variables; a notification (e-mail or webhook) when a job stops at a human gate. Not needed for manual or weekly-by-hand production.

### 5.4 Deployment verification checklist

- [ ] `python main.py --help` lists the new commands.
- [ ] Suite green on the target machine.
- [ ] `python main.py llm-config --check` reaches each configured role (one-token call).
- [ ] `produce-episode` on the fixture show with a stub or cheap model completes; `job status` all `done`.
- [ ] Interrupt and resume once (T13 by hand).
- [ ] Audio fixture renders; T11/T12 pass.
- [ ] `publish` dry run produces a feed; `verify-distribution --dry-run` passes.
- [ ] Rights report shows no unknowns for the show you intend to publish.

## 6. Rollback matrix

| Change | Fast rollback | Full rollback | Data to clean |
|---|---|---|---|
| BASE-001 | — | `git revert` | None |
| BASE-002 | Delete `data/llm_config.json` (defaults = old models) | Revert | None |
| BASE-003 | Use the migrated legacy profile | Revert | Profile block is harmless |
| STORYOS-001 | — | `migrate-shows --rollback`, revert | Manifest-listed files |
| STORYOS-002 | Delete `roadmap.json` (falls back to `season_plan.json`) | Revert | `roadmap_history/` |
| STORYOS-003 | New flags off | Revert | None |
| CANON-001…005 | `USE_CANON_LEDGER=false` | Revert | `canon/` (optional) |
| PLAN-001/002 | `USE_ROLLING_PLAN=false`; `roadmap restore --version K` | Revert | — |
| NARRATIVE-001 | `USE_SCENE_CARDS=false` | `git apply -R` patch; delete two files | Re-outline affected episodes if desired |
| NARRATIVE-002/003, CHAR-001 | Config switches | Revert | `characters/` optional |
| QUALITY-*, WRITERS-001 | `USE_WRITERS_ROOM=false` | Revert | `quality/` reports |
| AUDIO-001…005 | `USE_TIMELINE_MIXER=false` | Revert | `audio/lines`, `stems`, `assets/library` |
| AUDIO-006 | Restore `engine_order` | Revert | — |
| AUDIO-007/008 | Remove provider config | Revert | Generated assets |
| AUTO-001 | Use per-stage commands | Revert | `job.json` |
| PUB-* | Do not pass `--live` | Revert | Host-side: unpublish by hand |

A published episode cannot be rolled back by code. Unpublish on the host; the GUID must never be reused for different audio.

## 7. Versioning

- `schema_version` on every ledger record and on `roadmap.json`, `job.json`, `timeline.json`.
- `pipeline_version` in `job.json` participates in stage hashes, so a pipeline change invalidates caches deliberately.
- A reader that meets a higher schema version than it knows stops with a clear error; it never guesses.
- Record in `Docs/handoff/PROGRESS.md` the repository commit at which each migration was run.
