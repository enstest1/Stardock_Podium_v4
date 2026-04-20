"""
Feature flags for Story OS and agentic pipeline (env overrides JSON file).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

_FLAGS_PATH = Path('data/feature_flags.json')


def load_feature_flags() -> Dict[str, Any]:
    """Load flags from data/feature_flags.json if present."""
    if not _FLAGS_PATH.exists():
        return {}
    try:
        with open(_FLAGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def feature_enabled(name: str, default: bool = False) -> bool:
    """Return True if flag is enabled via env or JSON file.

    Env wins: USE_STORY_OS=1 or true enables regardless of file.
    """
    env_key = name.upper()
    raw = os.environ.get(env_key)
    if raw is not None:
        return raw.strip().lower() in ('1', 'true', 'yes', 'on')
    flags = load_feature_flags()
    val = (
        flags.get(name)
        or flags.get(name.upper())
        or flags.get(name.lower())
    )
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ('1', 'true', 'yes', 'on')
    return default
