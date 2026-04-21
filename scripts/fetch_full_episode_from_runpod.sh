#!/usr/bin/env bash
# Pull full_episode.mp3 from RunPod after SSH is working again.
#
# Example (Git Bash; replace POD_IP and PORT from RunPod Connect tab):
#   bash scripts/fetch_full_episode_from_runpod.sh 203.57.40.210 10085 ep_7ba65dfe

set -euo pipefail
HOST="${1:?usage: HOST PORT [episode_id, default ep_7ba65dfe]}"
PORT="${2:?usage: HOST PORT [episode_id]}"
EP="${3:-ep_7ba65dfe}"
KEY="${RUNPOD_KEY:-$HOME/.ssh/id_ed25519}"
REMOTE="/workspace/stardock_podium_04/episodes/${EP}/audio/full_episode.mp3"
LOCAL="episodes/${EP}/audio/full_episode.mp3"
mkdir -p "$(dirname "$LOCAL")"
scp -o BatchMode=yes -o ConnectTimeout=30 -i "$KEY" -P "$PORT" \
  "root@${HOST}:$REMOTE" "$LOCAL"
ls -la "$LOCAL"
