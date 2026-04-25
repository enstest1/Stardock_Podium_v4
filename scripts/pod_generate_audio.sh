#!/usr/bin/env bash
# Run full episode audio with the XTTS-capable venv (Python 3.11 + Coqui TTS).
# Falls back to .venv if .venv-xtts is missing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -x "$ROOT/.venv-xtts/bin/python" ]]; then
  exec "$ROOT/.venv-xtts/bin/python" "$ROOT/main.py" generate-audio "$@"
fi
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  echo "Warning: .venv-xtts not found; using .venv (no Coqui XTTS on Python 3.12)." >&2
  exec "$ROOT/.venv/bin/python" "$ROOT/main.py" generate-audio "$@"
fi
echo "No venv found. Run: bash scripts/setup_xtts_venv.sh" >&2
exit 1
