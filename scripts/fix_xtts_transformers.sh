#!/usr/bin/env bash
# Downgrade transformers for Coqui XTTS 0.22 (fixes BeamSearchScorer import on new HF).
# Run on the pod from repo root when XTTS falls back to Kokoro with that error.
#
#   bash scripts/fix_xtts_transformers.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$ROOT/.venv-xtts/bin/pip"
if [[ ! -x "$V" ]]; then
  echo "Need .venv-xtts (run: bash scripts/setup_xtts_venv.sh)" >&2
  exit 1
fi
# transformers 4.46.x may pull numpy 2.x; gruut (TTS) requires numpy<2.
"$V" install "transformers==4.46.2" "numpy>=1.22.0,<2.0" --force-reinstall
"$V" install "torchcodec" || echo "Warning: torchcodec install failed — XTTS may need it (see Docs/DEVLOG.md)." >&2
"$ROOT/.venv-xtts/bin/python" -c "import transformers as t; import TTS; print('transformers', t.__version__, '| TTS', TTS.__version__)"
