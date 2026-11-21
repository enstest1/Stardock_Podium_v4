"""Canon ledger record schemas (CANON-001).

Every record that can reach the ledger cites script ``line_id``s and a
verbatim quote. ``status`` is ``draft`` until the episode is approved.
Schemas are ours, written from the handoff text (doc 05 was not supplied).
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

SCHEMA_VERSION = 1
Status = Literal['draft', 'canon', 'superseded']


class Evidence(BaseModel):
    episode_id: str                     # "REF:<source_id>" for source events
    line_ids: List[str] = Field(min_length=1)
    quote: str


class Verification(BaseModel):
    quote_ok: bool = False
    judged: Optional[bool] = None       # single-claim judge for irreversible changes
    judge_reason: str = ''


class _Record(BaseModel):
    schema_version: int = SCHEMA_VERSION
    episode_id: str
    episode_number: int = 0
    scene_number: int = 0
    status: Status = 'draft'
    origin: Literal['generated', 'source'] = 'generated'
    source_id: Optional[str] = None
    evidence: Evidence
    verification: Verification = Field(default_factory=Verification)

    @model_validator(mode='after')
    def _canon_needs_verification(self):
        if self.status == 'canon' and not self.verification.quote_ok:
            raise ValueError('a canon record must have a verified quote')
        return self


class CanonEvent(_Record):
    event_id: str
    kind: Literal['action', 'reveal', 'decision', 'state_change', 'arrival',
                  'departure', 'discovery'] = 'action'
    summary: str
    actors: List[str] = Field(default_factory=list)
    witnesses: List[str] = Field(default_factory=list)
    consequential: bool = True


class StateChange(_Record):
    change_id: str
    entity: str
    attribute: str                      # condition, location, possession, role ...
    before: str = ''
    after: str
    irreversible: bool = False
    event_id: Optional[str] = None


class Belief(_Record):
    belief_id: str
    holder: str                         # character name or 'AUDIENCE'
    proposition: str
    stance: Literal['knows', 'believes', 'suspects', 'denies', 'claims'] = 'believes'
    truth: Literal['true', 'false', 'unknown'] = 'unknown'
    about_event_id: Optional[str] = None
    told_by: Optional[str] = None


class RelationshipDelta(_Record):
    delta_id: str
    a: str
    b: str
    dimension: Literal['trust', 'affection', 'respect', 'fear', 'rivalry',
                       'obligation'] = 'trust'
    direction: Literal['up', 'down'] = 'down'
    reason: str = ''


class Promise(_Record):
    promise_id: str
    kind: Literal['question', 'mystery', 'setup', 'threat', 'vow',
                  'secret', 'goal'] = 'question'
    statement: str
    horizon: Literal['scene', 'episode', 'season', 'series'] = 'episode'
    state: Literal['open', 'developed', 'paid', 'abandoned'] = 'open'
    developed_by: List[str] = Field(default_factory=list)
    paid_by: Optional[str] = None
    planted_in: str = ''                # episode_id


KIND_FILES = {
    'events': CanonEvent, 'state_changes': StateChange, 'beliefs': Belief,
    'relationships': RelationshipDelta, 'promises': Promise,
}
ID_FIELD = {'events': 'event_id', 'state_changes': 'change_id',
            'beliefs': 'belief_id', 'relationships': 'delta_id',
            'promises': 'promise_id'}
