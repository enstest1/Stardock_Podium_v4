#!/usr/bin/env bash
# Resume full episode render on RunPod (after pod restart or fresh pod).
# Run from Git Bash on your PC.
#
#   bash scripts/resume_episode_on_runpod.sh HOST PORT [episode_id]
#
# Get HOST and TCP PORT from the RunPod pod "Connect" SSH line.
# Default key: ~/.ssh/id_ed25519 — override: RUNPOD_KEY=/path/to/key
#
# Remote path: /workspace/stardock_podium_04 (clone repo there if missing).
#
# Uploads .env, git pull, venv+pip, clears cached outro narration, optional
# KOKORO_EXTRA_TAIL_TRIM_MS, starts generate-audio in background.

set -euo pipefail

HOST="${1:?usage: HOST PORT [episode_id]}"
PORT="${2:?usage: HOST PORT [episode_id]}"
EP="${3:-ep_7ba65dfe}"
KEY="${RUNPOD_KEY:-$HOME/.ssh/id_ed25519}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="/workspace/stardock_podium_04"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — add API keys first."
  exit 1
fi

echo ">> Uploading .env ..."
scp -o BatchMode=yes -o ConnectTimeout=30 -i "$KEY" -P "$PORT" \
  "$ROOT/.env" "root@${HOST}:${REPO}/.env"

echo ">> Remote: pull, venv, start render for ${EP} ..."
ssh -o BatchMode=yes -o ConnectTimeout=30 -i "$KEY" -p "$PORT" "root@${HOST}" \
  "EP='${EP}' REPO='${REPO}' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REPO" || { echo "No $REPO — on pod run: cd /workspace && git clone https://github.com/enstest1/Stardock_Podium_v4.git stardock_podium_04"; exit 1; }
git pull origin main || true
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -r requirements.txt
rm -f assets/music/outro_narration.wav
grep -q KOKORO_EXTRA_TAIL_TRIM_MS .env 2>/dev/null || echo "KOKORO_EXTRA_TAIL_TRIM_MS=10" >> .env
pkill -f "main.py generate-audio" 2>/dev/null || true
: > /tmp/stardock_gen_ep.log
nohup .venv/bin/python main.py generate-audio "$EP" >> /tmp/stardock_gen_ep.log 2>&1 &
echo "Started background job (see /tmp/stardock_gen_ep.log)"
sleep 5
tail -n 40 /tmp/stardock_gen_ep.log
REMOTE
