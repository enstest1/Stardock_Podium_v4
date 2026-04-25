#!/usr/bin/env bash
# Quick CUDA runtime check (not just nvidia-smi). Run on the pod after SSH.
# If this fails with CUDA_ERROR_UNKNOWN / cuda: False, the pod image/passthrough
# is broken — stop the pod and deploy a RunPod template with working CUDA
# (e.g. official PyTorch or CUDA 12.x), then reinstall .venv-xtts if needed.
set -euo pipefail
export NVIDIA_DRIVER_CAPABILITIES="${NVIDIA_DRIVER_CAPABILITIES:-all}"
export NVIDIA_VISIBLE_DEVICES="${NVIDIA_VISIBLE_DEVICES:-all}"
if [[ -z "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  unset CUDA_VISIBLE_DEVICES || true
fi
echo "== nvidia-smi (NVML) =="
nvidia-smi -L || true
echo "== PyTorch (.venv-xtts if present) =="
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/.venv-xtts/bin/python"
if [[ ! -x "$PY" ]]; then PY="${ROOT}/.venv/bin/python"; fi
if [[ ! -x "$PY" ]]; then echo "No venv python"; exit 1; fi
"$PY" -c "import torch; print('torch', torch.__version__); print('cuda_available', torch.cuda.is_available());
print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO GPU')"
