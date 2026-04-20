"""
Update rolling ``ShowState`` after a script is finalized.

Heuristic updates only (no LLM): character last-seen, light hook detection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from story_os import io, models

logger = logging.getLogger(__name__)

_HOOK_HINTS = (
    'cliffhanger',
    'to be continued',
    'unknown vessel',
    'distress call',
    'end of transmission',
)


def _maybe_hooks_from_script(script: Dict[str, Any]) -> List[models.Hook]:
    hooks: List[models.Hook] = []
    scenes = script.get('scenes') or []
    if not scenes:
        return hooks
    tail = scenes[-1].get('lines') or []
    for line in tail[-5:]:
        text = (line.get('content') or '').strip()
        low = text.lower()
        if not text:
            continue
        if any(h in low for h in _HOOK_HINTS) or text.endswith('...'):
            hooks.append(
                models.Hook(
                    hook_id=f'auto_{len(hooks)}',
                    description=text[:280],
                )
            )
    return hooks[:3]


def update_show_state_after_script(
    series_id: str,
    episode_id: str,
    episode: Dict[str, Any],
    script: Dict[str, Any],
) -> models.ShowState:
    """Merge episode and script signals into ``ShowState`` and save.

    Args:
        series_id: Series filesystem id.
        episode_id: Current episode id.
        episode: Episode structure (characters, theme, etc.).
        script: Full script dict (scenes/lines).

    Returns:
        Updated ``ShowState`` instance.
    """
    state = io.load_show_state(series_id)
    if state is None:
        state = models.ShowState(series_id=series_id)

    state.last_updated_episode_id = episode_id

    for ch in episode.get('characters') or []:
        name = (ch.get('name') or '').strip()
        if not name:
            continue
        prev = state.character_states.get(name, models.CharacterState())
        prev.last_seen_episode_id = episode_id
        role = ch.get('role') or ''
        if role:
            prev.notes = str(role)[:200]
        state.character_states[name] = prev

    existing_desc = {h.description[:100] for h in state.unresolved_hooks}
    for hook in _maybe_hooks_from_script(script):
        key = hook.description[:100]
        if key not in existing_desc:
            state.unresolved_hooks.append(hook)
            existing_desc.add(key)

    while len(state.unresolved_hooks) > 25:
        state.unresolved_hooks.pop(0)

    io.save_show_state(state, series_id)
    logger.info('Show state updated for series %s after %s.', series_id, episode_id)
    return state
