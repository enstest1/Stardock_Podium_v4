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

### RunPod / SSH
- `scripts/gitbash_run_all_runpod.sh`: requires **TCP SSH** (`root@IP -p PORT`); RunPod **`ssh.runpod.io` proxy** does not support `scp` or `ssh host "cmd"`. Uses `StrictHostKeyChecking=accept-new` for first connect.
- `scripts/fetch_full_episode_from_runpod.sh`: pulls `full_episode.mp3` down after render.

### CLI
- **`reassemble-audio <episode_id>`**: rebuilds **outro** + **`full_episode.mp3`** from existing `scene_XX/scene_audio.mp3` (no scene dialogue re-synth).
- **`reassemble-audio <episode_id> --refresh-intro`**: also deletes and rebuilds **`intro_complete.mp3`** (new intro narration + theme mux with current code).

### Bugfixes
- `outro_file.parent.mkdir(..., exist_ok=True)` (removed duplicate `parents=` kwarg).
- Outro mux: resample / layout alignment + direct ffmpeg for final mix.

---

## Needs to do / follow-ups

### To hear “all fixes” in the episode body
- **`reassemble-audio` does not re-speak dialogue.** Scene MP3s are whatever was rendered the last time **`generate-audio`** ran.
- After pod has latest `main`, correct **`assets/music`**, and **`lt_zhanil_thkethris_1.wav`**, run a **full** `python main.py generate-audio ep_7ba65dfe` (or equivalent) so **every line** goes through the new normalization and Zhanil sample path.
- Then **`scp`** / `fetch_full_episode_from_runpod.sh` the new `full_episode.mp3`.

### Narrator vs `narrator.wav`
- **Kokoro does not clone from WAV.** Synthesis uses **`kokoro_voice`** (e.g. `bm_george`). To match `narrator.wav` you need either a **different Kokoro preset**, or **voice-cloning TTS** (XTTS / F5 / etc.) with a new code path, or a **hosted API** that accepts a reference clip.

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

*Last updated: 2026-04-24.*
