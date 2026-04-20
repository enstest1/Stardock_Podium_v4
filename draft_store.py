"""
Human-in-the-loop drafts and pinned line overrides for episodes.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _episode_root(episode_id: str) -> Path:
    from config.paths import EPISODES_DIR
    return EPISODES_DIR / episode_id


def _pins_path(episode_id: str) -> Path:
    return _episode_root(episode_id) / 'pins.json'


def save_script_draft(episode_id: str, script: Dict[str, Any], label: str) -> Path:
    """Write a timestamped copy under ``drafts/``."""
    drafts = _episode_root(episode_id) / 'drafts'
    drafts.mkdir(parents=True, exist_ok=True)
    name = f'{int(time.time())}_{label}.json'.replace(' ', '_')
    path = drafts / name
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(script, f, indent=2, ensure_ascii=False)
    logger.info('Saved script draft %s', path)
    return path


def load_line_overrides(episode_id: str) -> Dict[str, str]:
    """Return ``line_id`` -> replacement ``content`` from ``pins.json``."""
    path = _pins_path(episode_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return {}
    raw = data.get('line_overrides')
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items()}


def apply_line_overrides(script: Dict[str, Any], episode_id: str) -> int:
    """Apply ``pins.json`` overrides to ``script`` in place. Returns count."""
    ovr = load_line_overrides(episode_id)
    if not ovr:
        return 0
    n = 0
    for scene in script.get('scenes') or []:
        for line in scene.get('lines') or []:
            lid = line.get('line_id')
            if lid and lid in ovr:
                line['content'] = ovr[lid]
                n += 1
    if n:
        logger.info('Applied %s pinned line overrides for %s.', n, episode_id)
    return n
