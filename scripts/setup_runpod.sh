#!/bin/bash
# RunPod first-time environment setup script for Stardock Podium.
#
# Run ONCE after cloning the repo on a fresh pod. Safe to re-run (each step
# is idempotent). Assumes a persistent network volume is mounted at
# /workspace — follow the guide in Docs for creating the volume and pod.
#
# Usage:
#   bash scripts/setup_runpod.sh

set -e  # Exit on any error

echo "============================================================"
echo "  Stardock Podium — RunPod Setup"
echo "============================================================"

# Sanity check — are we on RunPod (or anywhere with /workspace)?
if [ ! -d "/workspace" ]; then
    echo "[!!] /workspace not found. This script is for RunPod environments."
    echo "     For local setup, just run: pip install -r requirements.txt"
    exit 1
fi

PROJECT_ROOT="/workspace/Stardock_Podium_v4"

echo ""
echo ">> Installing system dependencies (ffmpeg, git, vim, wget)..."
apt-get update -qq
apt-get install -y -qq ffmpeg git vim wget

echo ""
echo ">> Installing Python dependencies..."
pip install -q -r requirements.txt --break-system-packages || \
    pip install -q -r requirements.txt

echo ""
echo ">> Setting up Kokoro model weights on persistent volume..."
mkdir -p /workspace/models
if [ ! -f "/workspace/models/kokoro-tts-base-ft.pt" ]; then
    echo "   Downloading Kokoro weights (~330 MB)..."
    wget -q --show-progress \
        https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v0_19.pth \
        -O /workspace/models/kokoro-tts-base-ft.pt
else
    echo "   [OK] Kokoro weights already present"
fi

# Symlink weights into the repo so anything hardcoded to the repo-root
# filename still resolves. The new config.paths + tts_engine.py flow reads
# KOKORO_MODEL_PATH directly, but the symlink is free insurance for legacy
# tooling and scripts.
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
if [ ! -e "kokoro-tts-base-ft.pt" ]; then
    ln -sf /workspace/models/kokoro-tts-base-ft.pt kokoro-tts-base-ft.pt
    echo "   Symlinked weights into repo root"
fi

echo ""
echo ">> Creating persistent data directories under $PROJECT_ROOT ..."
mkdir -p "$PROJECT_ROOT"/{books,voices/samples,data/series,data/shows,data/sync_status,episodes,audio,analysis,temp}

echo ""
echo ">> Checking .env file..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "   [!!] Created .env from template. EDIT IT NOW to add API keys:"
        echo "          nano .env"
    else
        echo "   [!!] No .env.example found. Create .env manually with API keys."
    fi
else
    echo "   [OK] .env already exists"
fi

echo ""
echo "============================================================"
echo "  Setup complete."
echo "============================================================"
echo ""
echo "  Next steps:"
echo "    1. Edit .env:                      nano .env"
echo "    2. Paste your API keys and the cloud path overrides:"
echo "         KOKORO_MODEL_PATH=/workspace/models/kokoro-tts-base-ft.pt"
echo "         HF_HOME=/workspace/models/hf_cache"
echo "         STARDOCK_BOOKS_DIR=$PROJECT_ROOT/books"
echo "         STARDOCK_VOICES_DIR=$PROJECT_ROOT/voices"
echo "         STARDOCK_DATA_DIR=$PROJECT_ROOT/data"
echo "         STARDOCK_EPISODES_DIR=$PROJECT_ROOT/episodes"
echo "         STARDOCK_AUDIO_DIR=$PROJECT_ROOT/audio"
echo "         STARDOCK_ANALYSIS_DIR=$PROJECT_ROOT/analysis"
echo "    3. Run diagnostics:                python main.py doctor"
echo "    4. Upload EPUBs to:                $PROJECT_ROOT/books"
echo "    5. Upload voice WAVs to:           $PROJECT_ROOT/voices/samples"
echo "    6. Run ingest (one time):          python main.py ingest"
echo "    7. Generate:                       python main.py new-show ..."
echo ""
