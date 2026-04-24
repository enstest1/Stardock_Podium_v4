#!/usr/bin/env bash
# From the repo root (Git Bash on Windows):
#   bash scripts/gitbash_run_all_runpod.sh [episode_id] [tcp_host] [tcp_port]
#
# IMPORTANT — RunPod "proxy" SSH (user@ssh.runpod.io) is interactive-only: it does
# not support ``ssh host "cmd"``, ``scp``, or ``ssh -T``. This script needs
# "SSH over exposed TCP" from the pod Connect tab: root@<ip> -p <port>.
#
# Examples:
#   export RUNPOD_TCP_HOST=203.x.x.x RUNPOD_TCP_PORT=12345
#   bash scripts/gitbash_run_all_runpod.sh ep_7ba65dfe
#
#   bash scripts/gitbash_run_all_runpod.sh ep_7ba65dfe 203.x.x.x 12345
#
# Optional: RUNPOD_KEY, RUNPOD_SSH_USER (default root for TCP), RUNPOD_ENV_FILE

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
KEY="${RUNPOD_KEY:-$HOME/.ssh/id_ed25519}"
REPO="/workspace/stardock_podium_04"
EP="${1:-ep_7ba65dfe}"
TCP_HOST="${2:-${RUNPOD_TCP_HOST:-}}"
TCP_PORT="${3:-${RUNPOD_TCP_PORT:-}}"
SSH_USER="${RUNPOD_SSH_USER:-root}"
ENV_LOCAL="${RUNPOD_ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$ENV_LOCAL" ]]; then
  echo "Missing $ENV_LOCAL — create .env or set RUNPOD_ENV_FILE"
  exit 1
fi

if [[ -z "$TCP_HOST" || -z "$TCP_PORT" ]]; then
  cat <<EOF
This script uploads .env and starts generate-audio over full (TCP) SSH.

RunPod's ssh.runpod.io proxy cannot run it — no remote commands / no scp.

From your pod's Connect tab, copy "SSH over exposed TCP" (IP + port), then:

  export RUNPOD_TCP_HOST=<ip> RUNPOD_TCP_PORT=<port>
  bash scripts/gitbash_run_all_runpod.sh ${EP}

Or pass host and port as 2nd and 3rd arguments.

Web-terminal fallback (paste on the pod):

  cd ${REPO} && git pull origin main && source .venv/bin/activate && pip install -q -r requirements.txt
  rm -f assets/music/outro_narration.wav
  pkill -f "main.py generate-audio" 2>/dev/null || true
  nohup .venv/bin/python main.py generate-audio ${EP} >> /tmp/stardock_gen_ep.log 2>&1 &
  tail -f /tmp/stardock_gen_ep.log
EOF
  exit 1
fi

echo ">> Uploading .env to ${SSH_USER}@${TCP_HOST}:${TCP_PORT}:${REPO}/.env ..."
# First-time pods: add host key without prompting (reject if key changes later).
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new)
scp "${SSH_OPTS[@]}" -i "$KEY" -P "$TCP_PORT" \
  "$ENV_LOCAL" "${SSH_USER}@${TCP_HOST}:${REPO}/.env"

echo ">> Remote: pull, venv, start generate-audio for ${EP} ..."
ssh "${SSH_OPTS[@]}" -i "$KEY" -p "$TCP_PORT" \
  "${SSH_USER}@${TCP_HOST}" \
  "EP='${EP}' REPO='${REPO}' bash -s" <<'REMOTE'
set -euo pipefail
cd "$REPO" || { echo "No $REPO — on pod: cd /workspace && git clone https://github.com/enstest1/Stardock_Podium_v4.git stardock_podium_04"; exit 1; }
git pull origin main
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -q -r requirements.txt
if [[ ! -f "episodes/${EP}/script.json" ]]; then
  echo "Missing episodes/${EP}/script.json on pod — copy the episode, then re-run."
  exit 1
fi
rm -f assets/music/outro_narration.wav
grep -q KOKORO_EXTRA_TAIL_TRIM_MS .env 2>/dev/null || echo "KOKORO_EXTRA_TAIL_TRIM_MS=10" >> .env
pkill -f "main.py generate-audio" 2>/dev/null || true
: > /tmp/stardock_gen_ep.log
nohup .venv/bin/python main.py generate-audio "$EP" >> /tmp/stardock_gen_ep.log 2>&1 &
echo "Background job started. Log: /tmp/stardock_gen_ep.log"
sleep 5
tail -n 50 /tmp/stardock_gen_ep.log
REMOTE
