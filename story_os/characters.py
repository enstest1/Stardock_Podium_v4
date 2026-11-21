"""Character profiles, derived state and arc steps (CHAR-001, NARRATIVE-003).

Owns ``data/projects/<id>/characters/<character_id>.json`` (CharacterProfile)
and ``characters/changes.jsonl`` (every profile edit with a reason).
Derived state (condition, location, knowledge) is rebuilt from the canon
ledger, never stored by hand. Arc steps must cite a canon event.
"""

from __future__ import annotations

import difflib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class DialogueProfile(BaseModel):
    vocabulary: str = ''
    rhythm: str = ''
    tics: List[str] = Field(default_factory=list)
    never_says: List[str] = Field(default_factory=list)


class ArcStep(BaseModel):
    position: int
    change: str
    event_id: str                        # canon evidence, required


class CharacterProfile(BaseModel):
    character_id: str
    name: str
    role_kind: Literal['character', 'host', 'narrator', 'guest_persona'] = 'character'
    role: str = ''
    want: str = ''
    need: str = ''
    wound: str = ''
    false_belief: str = ''
    dialogue: DialogueProfile = Field(default_factory=DialogueProfile)
    arc_steps: List[ArcStep] = Field(default_factory=list)


def _dir(project_id: str) -> Path:
    from story_os.projects import project_dir
    return project_dir(project_id) / 'characters'


def load_profiles(project_id: str) -> Dict[str, CharacterProfile]:
    d = _dir(project_id)
    out = {}
    if d.exists():
        for p in sorted(d.glob('*.json')):
            with open(p, 'r', encoding='utf-8') as f:
                prof = CharacterProfile.model_validate(json.load(f))
            out[prof.name] = prof
    return out


def save_profile(project_id: str, profile: CharacterProfile, reason: str) -> None:
    from story_os.projects import atomic_write_json
    d = _dir(project_id)
    atomic_write_json(d / f'{profile.character_id}.json', profile.model_dump())
    d.mkdir(parents=True, exist_ok=True)
    with open(d / 'changes.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': time.time(), 'character_id': profile.character_id,
                            'reason': reason}) + '\n')


def name_clashes(names: List[str]) -> List[str]:
    """Names too easy to confuse by ear (same first syllable / near spelling)."""
    warn = []
    firsts = [n.split()[0].lower() for n in names if n]
    for i in range(len(firsts)):
        for j in range(i + 1, len(firsts)):
            a, b = firsts[i], firsts[j]
            if a[:2] == b[:2] or difflib.SequenceMatcher(None, a, b).ratio() > 0.75:
                warn.append(f'{names[i]} / {names[j]} may sound alike')
    return warn


def profiles_from_identity(project_id: str, identity) -> Dict[str, CharacterProfile]:
    """Create profiles from the identity cast (fields filled by design_identity)."""
    from story_os.projects import _canon
    out = {}
    existing = load_profiles(project_id)
    for m in identity.cast:
        prof = existing.get(m.name) or CharacterProfile(
            character_id=f'char_{_canon(m.name)}', name=m.name, role=m.role)
        for field in ('want', 'need', 'wound', 'false_belief'):
            if not getattr(prof, field) and getattr(m, field, ''):
                setattr(prof, field, getattr(m, field))
        if not prof.dialogue.rhythm and getattr(m, 'speech_rhythm', ''):
            prof.dialogue.rhythm = m.speech_rhythm
        if not prof.dialogue.never_says and getattr(m, 'never_says', None):
            prof.dialogue.never_says = list(m.never_says)
        if not prof.dialogue.tics and getattr(m, 'verbal_tics', None):
            prof.dialogue.tics = list(m.verbal_tics)
        save_profile(project_id, prof, 'created from show identity')
        out[m.name] = prof
    return out


def enrich_profile(project_id: str, profile: CharacterProfile, context: str) -> CharacterProfile:
    """One planner call fills only EMPTY fields (never overwrites)."""
    from story_os import llm
    from story_os.projects import _json_from
    raw = llm.complete('planner', 'You are a story editor building character bibles. JSON only.',
                       f'SHOW: {context}\nCHARACTER: {profile.name} ({profile.role})\n'
                       'Return JSON: {"want": "...", "need": "...", "wound": "...", '
                       '"false_belief": "...", "rhythm": "how they talk", '
                       '"never_says": ["..."], "tics": ["..."]}', json=True,
                       max_tokens=600, temperature=0.7)
    data = _json_from(raw)
    for f in ('want', 'need', 'wound', 'false_belief'):
        if not getattr(profile, f) and data.get(f):
            setattr(profile, f, data[f])
    if not profile.dialogue.rhythm and data.get('rhythm'):
        profile.dialogue.rhythm = data['rhythm']
    if not profile.dialogue.never_says and data.get('never_says'):
        profile.dialogue.never_says = list(data['never_says'])[:4]
    if not profile.dialogue.tics and data.get('tics'):
        profile.dialogue.tics = list(data['tics'])[:3]
    save_profile(project_id, profile, 'enriched (empty fields only)')
    return profile


def derived_state(store, name: str) -> Dict[str, Any]:
    """CharacterState rebuilt from canon: attributes + what they know."""
    knows = [b['proposition'] for b in store.beliefs_of(name)
             if b['stance'] in ('knows', 'believes')][-5:]
    wrong = [b['proposition'] for b in store.beliefs_of(name) if b['truth'] == 'false']
    return {'name': name, 'state': store.character_state(name), 'knows': knows,
            'mistaken': wrong}


def add_arc_step(project_id: str, profile: CharacterProfile, change: str,
                 event_id: str, store) -> CharacterProfile:
    """Refused unless ``event_id`` is a canon event involving the character."""
    ev = {e['event_id']: e for e in store.query('events')}.get(event_id)
    if ev is None:
        raise ValueError(f'arc step needs canon evidence; {event_id!r} is not canon')
    pos = len(profile.arc_steps) + 1
    profile.arc_steps.append(ArcStep(position=pos, change=change, event_id=event_id))
    save_profile(project_id, profile, f'arc step {pos} from {event_id}')
    return profile


def render_character_briefs(card: Dict[str, Any], profiles: Dict[str, CharacterProfile],
                            store=None) -> str:
    """Per present character: objective, withheld, knows, dialogue profile."""
    present = card.get('present') or []
    objectives = card.get('objectives') or {}
    withheld = card.get('withheld') or {}
    blocks = []
    for name in present:
        prof = profiles.get(name) or next(
            (p for p in profiles.values() if p.name.split()[0].lower() == name.split()[0].lower()), None)
        lines = [f'{name}:']
        if objectives.get(name):
            lines.append(f'  wants in this scene: {objectives[name]}')
        if withheld.get(name):
            lines.append(f'  is hiding: {withheld[name]}')
        if prof:
            if prof.want and prof.role_kind == 'character':
                lines.append(f'  long-term want: {prof.want}; false belief: {prof.false_belief}')
            d = prof.dialogue
            if d.rhythm:
                lines.append(f'  speaks: {d.rhythm}')
            if d.tics:
                lines.append(f'  habits: {", ".join(d.tics)}')
            if d.never_says:
                lines.append(f'  never says: {"; ".join(d.never_says)}')
        if store is not None:
            st = derived_state(store, prof.name if prof else name)
            if st['knows']:
                lines.append('  knows: ' + '; '.join(st['knows'][-3:]))
            if st['mistaken']:
                lines.append('  wrongly believes: ' + '; '.join(st['mistaken'][-2:]))
        blocks.append('\n'.join(lines))
    return 'CHARACTER BRIEFS (only these people are in the scene):\n' + '\n'.join(blocks) if blocks else ''
