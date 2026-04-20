"""
Append-only JSONL traces for multi-step generation (debug / analytics).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from story_os.flags import feature_enabled

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    """Return a short unique run id."""
    return uuid.uuid4().hex[:12]


def trace_enabled() -> bool:
    return feature_enabled('USE_GENERATION_TRACE', default=False)


def log_step(run_id: str, step: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """Append one JSON line when tracing is enabled."""
    if not trace_enabled():
        return
    base = Path('logs') / 'generation'
    base.mkdir(parents=True, exist_ok=True)
    path = base / f'{run_id}.jsonl'
    row: Dict[str, Any] = {
        'ts': time.time(),
        'step': step,
    }
    if payload:
        row.update(payload)
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    except OSError as e:
        logger.warning('Trace write failed: %s', e)
