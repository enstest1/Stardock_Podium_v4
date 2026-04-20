"""
Asyncio compatibility helper for running coroutines from sync code
regardless of whether an event loop is already active.

Motivation:
    ``asyncio.run(coro)`` raises ``RuntimeError`` when called from inside an
    existing running loop (e.g. Jupyter, pytest‑asyncio, any wrapper that
    schedules our sync CLI from an async context). Several call sites in
    ``cli_entrypoint`` and ``script_editor`` invoke ``asyncio.run`` directly
    and will break the moment the CLI is ever driven async.

Usage:
    from story_os.asyncio_compat import run_coro

    result = run_coro(generate_scenes(episode_id))
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Awaitable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


def run_coro(coro: Awaitable[T]) -> T:
    """Run ``coro`` to completion, from either sync or async context.

    Resolution order:
        1. If no event loop is running in this thread → ``asyncio.run``.
        2. If a loop **is** running → run the coroutine in a new loop on
           a worker thread and block the caller until it completes. This
           keeps the caller's sync signature intact without nesting loops.

    Returns:
        The value returned by the coroutine.

    Raises:
        Any exception raised by the coroutine itself.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No loop in this thread → safe to use asyncio.run directly.
        return asyncio.run(coro)

    # We are inside a running loop; run the coroutine in a dedicated thread.
    logger.debug(
        "run_coro: active event loop detected — dispatching to worker thread")
    result: dict[str, Any] = {}

    def _runner() -> None:
        try:
            result['value'] = asyncio.run(coro)
        except BaseException as exc:
            result['error'] = exc

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join()

    if 'error' in result:
        raise result['error']
    return result['value']
