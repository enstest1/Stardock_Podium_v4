"""
Centralized path configuration for Stardock Podium.

Defaults to relative paths so local development works out of the box.
Override via environment variables for cloud deployments (RunPod, Docker, etc.)
where user data should live on a persistent volume (e.g. /workspace/...).

Environment variables honored (all optional):

    STARDOCK_BOOKS_DIR      default: "books"
    STARDOCK_VOICES_DIR     default: "voices"
    STARDOCK_EPISODES_DIR   default: "episodes"
    STARDOCK_AUDIO_DIR      default: "audio"
    STARDOCK_DATA_DIR       default: "data"
    STARDOCK_ANALYSIS_DIR   default: "analysis"
    STARDOCK_TEMP_DIR       default: "temp"

Plus the TTS-specific:

    KOKORO_MODEL_PATH       default: "kokoro-tts-base-ft.pt"
                            (where local Kokoro weights live; the Kokoro v0.9+
                            KPipeline will auto-download if missing and cache
                            via HF_HOME, but this is honored for legacy flows
                            and the doctor diagnostic).
"""

from __future__ import annotations

import os
from pathlib import Path


def _get_path(env_var: str, default: str) -> Path:
    """Get a path from env var or fall back to default (relative to CWD)."""
    return Path(os.environ.get(env_var, default))


# User-data directories (persist on the /workspace volume in cloud).
BOOKS_DIR = _get_path("STARDOCK_BOOKS_DIR", "books")
VOICES_DIR = _get_path("STARDOCK_VOICES_DIR", "voices")
EPISODES_DIR = _get_path("STARDOCK_EPISODES_DIR", "episodes")
AUDIO_DIR = _get_path("STARDOCK_AUDIO_DIR", "audio")
DATA_DIR = _get_path("STARDOCK_DATA_DIR", "data")
ANALYSIS_DIR = _get_path("STARDOCK_ANALYSIS_DIR", "analysis")

# Subdirectories derived from DATA_DIR.
SERIES_DIR = DATA_DIR / "series"
SHOWS_DIR = DATA_DIR / "shows"
SYNC_STATUS_DIR = DATA_DIR / "sync_status"

# Voice samples (under VOICES_DIR).
VOICE_SAMPLES_DIR = VOICES_DIR / "samples"

# Ephemeral (pod-local; not persisted across pod restarts).
TEMP_DIR = _get_path("STARDOCK_TEMP_DIR", "temp")


# Default Kokoro model weights location (for legacy loaders / diagnostic).
KOKORO_MODEL_PATH = Path(
    os.environ.get("KOKORO_MODEL_PATH", "kokoro-tts-base-ft.pt")
)


def ensure_all_dirs() -> None:
    """Create all user-data directories if they don't already exist.

    Safe to call repeatedly. Does NOT touch TTS model paths (they're files).
    """
    for d in (
        BOOKS_DIR,
        VOICES_DIR,
        VOICE_SAMPLES_DIR,
        EPISODES_DIR,
        AUDIO_DIR,
        DATA_DIR,
        ANALYSIS_DIR,
        SERIES_DIR,
        SHOWS_DIR,
        SYNC_STATUS_DIR,
        TEMP_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


__all__ = [
    "BOOKS_DIR",
    "VOICES_DIR",
    "VOICE_SAMPLES_DIR",
    "EPISODES_DIR",
    "AUDIO_DIR",
    "DATA_DIR",
    "ANALYSIS_DIR",
    "SERIES_DIR",
    "SHOWS_DIR",
    "SYNC_STATUS_DIR",
    "TEMP_DIR",
    "KOKORO_MODEL_PATH",
    "ensure_all_dirs",
]
