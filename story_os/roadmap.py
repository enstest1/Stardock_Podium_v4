"""Season plans, rolling replanning, series plan, context assembler.

Covers STORYOS-002 (unified, versioned roadmap), PLAN-001 (season creation
with commitments, mysteries and validation), PLAN-002 (replanning after an
approved episode), PLAN-003 (series directions filtered by canon) and
STORYOS-003 (one context assembler for story prompts).

Files under ``data/projects/<id>/seasons/<N>/``:
  roadmap.json            current plan (arc | slate | curriculum), ``version``
  roadmap_history/vNNNN.json   every saved version, never deleted
  mystery_solutions.json  answers + required clues (planning prompts only)
  blocked.json            written when a replan conflicts with a locked commitment
A plan is never evidence that something happened; canon lives in the ledger.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

FROZEN_STATUSES = ('written', 'approved')


class EpisodeMilestone(BaseModel):
    episode_number: int
    title: str = ''
    purpose: str = ''                       # what this episode does for the season
    arc_beat: str = ''                      # premise / beat text
    dramatic_question: str = ''
    structural_role: Literal['inciting', 'midpoint_reversal', 'low_point',
                             'climax', 'none'] = 'none'
    obstacle_type: Optional[str] = None
    character_focus: List[str] = Field(default_factory=list)
    must_plant: List[str] = Field(default_factory=list)
    must_develop: List[str] = Field(default_factory=list)
    must_payoff: List[str] = Field(default_factory=list)
    commitment: Literal['locked', 'guided', 'open'] = 'guided'
    status: Literal['planned', 'written', 'approved'] = 'planned'
    tension_level: str = 'rising'
    objectives: List[str] = Field(default_factory=list)   # curriculum


class Clue(BaseModel):
    clue: str
    by_episode: int


class Mystery(BaseModel):
    mystery_id: str
    question: str
    solution: str
    required_clues: List[Clue] = Field(default_factory=list)
    red_herrings: List[str] = Field(default_factory=list)
    payoff_episode: int


class RoadmapChange(BaseModel):
    version: int
    episode_number: int
    field: str
    before: Any = None
    after: Any = None
    reason: str
    triggered_by_event_id: Optional[str] = None
    at: float = Field(default_factory=time.time)


class SeasonRoadmap(BaseModel):
    schema_version: int = 1
    project_id: str
    season: int
    plan_type: Literal['arc', 'slate', 'curriculum'] = 'arc'
    version: int = 0
    title: str = ''
    season_question: str = ''
    opposition: str = ''
    theme: str = ''
    locked_commitments: List[str] = Field(default_factory=list)
    milestones: List[EpisodeMilestone] = Field(default_factory=list)
    changes: List[RoadmapChange] = Field(default_factory=list)


class LockedCommitmentConflict(RuntimeError):
    pass


# ------------------------------------------------------------- storage ----

def season_dir(project_id: str, season: int) -> Path:
    from story_os.projects import project_dir
    return project_dir(project_id) / 'seasons' / str(season)


def load_roadmap(project_id: str, season: int) -> Optional[SeasonRoadmap]:
    p = season_dir(project_id, season) / 'roadmap.json'
    if not p.exists():
        return None
    with open(p, 'r', encoding='utf-8') as f:
        return SeasonRoadmap.model_validate(json.load(f))


def save_roadmap(rm: SeasonRoadmap, reason: str) -> SeasonRoadmap:
    from story_os.projects import atomic_write_json
    rm.version += 1
    d = season_dir(rm.project_id, rm.season)
    atomic_write_json(d / 'roadmap_history' / f'v{rm.version:04d}.json',
                      {'reason': reason, **rm.model_dump()})
    atomic_write_json(d / 'roadmap.json', rm.model_dump())
    return rm


def restore_roadmap(project_id: str, season: int, version: int) -> SeasonRoadmap:
    p = season_dir(project_id, season) / 'roadmap_history' / f'v{version:04d}.json'
    with open(p, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.pop('reason', None)
    rm = SeasonRoadmap.model_validate(data)
    current = load_roadmap(project_id, season)
    rm.version = current.version if current else rm.version
    return save_roadmap(rm, f'restored v{version:04d}')


def load_mysteries(project_id: str, season: int) -> List[Mystery]:
    p = season_dir(project_id, season) / 'mystery_solutions.json'
    if not p.exists():
        return []
    with open(p, 'r', encoding='utf-8') as f:
        return [Mystery.model_validate(m) for m in json.load(f)]


def milestone_for(project_id: str, season: int, episode: int) -> Optional[Dict[str, Any]]:
    """Legacy ``arc_slot`` dict shape plus the new fields (or None)."""
    rm = load_roadmap(project_id, season)
    if rm is None:
        return None
    for m in rm.milestones:
        if m.episode_number == episode:
            d = m.model_dump()
            d.update({'arc_title': rm.title, 'arc_summary': rm.season_question,
                      'arc_importance': 'central' if m.structural_role != 'none' else 'supporting',
                      'roadmap_version': rm.version, 'plan_type': rm.plan_type})
            return d
    return None


# ---------------------------------------------------------- validation ----

def validate_roadmap(rm: SeasonRoadmap, mysteries: List[Mystery],
                     cast: List[str]) -> List[str]:
    issues: List[str] = []
    nums = [m.episode_number for m in rm.milestones]
    if nums != list(range(1, len(nums) + 1)):
        issues.append(f'episode numbers must be 1..{len(nums)} in order, got {nums}')
    if rm.plan_type != 'arc':
        if rm.plan_type == 'curriculum':
            seen: List[str] = []
            for m in rm.milestones:
                for o in m.objectives:
                    if o in seen:
                        issues.append(f'objective {o!r} scheduled twice')
                    seen.append(o)
        return issues
    n = len(rm.milestones)
    roles = {m.structural_role: m.episode_number for m in rm.milestones
             if m.structural_role != 'none'}
    if n >= 4:
        if 'midpoint_reversal' not in roles:
            issues.append('no midpoint_reversal milestone')
        elif not (n * 0.3 <= roles['midpoint_reversal'] <= n * 0.75):
            issues.append('midpoint_reversal is not near the middle')
        if roles.get('climax') not in (n, n - 1):
            issues.append('climax must be the last or second-to-last episode')
        if roles.get('inciting', 1) > max(2, n // 3):
            issues.append('inciting milestone comes too late')
    if not rm.season_question.strip():
        issues.append('season_question is empty')
    known = {c.strip().lower() for c in cast if c} | {c.split()[0].lower() for c in cast if c}
    for m in rm.milestones:
        for name in m.character_focus:
            if known and name.strip().lower() not in known:
                issues.append(f'episode {m.episode_number}: unknown character {name!r}')
    for my in mysteries:
        if not 1 <= my.payoff_episode <= n:
            issues.append(f'{my.mystery_id}: payoff episode {my.payoff_episode} out of range')
        for c in my.required_clues:
            if c.by_episode >= my.payoff_episode:
                issues.append(f'{my.mystery_id}: clue {c.clue!r} scheduled at or after its payoff')
        if len(my.required_clues) < 2:
            issues.append(f'{my.mystery_id}: needs at least two fair-play clues')
    return issues


# ------------------------------------------------------ season creation ----

def _ask(system: str, user: str, max_tokens: int) -> Dict[str, Any]:
    from story_os import llm
    from story_os.projects import _json_from
    return _json_from(llm.complete('planner', system, user, json=True,
                                   max_tokens=max_tokens, temperature=0.7))


ARC_SCHEMA = """{"title": "season title", "season_question": "the question the season answers",
 "opposition": "the force that resists", "theme": "...",
 "locked_commitments": ["2-4 things that must happen, e.g. 'E8: Nora learns why June left'"],
 "mysteries": [{"mystery_id": "M1", "question": "...", "solution": "the true answer",
   "required_clues": [{"clue": "...", "by_episode": 2}], "red_herrings": ["..."], "payoff_episode": 7}],
 "milestones": [{"episode_number": 1, "title": "...", "purpose": "...", "arc_beat": "what happens",
   "dramatic_question": "...", "structural_role": "inciting|midpoint_reversal|low_point|climax|none",
   "obstacle_type": "person|nature|society|self|mystery", "character_focus": ["Name"],
   "must_plant": ["..."], "must_develop": ["..."], "must_payoff": ["..."],
   "commitment": "locked|guided|open", "tension_level": "low|rising|high|peak"}]}"""


def create_season(project_id: str, season: int = 1, episodes: int = 8,
                  arc_prompt: Optional[str] = None) -> Optional[SeasonRoadmap]:
    """PLAN-001: one plan per ``season_plan`` capability; validated."""
    from story_os import projects
    project = projects.load_project(project_id)
    kind = project.capability('season_plan')
    if kind == 'none':
        return None
    identity = projects.load_identity(project_id)
    fmt = projects.load_format(project_id)
    cast = [m.name for m in identity.cast]
    brief = projects.format_brief(project, fmt, identity)
    system = ('You are the head writer of an original audio series. You plan '
              'seasons that keep promises to the audience. JSON only.')
    base = (f'SHOW: {brief}\nIDEA: {project.idea}\nCAST: {", ".join(cast)}\n'
            f'SEASON {season}, {episodes} episodes of {project.episode_minutes} minutes.\n'
            + (f'SEASON DIRECTION FROM THE SHOWRUNNER: {arc_prompt}\n' if arc_prompt else ''))
    if kind == 'arc':
        user = (base + 'Plan the season arc. Mark 2-4 milestones commitment "locked" '
                '(the spine), the rest "guided" or "open". Every mystery has a true '
                'solution and at least two clues planted before its payoff.\n'
                'Return JSON:\n' + ARC_SCHEMA)
    elif kind == 'slate':
        user = (base + 'Plan a slate of self-contained episodes around the show '
                'theme. No two episodes share the same protagonist type, obstacle or '
                'twist. Return JSON: {"title": "...", "theme": "...", "season_question": '
                '"what ties the season together", "milestones": [{"episode_number": 1, '
                '"title": "...", "arc_beat": "premise", "obstacle_type": "...", '
                '"commitment": "open"}], "mysteries": []}')
    else:   # curriculum
        user = (base + 'Plan a curriculum: objectives first, then episodes. Return JSON: '
                '{"title": "...", "season_question": "what the listener will be able to '
                'do", "milestones": [{"episode_number": 1, "title": "...", "arc_beat": '
                '"topic", "objectives": ["..."]}], "mysteries": []}')
    feedback = ''
    last: List[str] = []
    for attempt in (1, 2):
        try:
            data = _ask(system, user + feedback, 5000)
            mysteries = [Mystery.model_validate(m) for m in data.pop('mysteries', []) or []]
            ms = data.pop('milestones', [])
            rm = SeasonRoadmap(project_id=project_id, season=season, plan_type=kind,
                               milestones=[EpisodeMilestone.model_validate(m) for m in ms],
                               **{k: v for k, v in data.items() if k in SeasonRoadmap.model_fields
                                  and k not in ('project_id', 'season', 'plan_type', 'milestones')})
            last = validate_roadmap(rm, mysteries, cast)
        except (ValueError, ValidationError) as e:
            last = [f'invalid JSON or schema: {str(e)[:300]}']
        if not last:
            from story_os.projects import atomic_write_json
            save_roadmap(rm, 'created')
            if mysteries:
                atomic_write_json(season_dir(project_id, season) / 'mystery_solutions.json',
                                  [m.model_dump() for m in mysteries])
            return rm
        logger.warning('Season plan attempt %s rejected: %s', attempt, last[:6])
        feedback = ('\n\nYOUR PREVIOUS PLAN WAS REJECTED. Fix these problems and return '
                    'the whole JSON again:\n- ' + '\n- '.join(last[:12]))
    raise RuntimeError('Season plan failed validation twice: ' + '; '.join(last))


# ------------------------------------------------------------ replanning ----

def mark_episode(project_id: str, season: int, episode: int, status: str) -> None:
    rm = load_roadmap(project_id, season)
    if rm is None:
        return
    for m in rm.milestones:
        if m.episode_number == episode and m.status != status:
            m.status = status
            save_roadmap(rm, f'episode {episode} {status}')
            return


def apply_changes(rm: SeasonRoadmap, proposals: List[Dict[str, Any]],
                  max_changed: float = 0.4) -> List[RoadmapChange]:
    """Apply only allowed changes (property: frozen/locked never change)."""
    editable = {'title', 'purpose', 'arc_beat', 'dramatic_question', 'obstacle_type',
                'character_focus', 'must_plant', 'must_develop', 'must_payoff',
                'tension_level'}
    by_num = {m.episode_number: m for m in rm.milestones}
    future = [m for m in rm.milestones if m.status not in FROZEN_STATUSES]
    budget = max(1, int(len(future) * max_changed))
    touched: set = set()
    applied: List[RoadmapChange] = []
    for p in proposals:
        m = by_num.get(int(p.get('episode_number', -1) or -1))
        field = p.get('field')
        if m is None or field not in editable or not (p.get('reason') or '').strip():
            continue
        if m.status in FROZEN_STATUSES:
            continue
        if m.commitment == 'locked':
            raise LockedCommitmentConflict(
                f'episode {m.episode_number} is locked; proposal: {p}')
        if m.episode_number not in touched and len(touched) >= budget:
            continue
        before = getattr(m, field)
        after = p.get('after')
        if isinstance(before, list) and not isinstance(after, list):
            after = [after] if after else []
        if before == after:
            continue
        setattr(m, field, after)
        touched.add(m.episode_number)
        applied.append(RoadmapChange(version=rm.version + 1, episode_number=m.episode_number,
                                     field=field, before=before, after=after,
                                     reason=p['reason'],
                                     triggered_by_event_id=p.get('triggered_by_event_id')))
    return applied


def replan_season(project_id: str, season: int, approved_episode: int,
                  max_changed: float = 0.4) -> Dict[str, Any]:
    """PLAN-002: adjust unwritten, unlocked milestones to what canon now says."""
    from story_os.canon_store import CanonStore
    from story_os import projects
    rm = load_roadmap(project_id, season)
    if rm is None or rm.plan_type != 'arc':
        return {'status': 'skipped', 'reason': 'no arc roadmap'}
    store = CanonStore(projects.project_dir(project_id))
    canon = store.continuity_brief(limit=25)
    future = [m for m in rm.milestones if m.status not in FROZEN_STATUSES]
    if not future or not canon.strip():
        return {'status': 'nothing to do'}
    plan_lines = '\n'.join(
        f"E{m.episode_number} [{m.commitment}] {m.title}: {m.arc_beat} | plant {m.must_plant} "
        f"| develop {m.must_develop} | payoff {m.must_payoff}" for m in future)
    system = ('You are the head writer revising the rest of a season after an episode '
              'was approved. Change only what canon makes necessary or newly possible. '
              'JSON only.')
    user = (f'CANON SO FAR:\n{canon}\n\nREMAINING PLAN:\n{plan_lines}\n\n'
            f'LOCKED COMMITMENTS (never change): {rm.locked_commitments}\n'
            'Propose at most a few changes to guided/open milestones. Every change cites '
            'the canon id that triggered it. If nothing needs to change return an empty list.\n'
            'Return JSON: {"changes": [{"episode_number": 5, "field": "arc_beat|purpose|'
            'must_plant|must_develop|must_payoff|dramatic_question|title|character_focus", '
            '"after": "...", "reason": "...", "triggered_by_event_id": "EV-..."}]}')
    data = _ask(system, user, 2500)
    try:
        applied = apply_changes(rm, data.get('changes') or [], max_changed)
    except LockedCommitmentConflict as e:
        from story_os.projects import atomic_write_json
        atomic_write_json(season_dir(project_id, season) / 'blocked.json',
                          {'at': time.time(), 'reason': str(e)})
        return {'status': 'blocked', 'reason': str(e)}
    if not applied:
        return {'status': 'unchanged'}
    identity = projects.load_identity(project_id)
    issues = validate_roadmap(rm, load_mysteries(project_id, season),
                              [m.name for m in identity.cast])
    if issues:
        return {'status': 'rejected', 'issues': issues}
    rm.changes.extend(applied)
    save_roadmap(rm, f'replan after episode {approved_episode}')
    return {'status': 'changed', 'changes': [c.model_dump() for c in applied]}


# ----------------------------------------------------------- series plan ----

def series_directions(project_id: str, directions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """PLAN-003: keep directions whose ``requires_canon`` event ids are canon."""
    from story_os.canon_store import CanonStore
    from story_os import projects
    ids = {e['event_id'] for e in CanonStore(projects.project_dir(project_id)).query('events')}
    return [d for d in directions if set(d.get('requires_canon') or []) <= ids]


def propose_series_plan(project_id: str) -> List[Dict[str, Any]]:
    from story_os.canon_store import CanonStore
    from story_os import projects
    store = CanonStore(projects.project_dir(project_id))
    system = 'You are a showrunner proposing where an audio series goes next. JSON only.'
    user = (f'CANON:\n{store.continuity_brief(30)}\n\nPropose 2-4 directions for the next '
            'season. Each lists the series promises it pays and the canon event ids it '
            'depends on. Return JSON: {"directions": [{"title": "...", "pitch": "...", '
            '"pays_promises": ["PR-..."], "requires_canon": ["EV-..."]}]}')
    data = _ask(system, user, 2000)
    kept = series_directions(project_id, data.get('directions') or [])
    from story_os.projects import atomic_write_json
    atomic_write_json(projects.project_dir(project_id) / 'series_plan.json',
                      {'at': time.time(), 'directions': kept})
    return kept


# ------------------------------------------------------------- assembler ----

def _clip(text: str, budget_tokens: int) -> str:
    limit = budget_tokens * 4
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind('. '), cut.rfind('\n'))
    return cut[: end + 1] if end > limit // 2 else cut


def assemble_context(episode: Dict[str, Any], purpose: Literal['plan', 'write']) -> str:
    """STORYOS-003: the one place story prompts get show context from."""
    from story_os import projects
    pid = episode.get('project_id')
    if not pid:
        return ''
    project = projects.load_project(pid)
    cap = project.capability
    season = int(episode.get('season_number') or 1)
    n = int(episode.get('episode_number') or 1)
    parts: List[str] = []
    ms = milestone_for(pid, season, n)
    if ms:
        lines = [f"SEASON PLAN ({ms['plan_type']}): {ms.get('arc_title', '')} - {ms.get('arc_summary', '')}",
                 f"THIS EPISODE (E{n}, {ms['commitment']}): {ms.get('title', '')}: {ms.get('arc_beat', '')}"]
        if ms.get('purpose'):
            lines.append(f"Purpose in the season: {ms['purpose']}")
        if ms.get('dramatic_question'):
            lines.append(f"Dramatic question: {ms['dramatic_question']}")
        for k in ('must_plant', 'must_develop', 'must_payoff'):
            if ms.get(k):
                lines.append(f"{k.replace('_', ' ').title()}: " + '; '.join(ms[k]))
        parts.append(_clip('\n'.join(lines), 500))
    if cap('continuity') in ('canon_full', 'canon_light', 'per_episode', 'per_story'):
        from story_os.canon_store import CanonStore
        store = CanonStore.for_episode(episode)
        if store is not None:
            brief = store.continuity_brief()
            if brief:
                parts.append(_clip(brief, 900))
    if purpose == 'plan' and cap('season_plan') == 'arc':
        sols = [m for m in load_mysteries(pid, season)
                if any(c.by_episode == n for c in m.required_clues) or m.payoff_episode == n]
        if sols:
            parts.append('SECRET PLANNING NOTES (never state outright):\n' + '\n'.join(
                f"- {m.question} -> truth: {m.solution}; clues due now: "
                + '; '.join(c.clue for c in m.required_clues if c.by_episode == n)
                + (' (PAY OFF THIS EPISODE)' if m.payoff_episode == n else '')
                for m in sols))
    return '\n\n'.join(parts)
