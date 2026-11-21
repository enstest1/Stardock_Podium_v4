"""Nonfiction segment cards (GEN-002), parallel to ``scene_cards``.

Documentary, educational and conversational episodes are planned as ordered
segment cards (``SegmentCard`` from project_models), validated in Python,
then written sequentially like scenes. ``segments_to_scenes`` keeps the
``episode['scenes']`` shape so audio and QA code are unchanged.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from story_os.project_models import SegmentCard
from story_os.scene_cards import _extract_json

MIN_SEGMENTS, MAX_SEGMENTS = 3, 12
GENERAL = 'general knowledge'

SEGMENTS_SYSTEM = ('You are a producer planning a nonfiction podcast episode as ordered '
                   'segments. Hosts are disclosed fictional personas. You never invent '
                   'facts, people or quotations. JSON only.')

_SCHEMA = """{"segments": [{"segment_number": 1, "kind": "cold_open|context|explanation|example|evidence|counterpoint|exchange|story|check_understanding|recap|sign_off",
  "purpose": "...", "speakers": ["Host Name"], "key_points": ["..."],
  "claim_ids": ["CL-0001" or "general knowledge"], "builds_on": [],
  "listener_takeaway": "...", "transition_to_next": "...", "sound_design": ["..."]}]}"""


def build_segment_prompt(episode: Dict[str, Any], claims_block: str, context: str = '',
                         objectives: Optional[List[str]] = None) -> str:
    hosts = [c.get('name') for c in episode.get('characters') or [] if c.get('name')]
    parts = [f"EPISODE: {episode.get('title')}", f"TOPIC: {episode.get('theme')}",
             f"Show format: {episode.get('format_brief', '')}",
             f"Target length: {episode.get('target_duration_minutes', 10)} minutes.",
             'HOSTS (fictional personas; only they speak): ' + ', '.join(hosts)]
    if episode.get('framework_block'):
        parts.append(episode['framework_block'])
    if objectives:
        parts.append('LEARNING OBJECTIVES (each must be covered; last segment is a recap):\n- '
                     + '\n- '.join(objectives))
    if context:
        parts.append(context)
    parts.append(claims_block)
    parts.append(f'Plan {MIN_SEGMENTS}-{MAX_SEGMENTS} segments. Every key point that states a '
                 'fact lists the claim id it relies on, or "general knowledge". builds_on '
                 'lists earlier segment numbers.\nReturn JSON:\n' + _SCHEMA)
    return '\n\n'.join(parts)


def parse_segments(raw: str) -> Tuple[List[SegmentCard], List[str]]:
    try:
        data = _extract_json(raw)
    except ValueError as e:
        return [], [f'invalid JSON: {e}']
    items = data.get('segments') if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        return [], ['JSON must contain a non-empty "segments" list']
    cards, problems = [], []
    for i, item in enumerate(items, 1):
        try:
            cards.append(SegmentCard.model_validate(item))
        except ValidationError as e:
            for err in e.errors():
                problems.append(f"segment {i}: {'.'.join(map(str, err['loc']))}: {err['msg']}")
    return cards, problems


def validate_segments(cards: List[SegmentCard], hosts: List[str], *,
                      claims_mode: bool, known_claims: set,
                      objectives: Optional[List[str]] = None) -> List[str]:
    issues = []
    if not MIN_SEGMENTS <= len(cards) <= MAX_SEGMENTS:
        issues.append(f'{len(cards)} segments; expected {MIN_SEGMENTS}-{MAX_SEGMENTS}')
    known = {h.lower() for h in hosts} | {h.split()[0].lower() for h in hosts}
    for i, c in enumerate(cards, 1):
        tag = f'segment {i}'
        if c.segment_number != i:
            issues.append(f'{tag}: segment_number is {c.segment_number}')
        for s in c.speakers:
            if s.lower() not in known:
                issues.append(f'{tag}: unknown speaker {s!r}')
        for b in c.builds_on:
            if not 1 <= b < i:
                issues.append(f'{tag}: builds_on {b} is not an earlier segment')
        if not c.listener_takeaway.strip():
            issues.append(f'{tag}: empty listener_takeaway')
        if claims_mode:
            for kp in c.key_points:
                states_fact = bool(re.search(
                    r'\b\d{2,}\b|\d\s*(%|percent|million|billion|thousand|km|kg|tons?|'
                    r'miles|metres|meters|years)', kp, re.I))
                ids = [x for x in c.claim_ids if x != GENERAL]
                if states_fact and not ids:
                    issues.append(f'{tag}: key point with a figure has no claim id: {kp[:60]!r}')
            for x in c.claim_ids:
                if x != GENERAL and x not in known_claims:
                    issues.append(f'{tag}: unknown claim id {x}')
    if objectives:
        text = ' '.join(' '.join(c.key_points) + ' ' + c.purpose for c in cards).lower()
        for o in objectives:
            words = [w for w in re.findall(r'[a-z]{5,}', o.lower())]
            if words and not any(w in text for w in words):
                issues.append(f'objective not covered: {o[:60]!r}')
        if cards and cards[-1].kind not in ('recap', 'sign_off') and \
                not any(c.kind == 'recap' for c in cards[-2:]):
            issues.append('educational episode must end with a recap')
    return issues


def segments_to_scenes(cards: List[SegmentCard], total_seconds: float) -> List[Dict[str, Any]]:
    weights = [0.6 if c.kind in ('cold_open', 'recap', 'sign_off', 'check_understanding') else 1.0
               for c in cards]
    tw = sum(weights) or 1
    return [{'scene_id': f'scene_{uuid.uuid4().hex[:8]}', 'scene_number': c.segment_number,
             'beat': c.kind, 'setting': 'studio', 'characters': list(c.speakers),
             'plot': c.purpose, 'sound_effects': ', '.join(c.sound_design),
             'duration_seconds': int(total_seconds * w / tw), 'segment': c.model_dump()}
            for c, w in zip(cards, weights)]


def render_segment_block(scene: Dict[str, Any], previous: Optional[Dict[str, Any]] = None,
                         nxt: Optional[Dict[str, Any]] = None) -> str:
    s = scene.get('segment') or {}
    lines = ['SEGMENT CARD (write exactly this segment)',
             f"Kind: {s.get('kind')}   Purpose: {s.get('purpose')}",
             f"Speakers: {', '.join(s.get('speakers') or [])}",
             'Key points:\n' + '\n'.join(f'  - {k}' for k in s.get('key_points') or []),
             f"Claims to use: {', '.join(s.get('claim_ids') or []) or 'none'}",
             f"Listener takeaway: {s.get('listener_takeaway')}"]
    if s.get('transition_to_next'):
        lines.append(f"Hand over to the next segment with: {s['transition_to_next']}")
    if (nxt or {}).get('segment'):
        lines.append(f"Do NOT cover yet (next segment): {nxt['segment'].get('purpose')}")
    block = '\n'.join(lines)
    if previous:
        tail = [f"{(l.get('character') or 'NARRATOR').upper()}: {l.get('content')}"
                for l in (previous.get('lines') or []) if l.get('type') in ('dialogue', 'narration')][-8:]
        block += '\n\nPREVIOUS SEGMENT (continue from it, do not repeat it)\n' + '\n'.join(tail)
    return block
