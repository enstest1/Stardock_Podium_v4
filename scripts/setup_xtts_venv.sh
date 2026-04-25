#!/usr/bin/env bash
# Create Python 3.11 venv with Kokoro + Coqui XTTS (voice cloning).
# Coqui's ``TTS`` package does not support Python 3.12+; use this on RunPod
# when ``engine_order`` includes ``xtts``.
#
# Usage (repo root on the pod):
#   bash scripts/setup_xtts_venv.sh
#
# Optional: PYTHON311=python3.11
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON311:-python3.11}"
if ! command -v "$PY" &>/dev/null; then
  echo "Need $PY on PATH (install python3.11 or set PYTHON311=...)." >&2
  exit 1
fi
"$PY" -m venv .venv-xtts
.venv-xtts/bin/pip install -U pip setuptools wheel
.venv-xtts/bin/pip install -r requirements.txt
.venv-xtts/bin/pip install -r requirements-voice-clone.txt
# TTS may have pulled a newer transformers; keep XTTS import path working.
.venv-xtts/bin/pip install "transformers==4.46.2" "numpy>=1.22.0,<2.0" --force-reinstall
echo "---"
.venv-xtts/bin/python -c "import TTS, torch; print('TTS', TTS.__version__); print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available())"
echo "Use: .venv-xtts/bin/python main.py generate-audio <episode_id>"
