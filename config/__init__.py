"""Stardock Podium configuration package.

Re-exports the public path symbols from ``config.paths`` so callers can
``from config import BOOKS_DIR, ensure_all_dirs`` instead of reaching into
the submodule.
"""

from config.paths import (
    ANALYSIS_DIR,
    AUDIO_DIR,
    BOOKS_DIR,
    DATA_DIR,
    EPISODES_DIR,
    KOKORO_MODEL_PATH,
    SERIES_DIR,
    SHOWS_DIR,
    SYNC_STATUS_DIR,
    TEMP_DIR,
    VOICES_DIR,
    VOICE_SAMPLES_DIR,
    ensure_all_dirs,
)

__all__ = [
    "ANALYSIS_DIR",
    "AUDIO_DIR",
    "BOOKS_DIR",
    "DATA_DIR",
    "EPISODES_DIR",
    "KOKORO_MODEL_PATH",
    "SERIES_DIR",
    "SHOWS_DIR",
    "SYNC_STATUS_DIR",
    "TEMP_DIR",
    "VOICES_DIR",
    "VOICE_SAMPLES_DIR",
    "ensure_all_dirs",
]
