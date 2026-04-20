"""
Load and save Story OS JSON files under data/series/<series_id>/.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from story_os import models


def series_slug(series_name: str) -> str:
    """Filesystem-safe id from human series name (e.g. 'Main Series' -> main_series)."""
    s = (series_name or 'default').strip().lower()
    s = re.sub(r'[^a-z0-9]+', '_', s)
    return s.strip('_') or 'default'


def series_dir(series_id: str) -> Path:
    from config.paths import SERIES_DIR
    root = SERIES_DIR / series_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_show_state(series_id: str) -> Optional[models.ShowState]:
    path = series_dir(series_id) / 'show_state.json'
    if not path.exists():
        return None
    return models.ShowState.model_validate(load_json(path))


def save_show_state(state: models.ShowState, series_id: str) -> None:
    path = series_dir(series_id) / 'show_state.json'
    save_json(path, state.model_dump())


def load_series_bible(series_id: str) -> Optional[models.SeriesBible]:
    path = series_dir(series_id) / 'series_bible.json'
    if not path.exists():
        return None
    return models.SeriesBible.model_validate(load_json(path))


def save_series_bible(bible: models.SeriesBible) -> None:
    path = series_dir(bible.series_id) / 'series_bible.json'
    save_json(path, bible.model_dump())


def load_season_plan(series_id: str) -> Optional[models.SeasonPlan]:
    path = series_dir(series_id) / 'season_plan.json'
    if not path.exists():
        return None
    return models.SeasonPlan.model_validate(load_json(path))


def save_season_plan(plan: models.SeasonPlan) -> None:
    path = series_dir(plan.series_id) / 'season_plan.json'
    save_json(path, plan.model_dump())


def load_series_arc(series_id: str) -> Optional[models.SeriesArc]:
    path = series_dir(series_id) / 'series_arc.json'
    if not path.exists():
        return None
    return models.SeriesArc.model_validate(load_json(path))


def save_series_arc(arc: models.SeriesArc) -> None:
    path = series_dir(arc.series_id) / 'series_arc.json'
    save_json(path, arc.model_dump())


def episode_slot_path(series_id: str, episode_number: int) -> Path:
    return series_dir(series_id) / 'episode_slots' / f'{episode_number}.json'


def load_episode_slot(series_id: str, episode_number: int) -> Optional[models.EpisodeSlot]:
    path = episode_slot_path(series_id, episode_number)
    if not path.exists():
        return None
    return models.EpisodeSlot.model_validate(load_json(path))


def save_episode_slot(slot: models.EpisodeSlot) -> None:
    path = episode_slot_path(slot.series_id, slot.episode_index)
    save_json(path, slot.model_dump())


def promote_guest_to_main_cast(
    series_id: str,
    name: str,
    species: Optional[str] = None,
    role: Optional[str] = None,
    personality: Optional[str] = None,
    backstory: Optional[str] = None,
    voice_description: Optional[str] = None,
) -> bool:
    """Add a guest character to the series bible's permanent main_cast.

    If the character already exists in main_cast (by name), update fields.

    Returns:
        True if successfully promoted / updated.
    """
    bible = load_series_bible(series_id)
    if bible is None:
        return False

    existing = next(
        (m for m in bible.main_cast
         if m.name.lower() == name.lower()),
        None,
    )
    if existing:
        if species:
            existing.species = species
        if role:
            existing.role = role
        if personality:
            existing.personality = personality
        if backstory:
            existing.backstory = backstory
        if voice_description:
            existing.voice_description = voice_description
    else:
        bible.main_cast.append(
            models.CastMember(
                name=name,
                species=species,
                role=role,
                personality=personality,
                backstory=backstory,
                voice_description=voice_description,
            )
        )
    save_series_bible(bible)
    return True
