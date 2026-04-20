"""
Add lightweight ``director`` metadata to script lines (pause cues).

Heuristic only; optional LLM director can be layered later.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _pause_ms_for_line(text: str, line_type: str) -> int:
    t = (text or '').rstrip()
    if not t:
        return 120
    if line_type == 'narration' and len(t) > 220:
        return 450
    if t.endswith('...'):
        return 500
    if t[-1] in '.!?':
        if t[-1] == '?':
            return 420
        return 320
    return 220


def augment_script_with_director(script: Dict[str, Any]) -> None:
    """Mutate ``script`` in place: set ``director`` dict on lines."""
    for si, scene in enumerate(script.get('scenes') or []):
        for li, line in enumerate(scene.get('lines') or []):
            if not isinstance(line, dict):
                continue
            lt = line.get('type') or 'description'
            content = line.get('content') or ''
            pause = _pause_ms_for_line(content, lt)
            sfx = None
            m = re.search(r'\[sfx:\s*([^\]]+)\]', content, re.I)
            if m:
                sfx = m.group(1).strip()[:80]
            line['director'] = {
                'pause_after_ms': pause,
                'sfx_cue': sfx,
                'scene_index': si,
                'line_index': li,
            }
    logger.debug('Director metadata applied to script scenes.')
