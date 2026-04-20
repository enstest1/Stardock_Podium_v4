"""
Lightweight series-bible retrieval (chunk store + token overlap).

No embedding dependency: optional upgrade path to Mem0/vectors later.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from story_os.io import series_dir

logger = logging.getLogger(__name__)

_CHUNKS_NAME = 'bible_chunks.json'
_CHUNK_CHARS = 900
_CHUNK_OVERLAP = 120


def _chunks_path(series_id: str) -> Path:
    return series_dir(series_id) / _CHUNKS_NAME


def _tokenize(text: str) -> List[str]:
    return re.findall(r'[a-z0-9]+', text.lower())


def _score(query: str, chunk_text: str) -> float:
    qset = set(_tokenize(query))
    if not qset:
        return 0.0
    cset = set(_tokenize(chunk_text))
    if not cset:
        return 0.0
    inter = len(qset & cset)
    return inter / (len(qset) ** 0.5)


def ingest_markdown_folder(series_id: str, folder: str) -> int:
    """Chunk all ``.md`` / ``.txt`` files under ``folder`` into JSON storage.

    Args:
        series_id: Series id (slug).
        folder: Directory to scan recursively.

    Returns:
        Number of chunks written (replaces prior chunk list).
    """
    root = Path(folder)
    if not root.is_dir():
        logger.error('Bible folder not found: %s', folder)
        return 0

    chunks: List[Dict[str, Any]] = []
    idx = 0
    for path in sorted(root.rglob('*')):
        if path.suffix.lower() not in ('.md', '.txt'):
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='replace')
        except OSError as e:
            logger.warning('Skip %s: %s', path, e)
            continue
        pos = 0
        while pos < len(text):
            end = min(pos + _CHUNK_CHARS, len(text))
            piece = text[pos:end].strip()
            if piece:
                chunks.append(
                    {
                        'chunk_id': f'{series_id}_{idx}',
                        'text': piece,
                        'source': str(path.as_posix()),
                    }
                )
                idx += 1
            pos = end - _CHUNK_OVERLAP if end < len(text) else len(text)

    out = _chunks_path(series_id)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'chunks': chunks}, f, indent=2, ensure_ascii=False)
    logger.info('Ingested %s bible chunks for %s.', len(chunks), series_id)
    return len(chunks)


def search_bible_chunks(
    series_id: str,
    query: str,
    top_k: int = 5,
) -> List[str]:
    """Return top chunk texts by simple overlap score."""
    path = _chunks_path(series_id)
    if not path.exists():
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    rows = data.get('chunks') or []
    scored: List[Tuple[float, str]] = []
    for row in rows:
        txt = row.get('text') or ''
        s = _score(query, txt)
        if s > 0:
            scored.append((s, txt))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:top_k]]
