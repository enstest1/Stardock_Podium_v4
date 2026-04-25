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

### No API keys (RunPod TTS-only / `generate-audio` without OpenAI)
- **`mem0_client.get_mem0_client()`** — if `STARDOCK_DISABLE_MEM0` is set, or `Mem0Client()` init fails (e.g. local Mem0 stack needs `OPENAI_API_KEY` for embeddings), the singleton falls back to **`_Mem0Disabled`** (no-op search/add). **Do not** construct `Mem0Client()` in startup paths that must run without keys; **`main.py` `init_modules`** now calls `get_mem0_client()` only.
- **`story_structure.StoryStructure`** — `self.client` / `self.async_client` are **optional** when `OPENAI_API_KEY` is unset; **`get_episode()`** and file I/O work. LLM helpers guard before `self.client` / `self.async_client` use.
- **`script_editor.ScriptEditor`** — `self.client` optional for **loading** `script.json`; **scene regeneration** still requires a key.

### Coqui XTTS (clone voices) on headless / RunPod
- **CPML license prompt** reads **stdin**; under **`nohup`** you get **EOF** and XTTS never loads, then the pipeline falls back to **Kokoro**. Fix: set **`COQUI_TOS_AGREED=1`** (see `scripts/pod_generate_audio.sh` and `tts_engine.py` `XTTSEngine.__init__` before `CoquiTTS(...)`). You must still comply with [Coqui CPML](https://coqui.ai/cpml) (non-commercial) or a commercial license.
- **`engine_order`**: `["xtts", "kokoro"]` in `voices/voice_config.json`; venv: **`.venv-xtts`** (Python 3.11 + Coqui). **`scripts/pod_generate_audio.sh`** points `main.py generate-audio` at that venv and exports NVIDIA/Coqui env.
- **`transformers` vs TTS 0.22:** if the log shows **`XTTS failed … cannot import name 'BeamSearchScorer'`**, a **too-new** `transformers` is installed. Pin **`transformers==4.46.2`** (see `requirements-voice-clone.txt`), or on an existing venv: **`bash scripts/fix_xtts_transformers.sh`**, then run **`generate-audio` again** for real clones (not Kokoro fallback). After that install, use **`numpy>=1.22,<2.0`** (see `fix_xtts_transformers.sh`) so **gruut** stays happy.
- **PyTorch 2.6+** defaults **`torch.load(..., weights_only=True)`**, which breaks Coqui checkpoints (“Weights only load failed”). `tts_engine.XTTSEngine` patches `torch.load` to pass **`weights_only=False`** for trusted Coqui/HF caches before loading XTTS.
- **“TorchCodec is required for load_with_torchcodec”**: install **`torchcodec`** in **`.venv-xtts`** (included in `requirements-voice-clone.txt`; **`fix_xtts_transformers.sh`** and **`setup_xtts_venv.sh`** try to install it). We also stage **every** `speaker_wav` through **librosa + soundfile** so your sample files are not read via torchcodec.

### RunPod: “Your Pod’s GPUs are no longer available”
- In the RunPod dialog, use **Automatically migrate your Pod data (Recommended)** so you get **GPU** again (same class if offered). **Do not** rely on “Start using CPUs” for a full episode with **XTTS** (far too slow).
- After the new pod is **Running**, open **Connect** and copy the **new** `ssh … -p …` (IP/port change after migration).
- On the pod: `cd` to your repo (often `/workspace/stardock_podium_04`), `git pull`, then **`bash scripts/runpod_full_clone_render.sh ep_7ba65dfe`** (or the same steps by hand: `fix_xtts_transformers.sh`, then `nohup bash scripts/pod_generate_audio.sh …`).
- When the log shows **`Synthesized dialogue (xtts)`** and not constant **`XTTS failed`**, you have **clones** in the mix. Then on your PC: **`fetch_full_episode_from_runpod.sh`** with the **new** host/port.

### Bugfixes
- `outro_file.parent.mkdir(..., exist_ok=True)` (removed duplicate `parents=` kwarg).
- Outro mux: resample / layout alignment + direct ffmpeg for final mix.

### Intro mix fix (was: music plays, narrator not over tail)
- **Cause:** ffmpeg-python graph for mono `adelay` + `amix` (`normalize=0`) often dropped or buried narration over the theme tail.
- **Change:** `_create_intro_segment` now builds the intro with a **`ffmpeg` subprocess** `filter_complex` (same idea as outro): theme `atrim` / fades / `apad`, narration `pan` to stereo, **`adelay=delays=MS|MS`**, ducked music (`volume=0.30`) + boosted voice (`volume=1.4`), **`amix=normalize=1`**, 44.1 kHz stereo MP3.
- **Verify on pod:** `reassemble-audio <id> --refresh-intro` and audition `intro_complete.mp3` (narrator must sit clearly on the fading theme).

---

## Needs to do / follow-ups (priority order)

### 1) Confirm intro in a real render
- After pull, run **`reassemble-audio … --refresh-intro`** (or full `generate-audio`); tweak `STARDOCK_INTRO_NARRATION_START_SEC` / theme length if overlap timing feels wrong.

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
- **Do not** use `pkill -f "main.py generate-audio"` inside the same `ssh` one-liner as the pkill string: the **remote** `bash -c` command line can **include that text**, and **pkill can kill the SSH shell** (exit 255). Stop renders with **`ps aux | grep` pod path + `kill <pid>`** from an interactive pod shell, or match only the **`.venv-xtts/.../python ... main.py`** line.

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

# On pod: full episode with XTTS clone path (after migrate + git pull)
cd /workspace/stardock_podium_04
bash scripts/runpod_full_clone_render.sh ep_7ba65dfe

# Download finished MP3 to PC
bash scripts/fetch_full_episode_from_runpod.sh <ip> <port> ep_7ba65dfe
```

---

*Last updated: 2026-04-25 (RunPod migrate note; `torchcodec` + `runpod_full_clone_render.sh` for clone episode).*
