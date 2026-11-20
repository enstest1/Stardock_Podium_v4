"""Scene cards and sequential causal writing (NARRATIVE-001).

Owns: the ``SceneCard`` schema, the one-call episode planning prompt, JSON
parsing, Python-side validation (causality, value change, known cast), the
conversion of cards into the legacy ``episode['scenes']`` shape, and the
card/hand-off block that precedes each scene's script prompt.

Nothing here calls a model. ``StoryStructure._generate_scenes_from_cards``
does, through ``complete_text``.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

MIN_CARDS = 5
MAX_CARDS = 14
TAIL_LINES = 12
_REQUIRED_TEXT = ('goal', 'opposition', 'turn', 'value_shift', 'hands_off')


class SceneCard(BaseModel):
    scene_number: int
    kind: Literal['scene', 'sequel'] = 'scene'
    setting: str
    present: List[str] = Field(min_length=1)
    focus: str
    goal: str
    opposition: str
    turn: str
    outcome: Literal['yes', 'no', 'yes_but', 'no_and']
    value_shift: str
    audience_learns: str = ''
    caused_by: List[int] = Field(default_factory=list)
    hands_off: str
    sound_design: List[str] = Field(default_factory=list)


CARDS_SYSTEM = (
    'You are a story editor planning an audio drama episode. You design '
    'scenes that cause each other: every scene changes something for '
    'someone, and each scene exists because of an earlier one. You answer '
    'with JSON only.'
)

_SCHEMA_HINT = """{
  "scenes": [
    {"scene_number": 1, "kind": "scene", "setting": "...",
     "present": ["Name", "Name"], "focus": "Name",
     "goal": "what the focus character wants in this scene",
     "opposition": "who or what stands in the way",
     "turn": "the moment the scene changes direction",
     "outcome": "yes | no | yes_but | no_and",
     "value_shift": "what changes, as 'value: before -> after'",
     "audience_learns": "new information the listener gets",
     "caused_by": [],
     "hands_off": "what this scene leaves open for the next one",
     "sound_design": ["two or three specific sounds"]}
  ]
}"""


def target_card_count(minutes: Any) -> int:
    """Suggested number of scenes for an episode length (about 2.5 min each)."""
    try:
        m = float(minutes or 30)
    except (TypeError, ValueError):
        m = 30.0
    return max(MIN_CARDS, min(MAX_CARDS, round(m / 2.5)))


def build_cards_prompt(episode: Dict[str, Any], continuity: str = '') -> str:
    """User prompt asking for the whole episode as ordered scene cards."""
    minutes = episode.get('target_duration_minutes', 30)
    n = target_card_count(minutes)
    cast_lines = []
    for c in episode.get('characters') or []:
        name = (c.get('name') or '').strip()
        if not name:
            continue
        bits = [b for b in (c.get('role'), c.get('personality')) if b]
        cast_lines.append(f'- {name}' + (f': {"; ".join(bits)}' if bits else ''))
    parts = [
        f"EPISODE: {episode.get('title') or 'Untitled'}",
        f"Premise / theme: {episode.get('theme') or 'Not specified'}",
    ]
    if episode.get('format_brief'):
        parts.append(f"Show format: {episode['format_brief']}")
    parts.append(f'Target length: {minutes} minutes of audio.')
    slot = episode.get('arc_slot') or {}
    if slot.get('arc_beat'):
        parts.append(f"This episode's season milestone: {slot['arc_beat']}")
    parts.append('CAST (use these names exactly; no one else speaks):\n'
                 + ('\n'.join(cast_lines) or '- (none given)'))
    if continuity.strip():
        parts.append('CONTINUITY FROM EARLIER EPISODES:\n' + continuity.strip())
    parts.append(
        f'Plan the episode as {MIN_CARDS}-{MAX_CARDS} scenes (about {n} fits '
        'this length), in story order.\n'
        'Rules:\n'
        '- Every scene after the first lists in caused_by at least one '
        'EARLIER scene number that makes it happen.\n'
        '- Every scene has a value_shift that differs from the previous '
        "scene's.\n"
        '- Vary outcomes (yes, no, yes_but, no_and); do not use one outcome '
        'for every scene.\n'
        '- present and focus use only names from the cast list.\n'
        '- kind is "scene" (conflict) or "sequel" (reaction and decision).\n'
        '- This is audio: settings and turns must be audible, not visual.\n'
        '- The final scene resolves the episode question; hands_off for it '
        'is what lingers for the listener.\n\n'
        'Return only JSON in this shape:\n' + _SCHEMA_HINT)
    return '\n\n'.join(parts)


def _extract_json(raw: str) -> Any:
    text = (raw or '').strip()
    fence = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for open_c, close_c in (('{', '}'), ('[', ']')):
        start, end = text.find(open_c), text.rfind(close_c)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError('response is not valid JSON')


def parse_cards(raw: str) -> Tuple[List[SceneCard], List[str]]:
    """Parse model output into cards. Returns (cards, problems)."""
    try:
        data = _extract_json(raw)
    except ValueError as e:
        return [], [f'invalid JSON: {e}']
    items = data.get('scenes') if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        return [], ['JSON must contain a non-empty "scenes" list']
    cards: List[SceneCard] = []
    problems: List[str] = []
    for idx, item in enumerate(items, 1):
        if not isinstance(item, dict):
            problems.append(f'scene {idx}: not an object')
            continue
        try:
            cards.append(SceneCard.model_validate(item))
        except ValidationError as e:
            for err in e.errors():
                loc = '.'.join(str(x) for x in err.get('loc', ()))
                kind = err.get('type', '')
                msg = ('missing field ' + loc if kind == 'missing'
                       else f'{loc}: {err.get("msg")}')
                problems.append(f'scene {idx}: {msg}')
    return cards, problems


def validate_cards(cards: List[SceneCard], cast_names: List[str]) -> List[str]:
    issues: List[str] = []
    if not MIN_CARDS <= len(cards) <= MAX_CARDS:
        issues.append(f'{len(cards)} scenes; expected {MIN_CARDS}-{MAX_CARDS}')
    known = {n.strip().lower() for n in cast_names if n and n.strip()}
    for idx, card in enumerate(cards, 1):
        tag = f'scene {idx}'
        if card.scene_number != idx:
            issues.append(f'{tag}: scene_number is {card.scene_number}')
        for field in _REQUIRED_TEXT:
            if not getattr(card, field).strip():
                issues.append(f'{tag}: empty {field}')
        if idx > 1 and not card.caused_by:
            issues.append(f'{tag}: caused_by is empty')
        for c in card.caused_by:
            if not 1 <= c < idx:
                issues.append(f'{tag}: caused_by {c} is not an earlier scene')
        if known:
            for name in card.present:
                if name.strip().lower() not in known:
                    issues.append(f'{tag}: unknown character {name!r}')
        if idx > 1 and (card.value_shift.strip().lower()
                        == cards[idx - 2].value_shift.strip().lower()):
            issues.append(f'{tag}: same value_shift as the previous scene')
    if cards and len({c.outcome for c in cards}) == 1:
        issues.append('every scene has the same outcome')
    return issues


def cards_to_scenes(cards: List[SceneCard],
                    total_seconds: float) -> List[Dict[str, Any]]:
    """Cards -> legacy scene dicts (every key other modules read) + ``card``."""
    if not cards:
        return []
    # Sequels (reaction beats) get about half the time of a conflict scene.
    weights = [0.5 if c.kind == 'sequel' else 1.0 for c in cards]
    total_w = sum(weights)
    scenes = []
    for card, w in zip(cards, weights):
        scenes.append({
            'scene_id': f'scene_{uuid.uuid4().hex[:8]}',
            'scene_number': card.scene_number,
            'beat': card.kind,
            'setting': card.setting,
            'characters': list(card.present),
            'plot': (f'{card.focus} wants: {card.goal}. Against: '
                     f'{card.opposition}. Turn: {card.turn}.'),
            'sound_effects': ', '.join(card.sound_design),
            'duration_seconds': int(total_seconds * w / total_w),
            'card': card.model_dump(),
        })
    return scenes


def _spoken_tail(scene_script: Dict[str, Any], n: int = TAIL_LINES) -> List[str]:
    out = []
    for line in scene_script.get('lines') or []:
        kind = line.get('type')
        content = (line.get('content') or '').strip()
        if not content:
            continue
        if kind == 'dialogue':
            who = (line.get('character') or line.get('speaker') or '').strip()
            out.append(f'{who.upper()}: {content}')
        elif kind == 'narration':
            out.append(f'NARRATOR: {content}')
    return out[-n:]


def render_card_block(scene: Dict[str, Any],
                      previous_scene_script: Optional[Dict[str, Any]] = None,
                      next_scene: Optional[Dict[str, Any]] = None) -> str:
    """Text placed before a scene's script prompt on the card path."""
    card = scene.get('card') or {}
    if not card:
        return ''
    lines = [
        'SCENE CARD (write exactly this scene; the turn must happen on the page)',
        f"Setting: {card.get('setting', '')}",
        f"Present: {', '.join(card.get('present') or [])}",
        f"Focus character: {card.get('focus', '')}",
        f"Goal: {card.get('goal', '')}",
        f"Opposition: {card.get('opposition', '')}",
        f"Turn: {card.get('turn', '')}",
        f"Outcome: {card.get('outcome', '')}   "
        f"Value shift: {card.get('value_shift', '')}",
        'The audience learns: '
        + ((card.get('audience_learns') or '').strip() or '(nothing new)'),
        f"Leave unresolved for the next scene: {card.get('hands_off', '')}",
    ]
    if card.get('sound_design'):
        lines.append('Sounds: ' + ', '.join(card['sound_design']))
    next_card = (next_scene or {}).get('card') or {}
    if next_card.get('goal'):
        lines.append('Do NOT resolve this (it belongs to the next scene): '
                     + next_card['goal'])
    block = '\n'.join(lines)
    if previous_scene_script:
        prev_card = previous_scene_script.get('card') or {}
        prev = ['PREVIOUS SCENE (already written; continue from it, '
                'do not repeat it)']
        if prev_card.get('hands_off'):
            prev.append(f"It left unresolved: {prev_card['hands_off']}")
        prev.extend(_spoken_tail(previous_scene_script))
        block += '\n\n' + '\n'.join(prev)
    return block
