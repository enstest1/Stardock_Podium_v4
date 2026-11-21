# Stardock Podium v5: studio workflow and feature map

Run every command as `python main.py <command> ...` from the repo root.
New shows ("projects") live in `data/projects/<project_id>/`. Episodes live in `episodes/<episode_id>/`.
The old Star Trek pipeline (`generate-episode`, `new-show`, ...) still works unchanged. See `Docs/Docs_New/WORKFLOW.md`.

---

## 1. The map

```
 IDEA (one sentence)
   │  create-podcast "<idea>" [--mode ...] [--minutes N] [--produce]
   ▼
 PROJECT  data/projects/<id>/
   ├─ project.json   mode, idea, title            ─┐
   ├─ bible.json     cast (want/need/wound/...),   │  "identity" (designed by the planner model)
   │                 tagline, intro/outro text     │
   ├─ format.json    length, intro/outro, theme   ─┘
   ├─ voices.json    who speaks with which voice (+fx, +speed)
   ├─ characters/    one profile per cast member (arc steps)
   ├─ seasons/       season roadmap (locked / guided / open milestones)
   ├─ canon/         append-only ledger of story facts
   ├─ refs/          your reference material (+ research claims)
   ├─ music/         show theme (intro/outro)
   ├─ sound/         identities.json (recurring sounds), mix.json (dial-in)
   └─ metrics/       framework history, quality/originality
   │
   │  produce-episode <project> [--theme "..."]           (resumable job)
   ▼
 EPISODE  episodes/<ep_id>/
   cast ─► outline ─► script ─► edit ─► lint ─► extract ─► audio
    │        │          │        │       │        │          │
    │        │          │        │       │        │          └ timeline mixer → mix.wav → master (−16 LUFS)
    │        │          │        │       │        └ canon facts, quote-verified (draft until approved)
    │        │          │        │       └ rule checks (speech in cues, canon contradictions, ...)
    │        │          │        └ writers room: editor patches (only with USE_WRITERS_ROOM=1)
    │        │          └ scene by scene, each scene sees the previous one + character briefs
    │        └ scene cards (fiction) / segment cards (nonfiction), story framework picked per episode
    └ voices from the catalog (designs new Kokoro blends if needed)
   │
   ▼
 LISTEN  episodes/<ep_id>/audio/full_episode.mp3
   │  dialin-samples / sound-settings / recast-project   (tune, re-render cheaply)
   │  approve-episode                                    (canon becomes official, season replans)
   ▼
 PUBLISH  rights-report → publish (dry run: feed, transcript, chapters, cover)
```

---

## 2. Everyday recipes

**Make a new show and its first episode**
```
python main.py create-podcast "a night-shift radio host takes calls from people in other years" --minutes 5 --produce
```
This proposes a mode, title, cast, voices, theme and season plan, then writes and renders episode 1.
Add `--no-audio` to read the script before rendering.

**Next episode of the same show**
```
python main.py produce-episode static_at_mesquite_flats
python main.py produce-episode static_at_mesquite_flats --theme "the caller from 1962 asks for Owen by name"
```

**Something failed or you edited the script by hand**
```
python main.py produce-episode <project> --resume <ep_id>              # skip finished stages
python main.py produce-episode <project> --resume <ep_id> --force audio  # redo audio only
python main.py write-and-render <ep_id>                                # script from saved cards, then audio
```
Line audio is cached. A re-render only re-synthesises lines whose text, voice or speed changed.

**Better writing (costs about 2-3× the model calls)**
Set `USE_WRITERS_ROOM=1` for the run: `$env:USE_WRITERS_ROOM=1` in PowerShell, `USE_WRITERS_ROOM=1 python main.py ...` in bash.
This does three things: picks the best of 3 premises with a pairwise judge, runs an editor round (it may rewrite up to 30% of lines), and records originality metrics.

**Finish an episode**
```
python main.py lint-episode <ep_id>       # problems list
python main.py canon-show <ep_id>         # what the episode established
python main.py approve-episode <ep_id>    # facts → canon, season plan adjusts
python main.py roadmap-show <project>     # where the season is heading
```

---

## 3. Dialling in the sound (new)

```
python main.py dialin-samples <ep_id>           # ~8 min, no API cost
```
This writes `episodes/<ep_id>/dialin/` with a `README.md`. Each group is the same excerpt rendered with every option:

| Group | Options | What changes |
|---|---|---|
| A mix | balanced · intimate · cinematic · dry | how loud the ambience/SFX/music beds are and how much they dip under voices |
| B pacing | tight · natural · relaxed | pauses between lines and scenes |
| C phone voice | phone_light · phone · phone_old · radio | the filter applied to callers / `fx: phone` lines |
| D loudness | −19 · −16 · −14 LUFS | overall loudness (−16 is the podcast norm, −14 matches Spotify/YouTube) |
| E voices | current voice at 0.92 / 1.0 / 1.08 speed + 4 alternatives per lead | voice choice and speaking rate |

Save your picks for the show. They apply to every future render of that project:
```
python main.py sound-settings <project> --mix intimate --pacing tight --phone phone_old --loudness -16
python main.py sound-settings <project> --speed della=0.95,owen=0.92
python main.py sound-settings <project> --voice margaret=kokoro:af_nova
python main.py produce-episode <project> --resume <ep_id> --force audio
```
The settings are stored in `data/projects/<id>/sound/mix.json`, and speed and voice in `voices.json`.

---

## 4. Voices

| Command | Use |
|---|---|
| `voice-catalog [--refresh] [--source preset\|designed\|sample]` | every voice, who uses it, whether it may be auto-cast |
| `design-voice <name> --recipe af_river:0.5,af_kore:0.3,af_nicole:0.2 --audition "line"` | blend presets into a new voice (Apache-2.0, publishable) |
| `audition-voice <voice_id> --text "..."` | hear any catalog voice |
| `recast-project <project>` | re-cast the whole show (avoids voices other shows use) |
| `sound-settings <project> --voice / --speed` | change one character |

Your cloned samples (`voices/samples/`) are catalogued as private. They are never auto-cast and never pushed to GitHub.

## 5. Theme music and intros

| Command | Use |
|---|---|
| `make-intro <project>` | ElevenLabs Music from the show's `theme_prompt`. Needs a paid ElevenLabs plan; on the free plan you get a clear refusal |
| `make-intro <project> --intro-file theme.mp3 --provider suno [--commercial]` | use a track you made on Suno (or anywhere). `--commercial` records that you hold the rights |
| `make-intro <project> --prompt "..." --regenerate` | new brief / replace the theme |

The intro and outro text are spoken by the show's narrator over the theme. The outro always carries the AI disclosure.

## 6. Shows that aren't fiction

Use `--mode documentary | educational | conversational` (or let the planner pick). These modes use **segment cards** instead of scene cards, plus research:
```
python main.py reference-add <project> notes.md --purpose factual_research --rights owned
python main.py claims-list <project>                     # extracted claims, support level, conflicts
python main.py reference-add <project> novel.txt --purpose writing_techniques --rights licensed
python main.py reference-bind <project> SRC-xxxx --influence 0.4 --traits pacing:1,tone:1
python main.py reference-set <project> SRC-xxxx disable|enable|remove|purge
```
Scripts cite claims internally (`[[CL-xxxx]]`). The markers are stripped before audio, and unsupported claims are flagged.

## 7. Seasons and continuity

- `plan-project-season <project> --episodes 8 --direction "..."` makes a roadmap. Locked milestones (inciting, midpoint, climax) never move. Guided and open milestones can be re-planned.
- Each episode gets its milestone, a continuity brief from canon (who knows what, open promises) and a framework choice. The framework is one of 10 fiction structures, and it isn't repeated back to back.
- `approve-episode` commits canon and re-plans the remaining open episodes. Use `--no-replan` to keep the plan.

## 8. Publishing

| Step | Command | Notes |
|---|---|---|
| Check rights | `rights-report <ep_id>` | lists every engine, voice, sound and track with its licence |
| Package (dry run) | `publish <ep_id>` | writes `publish/` with the transcript (VTT), chapters, description, cover and RSS feed. Nothing leaves your machine |
| Go live | `publish <ep_id> --live --i-authorise-publication` | blocked until the rights gate passes **and** a host adapter exists (not built yet) |

**Sharing it yourself is fine**: `full_episode.mp3` is a normal tagged MP3. Before posting it publicly or monetising it, clear the two blockers:
1. Swap the bundled theme for your own track: `make-intro <project> --intro-file ... --commercial`.
2. Free-tier ElevenLabs sound effects are non-commercial and need a credit. Either credit them, upgrade, or regenerate on a paid plan.

## 9. Switches (data/feature_flags.json or environment)

| Flag | Default | Effect |
|---|---|---|
| `USE_WRITERS_ROOM` | off | premise contest, editor round, originality metrics |
| `USE_SCENE_CARDS`, `USE_TIMELINE_MIXER` | off | turn the v5 outline/mixer on for the *legacy* show (projects always use them) |
| `STARDOCK_SFX_GENERATE=0` | on | don't generate missing sounds (library only) |

Models are set per role in `data/llm_config.json`: planner/writer use Opus 5.5, editor/extractor/judge use Sonnet 5.5, and the fallback is GPT-4.1. Delete that file to go back to the legacy models.

## 10. Safety nets

- Git: tag `v4-pre-upgrade` and branch `stable/v4-pre-upgrade` are the pre-upgrade code. The v5 work is on `feature/upgrade-v5`.
- `migrate-shows --dry-run` / `--rollback <manifest>` for the legacy show data.
- Every production stage is a resumable job (`episodes/<id>/job.json`). Inputs are hashed, so only changed stages re-run.

## 11. Not built yet / needs a decision

- Live host upload (pick a host such as Transistor or Buzzsprout, plus an API key).
- Commercial music/SFX (paid ElevenLabs, or Suno-made themes; the Suno API is invite-only).
- TTS benchmark against other engines, ablation/originality experiments (cost approval).
- Word-accurate forced alignment (aligner licence choice).
- PDF/DOCX references (`pip install pypdf python-docx`).
- Trend research bot (later idea).
