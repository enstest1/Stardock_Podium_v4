"""
Export a rough word-clock timeline from ``script.json``.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_WPS = 2.4  # words per second (dialogue-ish heuristic)


def _word_count(text: str) -> int:
    return len(re.findall(r'\w+', text or ''))


def export_episode_timeline(episode_id: str) -> Path:
    """Build ``exports/timeline.json`` with cumulative start times (seconds)."""
    from config.paths import EPISODES_DIR
    ep_dir = EPISODES_DIR / episode_id
    script_path = ep_dir / 'script.json'
    if not script_path.exists():
        raise FileNotFoundError(script_path)

    script = json.loads(script_path.read_text(encoding='utf-8'))
    exports = ep_dir / 'exports'
    exports.mkdir(parents=True, exist_ok=True)
    out_path = exports / 'timeline.json'

    t = 0.0
    chapters: List[Dict[str, Any]] = []

    for si, scene in enumerate(script.get('scenes') or []):
        sc_start = t
        lines_out: List[Dict[str, Any]] = []
        for line in scene.get('lines') or []:
            lt = line.get('type') or 'line'
            text = line.get('content') or ''
            w = max(1, _word_count(text))
            dur = w / _WPS
            pause = 0.0
            director = line.get('director') or {}
            if isinstance(director, dict) and 'pause_after_ms' in director:
                try:
                    pause = float(director['pause_after_ms']) / 1000.0
                except (TypeError, ValueError):
                    pause = 0.0
            lines_out.append(
                {
                    'line_id': line.get('line_id'),
                    'type': lt,
                    'start_s': round(t, 3),
                    'duration_s': round(dur + pause, 3),
                }
            )
            t += dur + pause
        chapters.append(
            {
                'scene_index': si,
                'scene_number': scene.get('scene_number'),
                'beat': scene.get('beat'),
                'start_s': round(sc_start, 3),
                'end_s': round(t, 3),
                'lines': lines_out,
            }
        )

    payload = {
        'episode_id': episode_id,
        'title': script.get('title'),
        'approx_total_s': round(t, 2),
        'chapters': chapters,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info('Wrote timeline export %s', out_path)
    return out_path
