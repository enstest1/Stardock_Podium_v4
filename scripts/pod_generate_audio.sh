#!/usr/bin/env bash
# Run full episode audio with the XTTS-capable venv (Python 3.11 + Coqui TTS).
# Falls back to .venv if .venv-xtts is missing.
#
# NVIDIA containers (RunPod): some images set CUDA_VISIBLE_DEVICES to an empty
# string or omit driver capabilities; that can break cuInit for PyTorch while
# nvidia-smi still works. If CUDA still fails, redeploy the pod (CUDA_ERROR_UNKNOWN).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export NVIDIA_DRIVER_CAPABILITIES="${NVIDIA_DRIVER_CAPABILITIES:-all}"
export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
if [[ -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  unset CUDA_VISIBLE_DEVICES || true
fi
if [[ -x "$ROOT/.venv-xtts/bin/python" ]]; then
  exec "$ROOT/.venv-xtts/bin/python" "$ROOT/main.py" generate-audio "$@"
fi
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  echo "Warning: .venv-xtts not found; using .venv (no Coqui XTTS on Python 3.12)." >&2
  exec "$ROOT/.venv/bin/python" "$ROOT/main.py" generate-audio "$@"
fi
echo "No venv found. Run: bash scripts/setup_xtts_venv.sh" >&2
exit 1
