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
| BASE-003 | partial | 061c112 | covered by `test_projects.py` | `FormatProfile` (`story_os/profile.py`) used by project episodes. Legacy prompts untouched (no migrate-shows yet), so the franchise grep is **not** clean yet |
| GEN-001 | tested (fiction modes) | 061c112, a20813b, d61cefa | `pytest tests -q` → 37 passed; real run below | `create-podcast`, `produce-episode`, `list-projects`. Nonfiction modes stop with a clear GEN-002 message. Project episodes skip global bible, book RAG, legacy Mem0 extraction (isolation until GEN-003) |

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
