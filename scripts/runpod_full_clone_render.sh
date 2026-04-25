#!/usr/bin/env bash
# Run on a GPU RunPod *after* you migrate a stopped pod and open SSH.
# Produces a full episode with Coqui XTTS (clone) when the venv is healthy.
#
#   cd /workspace/stardock_podium_04   # or your clone path
#   git pull
#   bash scripts/runpod_full_clone_render.sh ep_7ba65dfe
#
set -euo pipefail
EP="${1:?usage: <episode_id> e.g. ep_7ba65dfe}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git pull --ff-only || git pull
bash scripts/fix_xtts_transformers.sh
LOG="${STARDOCK_GEN_LOG:-/tmp/stardock_gen_clones.log}"
echo "Starting generate-audio for $EP — log: $LOG"
nohup bash scripts/pod_generate_audio.sh "$EP" --quality high >>"$LOG" 2>&1 &
echo "PID $!  —  tail: tail -f $LOG"
echo "When done, on your PC: bash scripts/fetch_full_episode_from_runpod.sh <ip> <port> $EP"
