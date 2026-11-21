# Upgrade progress (v4 → v5)

Fallback point: tag `v4-pre-upgrade` and branch `stable/v4-pre-upgrade` (commit `3cb9576`), pushed to GitHub.
Local backup of untracked runtime data (episodes, voices, books, .env): `Desktop/stardock_backups/stardock_podium_04_pre-upgrade_2026-11-20.tar.gz`.
All upgrade work is on branch `feature/upgrade-v5`, one commit per change ID.

Handoff was written against `c32a965`; HEAD at start was `3cb9576` (one checkpoint commit: pronunciation/pipeline WIP). No cited function had moved.
Environment: Windows 10, Python 3.11.5, pydantic 2.10.6, openai 1.79.0, ffmpeg (choco), RTX 3070 Laptop, Kokoro installed.

| Change ID | Status | Commit | Tests run → result | Notes / deviations |
|---|---|---|---|---|
| baseline | — | 3cb9576 | `pytest tests -q` → 6 failed, 6 passed | Matches audit (one stale mock) |
| BASE-001 | tested | 6763a9e | `pytest tests -q` → 12 passed | Patch file not supplied; applied the spec's verified snippet by hand |
| BASE-002 | tested | 099c89f | `pytest tests -q` → 18 passed; model grep clean except `mem0_client.py:88` | `mem0_client` keeps its own Mem0-internal LLM config (CANON-005 scope). `data/llm_config.json` added pointing roles to Claude Opus 5.5 / Sonnet 5.5; delete it to get the legacy models back. StoryStructure passes its own clients to `llm.complete` so existing test patches still apply |
| NARRATIVE-001 | tested | 52630d2 | `pytest tests/test_scene_cards.py` → 9 passed; suite → 27 passed | `reference/scene_cards.py`, its tests and the patch were not in the handoff folder; written from the spec text. Added a per-scene word target on the card path |
| BASE-003 | tested | 061c112, c2da6e1 | `test_golden_legacy.py` 4 passed (prompts + TTS byte-identical; franchise grep empty) | Franchise wording moved to `data/shows/legacy_format.json` + `legacy_lexicon.json`; `normalize_tts_text` generic with per-show lexicon. Old name `normalize_trek_tts_text` NOT kept as alias (only caller updated; alias would fail the grep) |
| GEN-001 | tested | 061c112, a20813b, d61cefa | real runs below | `create-podcast`, `produce-episode`, `list-projects`; all modes now (GEN-002) |
| AUDIO-006 (voices) | tested | 6214476 | `test_voice_catalog.py` | `voices/catalog.json`, LLM casting, designed Kokoro blends in `voices/designed/`. Clone samples private-only (user decision). Provider registry / TTS benchmark (EXP-TTS) **not run** |
| AUDIO-007 | tested | 6214476, 1ad3691 | `test_voice_catalog.py`, `test_audio_engine.py` | ElevenLabs Music (`/v1/music`) refused on free plan (verified, HTTP 402 paid_plan_required); theme import for Suno-made tracks; ElevenLabs SFX generation works on free tier (non-commercial, recorded) |
| AUDIO-001..005 | tested | 1ad3691 | `test_audio_engine.py` 18 passed; real render −16.3 LUFS / −1.7 dBTP | Alignment is proportional only (aligner model licence needs user approval, per master prompt) |
| AUDIO-008 | implemented | 3da10cc | covered indirectly | per-show `sound/identities.json` |
| CANON-001..005 | tested | c0bd123 | `test_canon.py` 8 passed; real extraction 17 events / 55 beliefs / 12 promises, 1 rejected | Schemas ours (doc 05 and `reference/canon_models.py` not supplied). Omniscience check is a deterministic heuristic, not the LLM check |
| STORYOS-002/003, PLAN-001..003 | tested | 5efa9c7 | `test_roadmap.py` 7 passed incl. 60-trial frozen/locked property test | EXP-REPLAN not run |
| NARRATIVE-002/003, CHAR-001 | tested | 6b236bd | `test_narrative.py` 5 passed | Ten fiction frameworks are ours (doc 03 not supplied) |
| QUALITY-001..004, WRITERS-001 | tested | 49a6c59 | `test_quality.py` 7 passed | `USE_WRITERS_ROOM` default false; EXP-ABLATE / EXP-ORIG **not run**; originality thresholds uncalibrated |
| AUTO-001 | tested | 3da10cc | `test_jobs.py` 3 passed (T13 scene resume) | |
| REF-001..005, GEN-002 | tested | 13dbff8 | `test_references.py` 5 passed | pdf/docx loaders need `pypdf` / `python-docx` (not added) |
| GEN-003 | tested | 412285a | `test_isolation.py` 4 passed | client bound with `for_project`; legacy bound to old names |
| STORYOS-001 | tested | c2da6e1 | `test_migrate_shows.py` 2 passed; real migration run, 2nd dry-run "nothing to do" | Deviation: legacy episodes get `show_id`, not `project_id` (keeps golden prompts) |
| PUB-001..003 | tested | 2ed927d | `test_publish.py` 5 passed; real dry-run feed parses | No live host adapter (Transistor) — needs its API docs + key |

## Log

### 2026-11-20
Set up fallback (tag + branch + local archive). Phase 0 items BASE-001/002, NARRATIVE-001 pulled forward, and a minimal GEN-001 so one sentence produces an original episode end-to-end (cards → sequential script → Kokoro audio with per-project voices and intro/outro). Next: STORYOS-001 + migrate-shows (legacy show gets a `format` profile, then BASE-003 grep can go clean), GEN-003 isolation, AUDIO-001→003 timeline mixer, GEN-002 for nonfiction.

### 2026-11-20 — first real end-to-end run
`create-podcast "<baker / missing sister idea>" --minutes 3 --produce` → project `the_proofing_hour` (mode serialized_fiction, proposed), episode `ep_10a858f7` "The Brass Slot at Midnight".
- Scene cards: 5 cards accepted on attempt 1 (Claude Opus 5.5), every card causally linked; `metadata.outline_mode == "cards"`.
- Script: 93 lines, 417 spoken words, 0 empty scenes. Audio: 70/70 spoken lines rendered with per-project Kokoro voices; full_episode.mp3 = 3:22, −20.1 LUFS integrated, +0.4 dBFS peak.
- LLM cost of the successful stages ≈ 11 Opus 5.5 calls, ~15k prompt / ~12k completion tokens (≈ $0.30).

Problems found and fixed during the run:
1. Provider failover only on missing key → now fails over on any final error; no retries on 400/401/402/403/404 or `insufficient_quota` 429.
2. Opus 5.5 on OpenRouter has mandatory reasoning that counts against `max_tokens` → empty answers. Added `reasoning_headroom` per role and an automatic bigger-budget retry on empty `finish=length` answers.
3. Runner continued to audio with an empty script → now stops; `write-and-render <episode_id>` resumes from saved cards.
4. First use of a Kokoro voice downloads it; a connection reset dropped 2 lines → transient network retry in `dialogue_engine`.
5. "MRS. X" speaker tags → honorific aliases in project voices.

Known gaps (not fixed, by design of scope): all 23 SFX cues + ambiences unresolved (46 items in needed_audio_assets.json; AUDIO-005/007); peak above 0 dBFS and no loudness target (AUDIO-003/004); theme music is the existing sci-fi theme for every show; nonfiction modes blocked (GEN-002); legacy show prompts still contain franchise text (needs STORYOS-001 migrate-shows); project isolation of Mem0 not built (GEN-003) — project episodes simply skip Mem0.

### 2026-11-20 — full roadmap pass + showcase
All change IDs implemented on `feature/upgrade-v5` (see table). Suite: 115 passed.
Showcase: `create-podcast "<late-night call-in radio show; callers from other years; one has the host's voice>" --minutes 5 --produce` with `USE_WRITERS_ROOM=1`
→ project `static_at_mesquite_flats` "Static at Mesquite Flats", episode `ep_cb2f5351` "1340 After Midnight".
- Season roadmap: 6 episodes, 3 locked (inciting / midpoint / climax). Premise chosen from 3 by the pairwise judge. Framework `mystery_fairplay` (rule match). 5 cards accepted first try.
- Voices: 3 newly designed Kokoro blends (host, engineer, narrator) + 2 presets for callers with telephone fx.
- Script 586 words; editor returned 0 patches; lint 0 errors / 0 warnings; originality: no flags.
- Canon: 22 events, 4 state changes, 74 beliefs, 11 promises (4 rejected by quote check).
- Audio 4:49, −16.36 LUFS / −1.64 dBTP, 54/54 lines, 33 cues (ElevenLabs SFX, free tier), 1 cue reported missing.
- Found and fixed during the run: speech written inside SFX cues (now voiced as dialogue + `speech_in_cue` lint). Resume re-rendered only 2 lines (52 from cache).
- Rights gate: BLOCKED (free-tier SFX are non-commercial; bundled theme licence unknown) — correct.

Not done / needs the user: TTS benchmark (EXP-TTS), ablation and originality experiments (EXP-ABLATE, EXP-ORIG, EXP-LONG; cost approval), live host adapter (host choice + API key), commercial music/SFX (paid ElevenLabs plan or Suno-made themes via `make-intro --intro-file`), forced aligner (licence choice), pypdf/python-docx for PDF/DOCX references.

### 2026-11-21 — dial-in controls
Added per-show sound settings (`sound/mix.json`: mix preset balanced/intimate/cinematic/dry, pacing tight/natural/relaxed, phone style phone_light/phone/phone_old/radio, loudness target), per-voice Kokoro speed (in the line-cache key only when not 1.0, so existing caches stay valid), `set_voice`, CLI `dialin-samples` + `sound-settings`. Sample pack rendered for `ep_cb2f5351` (14 excerpts + 28 voice auditions, all within 0.4 LU of target). Fixed: a second `plan-season` registration had shadowed the legacy command; the project one is now `plan-project-season`. Suite: 119 passed. User-facing map: `Docs/STUDIO_WORKFLOW.md`.

