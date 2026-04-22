#!/usr/bin/env bash
# Resume full episode render on RunPod (after pod restart or fresh pod).
# Run from Git Bash on your PC.
#
#   bash scripts/resume_episode_on_runpod.sh HOST PORT [episode_id]
#
# Direct TCP (root@IP): get IP and PORT from RunPod Connect → SSH.
#
# RunPod proxy (user@ssh.runpod.io): use HOST=ssh.runpod.io PORT=22 and set
#   export RUNPOD_SSH_USER='aavugmxhgx4i01-64411b6a'
# (copy the username from your Connect line before @ssh.runpod.io)
#
# Default key: ~/.ssh/id_ed25519 — override: RUNPOD_KEY=/path/to/key
# Optional: RUNPOD_ENV_FILE=/c/Users/you/project/.env to upload a specific file
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
SSH_USER="${RUNPOD_SSH_USER:-root}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="/workspace/stardock_podium_04"
# Optional: which local .env to upload (default: $ROOT/.env)
ENV_LOCAL="${RUNPOD_ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$ENV_LOCAL" ]]; then
  echo "Missing $ENV_LOCAL — create it or set RUNPOD_ENV_FILE=/path/to/.env"
  exit 1
fi

echo ">> Uploading .env from $ENV_LOCAL ... ($SSH_USER@${HOST})"
scp -o BatchMode=yes -o ConnectTimeout=30 -i "$KEY" -P "$PORT" \
  "$ENV_LOCAL" "${SSH_USER}@${HOST}:${REPO}/.env"

echo ">> Remote: pull, venv, start render for ${EP} ..."
ssh -o BatchMode=yes -o ConnectTimeout=30 -i "$KEY" -p "$PORT" "${SSH_USER}@${HOST}" \
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
