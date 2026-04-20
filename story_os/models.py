"""
Pydantic models for series bible, arcs, season plans, and show state.

Used when Story OS files exist; validation is optional at import time.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PlotThread(BaseModel):
    """Serialized plot thread for continuity."""

    thread_id: str
    summary: str
    status: Literal['open', 'resolved', 'parked'] = 'open'


class CharacterState(BaseModel):
    """Per-character continuity snapshot."""

    location: Optional[str] = None
    emotional_beat: Optional[str] = None
    last_seen_episode_id: Optional[str] = None
    notes: Optional[str] = None


class WorldFact(BaseModel):
    """Established canon fact."""

    fact_id: str
    statement: str
    source_episode_id: Optional[str] = None


class Hook(BaseModel):
    """Unresolved story hook."""

    hook_id: str
    description: str


class ShowState(BaseModel):
    """Rolling canon for a series (strict when Story OS is enabled)."""

    series_id: str = 'default'
    active_threads: List[PlotThread] = Field(default_factory=list)
    character_states: Dict[str, CharacterState] = Field(default_factory=dict)
    world_facts: List[WorldFact] = Field(default_factory=list)
    unresolved_hooks: List[Hook] = Field(default_factory=list)
    last_updated_episode_id: Optional[str] = None
    schema_version: int = 1


class CastMember(BaseModel):
    """Permanent series cast member."""

    name: str
    species: Optional[str] = None
    role: Optional[str] = None
    personality: Optional[str] = None
    backstory: Optional[str] = None
    voice_description: Optional[str] = None


class SeriesBible(BaseModel):
    """Creator-facing series configuration."""

    series_id: str
    title: str
    themes: List[str] = Field(default_factory=list)
    tone_notes: Optional[str] = None
    taboos: List[str] = Field(default_factory=list)
    finale_notes: Optional[str] = None
    main_cast: List[CastMember] = Field(default_factory=list)


class BeatSlot(BaseModel):
    """Maps Save-the-Cat style beat to an episode index."""

    beat_id: str
    beat_name: str
    episode_index: int
    notes: Optional[str] = None


class SeriesArc(BaseModel):
    """Series-level beat coverage."""

    series_id: str
    beats: List[BeatSlot] = Field(default_factory=list)


class SeasonPlan(BaseModel):
    """One season's episode count and beat mapping."""

    season_id: str
    series_id: str
    episode_count: int
    beats: List[BeatSlot] = Field(default_factory=list)


class EpisodeSlot(BaseModel):
    """Per-episode obligations from the planner."""

    episode_index: int
    series_id: str
    season_id: str
    primary_beat_id: Optional[str] = None
    must_plant: List[str] = Field(default_factory=list)
    must_payoff: List[str] = Field(default_factory=list)
