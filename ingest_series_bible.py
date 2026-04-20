#!/usr/bin/env python
"""
CLI helper: chunk markdown/text into per-series bible RAG store.

See ``story_os.bible_rag.ingest_markdown_folder``.
"""

from __future__ import annotations

import logging

from story_os import io
from story_os.bible_rag import ingest_markdown_folder

logger = logging.getLogger(__name__)


def ingest_cli(series_name: str, folder: str) -> int:
    """Run ingest for a human series name; returns chunk count."""
    sid = io.series_slug(series_name)
    n = ingest_markdown_folder(sid, folder)
    logger.info('Ingested %s chunks for series key %s.', n, sid)
    return n
