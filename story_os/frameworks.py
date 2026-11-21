"""Episode framework registry and selection (NARRATIVE-002).

Owns the data rows for story/segment frameworks and ``select_framework``.
Frameworks are *functions an episode must contain*, not scene lists; the
card planner maps them to as many scenes as it needs (``SceneCard.step``).

Selection rule (deterministic first, written down here because doc 03 was
not supplied with the handoff):
 1. keep the mode's family (``frameworks`` capability)
 2. drop the framework used by the previous episode, and any used twice in
    the last four
 3. hard matches from the milestone: mystery payoff/clues -> mystery_fairplay;
    climax -> ticking_clock / three_act; low point -> tragedy_dilemma;
    two focus characters -> two_hander; three or more -> abc_ensemble
 4. order the rest by genre bias, then by least recently used
 5. if two or more candidates tie at the top, a chooser (the planner model)
    picks among at most three; otherwise the top one is used
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, model_validator


class Step(BaseModel):
    id: str
    function: str
    share: float


class Framework(BaseModel):
    id: str
    name: str
    family: str = 'fiction'
    steps: List[Step]
    tags: List[str] = Field(default_factory=list)
    audio_notes: str = ''

    @model_validator(mode='after')
    def _shares(self):
        if abs(sum(s.share for s in self.steps) - 1.0) > 1e-6:
            raise ValueError(f'{self.id}: step shares must sum to 1')
        return self


def _fw(fid, name, family, steps, tags=(), audio=''):
    return Framework(id=fid, name=name, family=family, tags=list(tags), audio_notes=audio,
                     steps=[Step(id=s[0], function=s[1], share=s[2]) for s in steps])


REGISTRY: Dict[str, Framework] = {f.id: f for f in [
    # ---------------------------------------------------------- fiction
    _fw('three_act', 'Three-act turn', 'fiction', [
        ('setup', 'establish want and normal world fast', .2),
        ('confrontation', 'escalating attempts that cost something', .5),
        ('resolution', 'decisive choice and its consequence', .3)], ['climax']),
    _fw('mystery_fairplay', 'Fair-play mystery', 'fiction', [
        ('question', 'pose a concrete question the listener can try to solve', .15),
        ('clues', 'plant clues in plain hearing, one misdirect', .35),
        ('pressure', 'a cost to keep asking', .2),
        ('reveal', 'answer using only clues already heard', .3)], ['mystery', 'payoff'],
        'clues must be audible: said aloud or a distinct sound'),
    _fw('bottle', 'Bottle episode', 'fiction', [
        ('trap', 'characters stuck in one place', .2),
        ('pressure', 'the room squeezes secrets out', .5),
        ('break', 'something said that cannot be unsaid', .3)], ['horror', 'drama'],
        'one ambience bed carries the whole episode'),
    _fw('two_hander', 'Two-hander', 'fiction', [
        ('meeting', 'two people, opposed needs', .2),
        ('sparring', 'each tries to move the other', .5),
        ('shift', 'one of them changes position', .3)], ['focus2']),
    _fw('abc_ensemble', 'A/B/C ensemble', 'fiction', [
        ('a_story', 'main plot, highest stakes', .5),
        ('b_story', 'a relationship line that mirrors the theme', .3),
        ('c_story', 'a light runner that pays off at the end', .2)], ['focus3', 'comedy']),
    _fw('tragedy_dilemma', 'Tragic dilemma', 'fiction', [
        ('bind', 'a choice between two goods or two harms', .25),
        ('delay', 'attempts to avoid choosing fail', .4),
        ('choice', 'the choice is made and paid for', .35)], ['low_point', 'horror']),
    _fw('ticking_clock', 'Ticking clock', 'fiction', [
        ('deadline', 'a hard deadline stated aloud', .15),
        ('race', 'obstacles eat the time', .55),
        ('wire', 'the last second decides it', .3)], ['climax', 'thriller'],
        'use a recurring time sound (clock, countdown, train)'),
    _fw('kishotenketsu', 'Kishotenketsu', 'fiction', [
        ('ki', 'introduce a situation', .25), ('sho', 'develop it', .25),
        ('ten', 'an unexpected turn from outside', .25),
        ('ketsu', 'reconcile both threads', .25)], ['quiet', 'literary']),
    _fw('heist_plan', 'Plan and execution', 'fiction', [
        ('plan', 'the plan is laid out', .25), ('execution', 'it goes wrong in steps', .5),
        ('twist', 'the hidden part of the plan lands', .25)], ['caper']),
    _fw('revelation_spiral', 'Revelation spiral', 'fiction', [
        ('surface', 'what everyone believes', .2),
        ('layers', 'each scene peels a belief away', .55),
        ('core', 'the truth recolours the opening', .25)], ['mystery', 'drama']),
    # --------------------------------------------------------- nonfiction
    _fw('investigative_question', 'Investigative question', 'nonfiction', [
        ('question', 'a question worth an episode', .15), ('evidence', 'what the sources show', .5),
        ('counterpoint', 'the strongest other reading', .15), ('answer', 'what we can say and cannot', .2)]),
    _fw('chronological', 'Chronological', 'nonfiction', [
        ('before', 'the world before', .2), ('event', 'what happened', .5), ('after', 'consequences', .3)]),
    _fw('case_study', 'Case study', 'nonfiction', [
        ('case', 'one concrete case', .4), ('pattern', 'what it shows in general', .4),
        ('takeaway', 'what to remember', .2)]),
    _fw('profile', 'Profile', 'nonfiction', [
        ('portrait', 'who or what it is', .3), ('turning_points', 'key moments', .5),
        ('legacy', 'why it matters', .2)]),
    # -------------------------------------------------------- educational
    _fw('explainer', 'Explainer', 'educational', [
        ('hook', 'a puzzle the listener cares about', .1), ('objective', 'what they will learn', .05),
        ('explain', 'the idea in plain steps', .35), ('example', 'a worked example', .25),
        ('check', 'a question to check understanding', .1), ('recap', 'recap', .15)]),
    _fw('myth_vs_fact', 'Myth vs fact', 'educational', [
        ('myths', 'common beliefs', .3), ('facts', 'what is actually true and why', .5),
        ('rule', 'a rule of thumb', .2)]),
    _fw('how_to', 'How-to', 'educational', [
        ('goal', 'the result', .1), ('steps', 'the steps, one at a time', .7), ('pitfalls', 'common mistakes', .2)]),
    # ----------------------------------------------------- conversational
    _fw('host_discussion', 'Host discussion', 'conversational', [
        ('topic', 'set up the topic', .15), ('views', 'hosts disagree with reasons', .6),
        ('landing', 'where they end up', .25)]),
    _fw('interview_persona', 'Interview (fictional persona)', 'conversational', [
        ('intro', 'introduce the persona as synthetic', .1), ('questions', 'questions and answers', .75),
        ('close', 'one last question', .15)]),
    _fw('roundtable', 'Roundtable', 'conversational', [
        ('prompt', 'the question', .1), ('round', 'each voice answers', .6), ('synthesis', 'synthesis', .3)]),
    _fw('listener_questions', 'Listener questions', 'conversational', [
        ('mailbag', 'read questions', .2), ('answers', 'answer them', .7), ('next', 'tease next time', .1)]),
]}

FAMILY_DEFAULT = {'fiction': 'three_act', 'nonfiction': 'investigative_question',
                  'educational': 'explainer', 'conversational': 'host_discussion'}

GENRE_BIAS: Dict[str, List[str]] = {
    'horror': ['bottle', 'mystery_fairplay', 'tragedy_dilemma'],
    'mystery': ['mystery_fairplay', 'revelation_spiral', 'two_hander'],
    'comedy': ['abc_ensemble', 'two_hander', 'heist_plan'],
    'thriller': ['ticking_clock', 'heist_plan', 'mystery_fairplay'],
    'romance': ['two_hander', 'kishotenketsu', 'abc_ensemble'],
    'drama': ['revelation_spiral', 'two_hander', 'tragedy_dilemma'],
    'science fiction': ['ticking_clock', 'bottle', 'revelation_spiral'],
}


def history_path(project_id: str) -> Path:
    from story_os.projects import project_dir
    return project_dir(project_id) / 'metrics' / 'episodes.jsonl'


def load_history(project_id: str) -> List[str]:
    p = history_path(project_id)
    if not p.exists():
        return []
    with open(p, 'r', encoding='utf-8') as f:
        return [json.loads(l)['framework'] for l in f if l.strip()]


def record(project_id: str, episode_id: str, episode_number: int, framework_id: str,
           reason: str) -> None:
    p = history_path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'episode_id': episode_id, 'episode_number': episode_number,
                            'framework': framework_id, 'reason': reason}) + '\n')


def select_framework(milestone: Optional[Dict[str, Any]], history: List[str], *,
                     family: str = 'fiction', genre: str = '',
                     chooser: Optional[Callable[[List[Framework]], str]] = None
                     ) -> Tuple[str, str]:
    pool = [f for f in REGISTRY.values() if f.family == family]
    if not pool:
        return FAMILY_DEFAULT['fiction'], 'no family match'
    recent = history[-4:]
    allowed = [f for f in pool if (not history or f.id != history[-1])
               and recent.count(f.id) < 2] or pool
    m = milestone or {}
    text = ' '.join(str(m.get(k, '')) for k in ('arc_beat', 'purpose', 'must_payoff',
                                                'must_plant', 'dramatic_question')).lower()
    hard: List[str] = []
    if family == 'fiction':
        if 'mystery' in text or 'clue' in text or 'reveal' in text or 'who ' in text:
            hard.append('mystery_fairplay')
        role = m.get('structural_role')
        if role == 'climax':
            hard += ['ticking_clock', 'three_act']
        if role == 'low_point':
            hard.append('tragedy_dilemma')
        focus = len(m.get('character_focus') or [])
        if focus == 2:
            hard.append('two_hander')
        elif focus >= 3:
            hard.append('abc_ensemble')
    ids = [f.id for f in allowed]
    for h in hard:
        if h in ids:
            return h, f'rule match ({h}) from milestone'
    bias: List[str] = []
    for key, fws in GENRE_BIAS.items():
        if key in (genre or '').lower():
            bias += fws

    def rank(f):
        b = bias.index(f.id) if f.id in bias else 99
        last = max((i for i, h in enumerate(history) if h == f.id), default=-1)
        return (b, last)
    ranked = sorted(allowed, key=rank)
    top = [f for f in ranked if rank(f)[0] == rank(ranked[0])[0]][:3]
    if len(top) >= 2 and chooser is not None:
        pick = chooser(top)
        if pick in {f.id for f in top}:
            return pick, 'planner chose among ' + ', '.join(f.id for f in top)
    return ranked[0].id, ('genre bias' if rank(ranked[0])[0] < 99 else 'least recently used')


def llm_chooser(milestone: Optional[Dict[str, Any]]) -> Callable[[List[Framework]], str]:
    def choose(cands: List[Framework]) -> str:
        from story_os import llm
        opts = '\n'.join(f'- {f.id}: {f.name} ({", ".join(s.function for s in f.steps)})'
                         for f in cands)
        beat = (milestone or {}).get('arc_beat', '')
        try:
            out = llm.complete('planner', 'Pick the best episode framework. Reply with the id only.',
                               f'EPISODE: {beat}\nOPTIONS:\n{opts}', max_tokens=20,
                               temperature=0.0)
        except Exception:
            return cands[0].id
        return out.strip().split()[0].strip('`"\'.') if out.strip() else cands[0].id
    return choose


def render_framework_block(fw: Framework, minutes: float) -> str:
    lines = [f'FRAMEWORK FOR THIS EPISODE: {fw.name}. These are functions the episode '
             'must contain (not one scene each; map them onto as many scenes as the '
             'story needs, and set each card\'s "step" to the function id):']
    for s in fw.steps:
        lines.append(f'- {s.id}: {s.function} (~{round(s.share * minutes, 1)} min)')
    if fw.audio_notes:
        lines.append(f'Audio note: {fw.audio_notes}')
    return '\n'.join(lines)
