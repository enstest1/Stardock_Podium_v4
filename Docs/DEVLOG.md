# Devlog — audio / RunPod / TTS (April 2026)

Session notes: what shipped, how to operate it, and what is still open.

---

## Done (merged to `main`)

### Trek-aware TTS (Kokoro)
- Added `tts_pronunciation.py`: expands **stardates** to spoken digit form (avoids “eight thousand…” style readings); **lexicon** respellings for Bajoran/Bajorian, Cardassian, Romulan, Vulcan, Klingon, Ferengi, Betazoid (extend `_LEXICON` as needed).
- `tts_engine.py` runs all Kokoro input through `normalize_trek_tts_text()` before the existing Kokoro cleanup.

### Intro / outro / themes (`audio_pipeline.py`)
- Intro copy uses **Stardate** from `structure.json` → `stardate` field, else first match in `script.json`, else synthetic `52{episode_number:03d}.1`.
- **Intro layout**: theme ~60s (env `STARDOCK_INTRO_MUSIC_SEC`), narrator delayed ~45s (`STARDOCK_INTRO_NARRATION_START_SEC`), mix with `amix` (music-first, OG-style tail).
- **Theme selection**: prefers `assets/music/Cosmic_Odyssey_Main_Theme_2025-12-25T222447.wav` (intro) and `...2025-12-27T064552.wav` (outro); override with `STARDOCK_INTRO_MUSIC` / `STARDOCK_OUTRO_MUSIC`.
- **Outro**: theme trim as **PCM WAV** (not MP3 intermediate); mix uses **`ffmpeg` subprocess** for `pan` + `amix` because ffmpeg-python mangled `pan=stereo|c0=c0`.
- Intro/outro narrator gate accepts **`kokoro_voice` or `speaker_wav`** (Kokoro still uses `kokoro_voice`).

### Voices (`voices/voice_config.json`)
- `lieutenant_zhanil_thkethris` → `lt_zhanil_thkethris_1.wav` (sample path; Kokoro timbre still from `kokoro_voice`).
- Narrator entry notes that **`narrator.wav` is casting reference only** until a clone-capable engine is wired.

### Voice samples vs what you hear (read this)
- Files under **`voices/samples/Star_Trek_Horizon/*.wav`** (captain, Tevan, narrator, etc.) are **not** fed into Kokoro as cloning references in the current code.
- **Every** role (including narrator) speaks with the **`kokoro_voice`** preset in `voice_config.json`. Cast sounds *different from each other* because **presets differ** (`af_bella`, `am_michael`, `bm_george`, …), not because the engine copies each WAV.
- **`speaker_wav`** is for documentation, validation, and a **future** clone-capable path (XTTS / F5 / API). Treat samples as **casting targets**, not drivers of Kokoro output.

### RunPod / SSH
- `scripts/gitbash_run_all_runpod.sh`: requires **TCP SSH** (`root@IP -p PORT`); RunPod **`ssh.runpod.io` proxy** does not support `scp` or `ssh host "cmd"`. Uses `StrictHostKeyChecking=accept-new` for first connect.
- `scripts/fetch_full_episode_from_runpod.sh`: pulls `full_episode.mp3` down after render.

### CLI
- **`reassemble-audio <episode_id>`**: rebuilds **outro** + **`full_episode.mp3`** from existing `scene_XX/scene_audio.mp3` (no scene dialogue re-synth).
- **`reassemble-audio <episode_id> --refresh-intro`**: also deletes and rebuilds **`intro_complete.mp3`** (new intro narration + theme mux with current code).

### Bugfixes
- `outro_file.parent.mkdir(..., exist_ok=True)` (removed duplicate `parents=` kwarg).
- Outro mux: resample / layout alignment + direct ffmpeg for final mix.

### Known bug — intro: music plays, narrator not audible over tail
- **Symptom:** Theme plays, but the narrator does **not** clearly come in over the **last portion** (expected: voiceover on top of fading theme, OG Trek style).
- **Where:** `_create_intro_segment` in `audio_pipeline.py` — `amix` of delayed narration + ducked music (ffmpeg-python: `adelay`, `afade`, `normalize=0`).
- **Likely directions to fix:**
  - Verify **`adelay`** for mono on FFmpeg 6 (ffmpeg-python may pass ms incorrectly; compare with a **direct `ffmpeg` CLI** mix, same as outro `pan` fix).
  - **Levels:** with `normalize=0`, music may drown voice; raise narration gain or duck music further under the overlap.
  - **Theme length vs `STARDOCK_INTRO_MUSIC_SEC`:** short assets (e.g. 30 s) vs 60 s target can make `atrim` / pad / mix behave oddly; align duration or pad explicitly.
  - **Delay:** tune `STARDOCK_INTRO_NARRATION_START_SEC` so the overlap window is long enough.
- **Quick check:** narration-only intro (no theme) should sound fine — if so, the bug is the **mix**, not the TTS line.

---

## Needs to do / follow-ups (priority order)

### 1) Fix intro voiceover-over-music (bug above)
- Reproduce with theme WAV + `intro_narration.wav`; iterate until narrator is clearly audible over the tail.
- If `adelay` / filter graph stays flaky, build intro mix with **`ffmpeg` subprocess** (mirror outro fix).

### 2) Fix speech issues in the episode body
- Run **full** `generate-audio` on the episode once `main` and assets are stable so every line uses `normalize_trek_tts_text` (stardates, species lexicon).
- Add / tune **`tts_pronunciation.py`** entries after listening passes.
- **Zhanil:** ensure **`lt_zhanil_thkethris_1.wav`** on the render host; spoken timbre is still **`kokoro_voice`** until cloning exists.

### 3) Optional — match `voices/samples/Star_Trek_Horizon` (real reference voices)
- Plan a **second TTS path** (XTTS / F5 / API) that uses **`speaker_wav`**; route narrator first or full cast as budget allows.

### Narrator vs `narrator.wav` (same rule as all cast WAVs)
- **Kokoro does not clone from WAV** for narrator or anyone else. **`narrator.wav`** does not drive output today. To match it: **different `kokoro_voice`**, or **cloning pipeline** (priority 3).

### To hear “all fixes” in the episode body (reminder)
- **`reassemble-audio` does not re-speak dialogue.** Scene MP3s are whatever was rendered the last time **`generate-audio`** ran.
- After pod has latest `main`, correct **`assets/music`**, and **`lt_zhanil_thkethris_1.wav`**, run **full** `python main.py generate-audio ep_7ba65dfe` (or your episode id), then **`fetch_full_episode_from_runpod.sh`** (or `scp`).

### RunPod hygiene
- Ensure **named theme WAVs** (or env paths) exist under **`assets/music/`** on the pod if you do not want the generic `Cosmic_Odyssey_Main_Theme.wav` fallback.
- **`HF_TOKEN`** on the pod avoids Hugging Face rate-limit warnings when Kokoro pulls weights/voices.
- **GPU / CUDA**: logs showed CPU fallback on at least one run; worth checking pod GPU visibility if renders are slow.

### Operations checklist (short)
1. `git pull origin main` on pod.
2. Place/update WAVs: themes, `voices/samples/Star_Trek_Horizon/lt_zhanil_thkethris_1.wav`, etc.
3. Full **`generate-audio`** when body content must change; otherwise **`reassemble-audio`** / **`--refresh-intro`** for mux-only fixes.
4. **`bash scripts/fetch_full_episode_from_runpod.sh <IP> <PORT> ep_7ba65dfe`** to refresh local `full_episode.mp3`.

---

## Reference commands

```bash
# Deploy + start full render (from PC Git Bash; set TCP IP/port)
export RUNPOD_TCP_HOST=<ip> RUNPOD_TCP_PORT=<port>
bash scripts/gitbash_run_all_runpod.sh ep_7ba65dfe

# On pod: mux-only + optional intro rebuild
cd /workspace/stardock_podium_04
git pull origin main
.venv/bin/python main.py reassemble-audio ep_7ba65dfe --refresh-intro

# Download finished MP3 to PC
bash scripts/fetch_full_episode_from_runpod.sh <ip> <port> ep_7ba65dfe
```

---

*Last updated: 2026-04-24 (intro bug + samples vs Kokoro + next priorities).*
