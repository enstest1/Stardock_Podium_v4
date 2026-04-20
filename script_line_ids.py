"""
Assign stable line_id values to episode script lines (optional field).

Backward compatible: scripts without line_id continue to work; callers can
run ensure_script_line_ids before persisting to support pins and ADR.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List


def ensure_script_line_ids(script: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of script with UUID line_id on each line that lacks it.

    Args:
        script: Episode script dict with scenes[].lines[].

    Returns:
        Updated script (mutates nested line dicts in place for simplicity).
    """
    scenes = script.get('scenes') or []
    for scene in scenes:
        lines = scene.get('lines') or []
        for line in lines:
            if not isinstance(line, dict):
                continue
            if not line.get('line_id'):
                line['line_id'] = str(uuid.uuid4())
    return script


def count_lines_missing_ids(script: Dict[str, Any]) -> int:
    """Count lines without line_id (for migration reporting)."""
    missing = 0
    for scene in script.get('scenes') or []:
        for line in scene.get('lines') or []:
            if isinstance(line, dict) and not line.get('line_id'):
                missing += 1
    return missing
