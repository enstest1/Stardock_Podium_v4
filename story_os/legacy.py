"""Pre-v5 show wording, read from data (BASE-003).

Owns nothing on disk; reads ``data/shows/legacy_format.json``. Used only on
the legacy path (episodes without ``project_id``), so franchise wording lives
in a data file instead of in code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _data() -> dict:
    from config.paths import DATA_DIR
    return json.loads((Path(DATA_DIR) / 'shows' / 'legacy_format.json').read_text(encoding='utf-8'))


def legacy(key: str, **fmt: Any):
    value = _data()[key]
    return value.format(**fmt) if fmt and isinstance(value, str) else value
