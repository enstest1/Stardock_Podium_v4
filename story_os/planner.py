"""
Season planning: map Save-the-Cat beats across episodes and persist slots.

Writes ``season_plan.json`` and per-episode ``episode_slots/<n>.json`` under
``data/series/<series_id>/``.
"""

from __future__ import annotations

import logging
from typing import List

from story_structure import StoryStructure

from story_os import io, models

logger = logging.getLogger(__name__)


def build_season_plan(
    series_id: str,
    season_id: str,
    episode_count: int,
) -> models.SeasonPlan:
    """Spread beat-sheet milestones across ``episode_count`` episodes.

    Args:
        series_id: Filesystem-safe series key (see ``io.series_slug``).
        season_id: Season label (e.g. ``s1``).
        episode_count: Number of planned episodes (>= 1).

    Returns:
        Validated ``SeasonPlan`` (not yet written to disk).
    """
    sheet: List[dict] = StoryStructure.BEAT_SHEET
    beats: List[models.BeatSlot] = []
    last = max(episode_count - 1, 1)

    for ep_idx in range(1, episode_count + 1):
        if episode_count == 1:
            bi = 0
        else:
            t = (ep_idx - 1) / last
            bi = min(len(sheet) - 1, int(round(t * (len(sheet) - 1))))
        row = sheet[bi]
        desc = (row.get('description') or '')[:240]
        beats.append(
            models.BeatSlot(
                beat_id=f'stc_{bi}',
                beat_name=row['name'],
                episode_index=ep_idx,
                notes=desc,
            )
        )

    return models.SeasonPlan(
        season_id=season_id,
        series_id=series_id,
        episode_count=episode_count,
        beats=beats,
    )


def persist_season_plan(plan: models.SeasonPlan) -> None:
    """Save season plan and one ``EpisodeSlot`` file per episode index."""
    io.save_season_plan(plan)
    for bs in plan.beats:
        slot = models.EpisodeSlot(
            episode_index=bs.episode_index,
            series_id=plan.series_id,
            season_id=plan.season_id,
            primary_beat_id=bs.beat_id,
            must_plant=[],
            must_payoff=[],
        )
        io.save_episode_slot(slot)
    logger.info(
        'Persisted season plan %s/%s (%s episodes).',
        plan.series_id,
        plan.season_id,
        plan.episode_count,
    )


def plan_and_write(
    series_id: str,
    season_id: str,
    episode_count: int,
) -> models.SeasonPlan:
    """Build and persist a season plan."""
    plan = build_season_plan(series_id, season_id, episode_count)
    persist_season_plan(plan)
    return plan
