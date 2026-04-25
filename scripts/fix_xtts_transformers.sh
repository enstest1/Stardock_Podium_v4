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
"$V" install "transformers==4.46.2" --force-reinstall
"$ROOT/.venv-xtts/bin/python" -c "import transformers as t; import TTS; print('transformers', t.__version__, '| TTS', TTS.__version__)"
