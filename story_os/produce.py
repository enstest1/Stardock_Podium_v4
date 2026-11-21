"""Idea -> finished episode for a project (GEN-001 + AUTO-001).

Owns ``create_podcast`` (proposal, identity, voices, profiles, theme) and
``produce_episode``: a resumable job (``story_os.jobs``) whose stages are
built from the project's capabilities:

  plan (season, once per project) -> premises (writers room, optional)
  -> structure -> cast -> outline (scene or segment cards) -> script
  -> edit (writers room, optional) -> lint + originality -> extract (canon)
  -> audio

Re-running with ``episode_id`` skips every stage whose inputs are unchanged;
the script stage resumes per scene (``drafts/scenes``), audio per line.
Writes ``episodes/<id>/production_report.json``.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from story_os import llm, projects

logger = logging.getLogger(__name__)


def create_podcast(idea: str, *, mode: Optional[str] = None,
                   title: Optional[str] = None,
                   minutes: Optional[int] = None,
                   overwrite: bool = False):
    """Propose and write a project from one sentence. Returns (config, identity, dir)."""
    config = projects.propose_project(idea, mode=mode, title=title, minutes=minutes)
    identity = projects.design_identity(config)
    pdir = projects.create_project(config, identity, overwrite=overwrite)
    try:
        from story_os.music import make_show_theme
        theme = make_show_theme(config.project_id)
    except Exception as e:  # never block creation on music
        theme = {'status': 'unavailable', 'reason': str(e)}
    identity.__dict__['_theme_status'] = theme
    return config, identity, pdir


def _cards_of(ep: Dict[str, Any]):
    return [s.get('card') or s.get('segment') or s.get('plot') for s in ep.get('scenes') or []]


def _lines_of(script: Dict[str, Any]):
    return [(l.get('line_id'), l.get('type'), l.get('character'), l.get('content'))
            for sc in script.get('scenes') or [] for l in sc.get('lines') or []]


def produce_episode(project_id: str, *, theme: Optional[str] = None,
                    minutes: Optional[int] = None,
                    audio: bool = True,
                    episode_id: Optional[str] = None,
                    season_episodes: int = 6,
                    force: Optional[str] = None) -> Dict[str, Any]:
    """Produce (or resume) one episode of ``project_id``."""
    from story_structure import get_story_structure
    from story_os.asyncio_compat import run_coro
    from story_os.flags import feature_enabled
    from story_os.jobs import Job

    project = projects.load_project(project_id)
    ss = get_story_structure()
    report: Dict[str, Any] = {'project_id': project_id, 'mode': project.mode, 'stages': {}}
    t0 = time.time()

    if not episode_id and project.capability('season_plan') != 'none':
        from story_os.roadmap import create_season, load_roadmap
        if load_roadmap(project_id, 1) is None:
            rm = create_season(project_id, 1, episodes=season_episodes)
            report['season_plan'] = {'type': rm.plan_type if rm else None,
                                     'episodes': len(rm.milestones) if rm else 0,
                                     'title': rm.title if rm else ''}

    existing = ss.get_episode(episode_id) if episode_id else None
    if episode_id and not existing:
        raise RuntimeError(f'Episode not found: {episode_id}')

    if existing is None:
        if not theme and feature_enabled('USE_WRITERS_ROOM', default=False):
            theme = _choose_premise(ss, project, minutes, report)
        started = time.time()
        episode = ss.generate_episode_structure({
            'project_id': project_id, 'theme': theme,
            'target_duration': minutes or project.episode_minutes})
        report['stages']['structure'] = {'seconds': round(time.time() - started, 1)}
        eid = episode['episode_id']
    else:
        eid = episode_id
        report['resumed'] = True
    report['episode_id'] = eid
    ep_dir = Path(ss.episodes_dir) / eid
    job = Job(ep_dir)
    job.acquire()
    order = ['cast', 'outline', 'script', 'edit', 'lint', 'extract', 'audio']
    if force:
        job.invalidate_from(order, force)

    def stage(name, fn, config=None, inputs=()):
        started = time.time()
        logger.info('=== stage %s ===', name)
        stale = job.state['stages'].get(name, {}).get('status') == 'stale'
        out = job.run_stage(name, fn, inputs=inputs, config=config, force=stale)
        report['stages'][name] = {'seconds': round(time.time() - started, 1),
                                  'skipped': out['skipped']}
        return out['result']

    try:
        cast = stage('cast', lambda: [c['name'] for c in ss.generate_character_cast(eid)],
                     config={'identity': projects.load_identity(project_id).model_dump()})
        report['stages']['cast']['characters'] = cast

        def outline():
            scenes = run_coro(ss.generate_scenes(eid))
            if not scenes:
                raise RuntimeError('Outline (scene/segment cards) failed; see log.')
            return {'scenes': len(scenes)}
        ep = ss.get_episode(eid)
        stage('outline', outline, config={'theme': ep.get('theme'),
                                          'arc_slot': ep.get('arc_slot'),
                                          'minutes': ep.get('target_duration_minutes'),
                                          'cast': cast})
        ep = ss.get_episode(eid)
        report['stages']['outline']['scenes'] = len(ep.get('scenes') or [])
        report['stages']['outline']['framework'] = (ep.get('metadata') or {}).get('framework')

        def write():
            ss.defer_canon = True
            try:
                script = ss.generate_episode_script(eid)
            finally:
                ss.defer_canon = False
            if not script or not script.get('scenes'):
                raise RuntimeError('Script generation failed; see log.')
            empty = sum(1 for sc in script['scenes'] if not sc.get('lines'))
            words = sum(len((l.get('content') or '').split()) for sc in script['scenes']
                        for l in sc.get('lines') or [] if l.get('type') in ('dialogue', 'narration'))
            if empty or not words:
                raise RuntimeError(f'Script incomplete: {empty} empty scene(s). Rerun '
                                   f'"python main.py produce-episode {project_id} --resume {eid}" '
                                   'after fixing the cause; finished scenes are kept.')
            return {'lines': sum(len(sc.get('lines') or []) for sc in script['scenes']),
                    'spoken_words': words}
        res = stage('script', write, config={'cards': _cards_of(ep)})
        report['stages']['script'].update(res or {})

        ep = ss.get_episode(eid)
        script = ep.get('script') or {}
        if feature_enabled('USE_WRITERS_ROOM', default=False):
            from story_os.writers_room import run_edit_round

            def edit():
                r = run_edit_round(eid)
                return {'patches': len(r['patches']), 'plan': r['plan']['status'],
                        'revised_scenes': r['revised']}
            res = stage('edit', edit, config={'lines': _lines_of(script)})
            report['stages']['edit'].update(res or {})
            ep = ss.get_episode(eid)
            script = ep.get('script') or {}

        def lint_and_metrics():
            from story_os import originality, writers_room
            from story_os.canon_store import CanonStore
            names = [c.get('name', '') for c in ep.get('characters') or []]
            findings = writers_room.lint(script, names,
                                         editorial=project.capability('editorial'),
                                         store=CanonStore.for_episode(ep))
            prev = [e.get('script') for e in ss.list_episodes()
                    if e.get('project_id') == project_id and e.get('episode_id') != eid
                    and e.get('script')]
            om = originality.metrics(script, names, prev)
            originality.record(project_id, eid, om)
            return {'lint': {s: sum(1 for f in findings if f['severity'] == s)
                             for s in ('error', 'warning', 'info')},
                    'lint_rules': sorted({f['rule'] for f in findings if f['severity'] != 'info'}),
                    'originality': {k: om[k] for k in ('distinct_2', 'self_repeat_4gram',
                                                       'slop_per_1k_words',
                                                       'cross_episode_jaccard', 'flags')}}
        res = stage('lint', lint_and_metrics, config={'lines': _lines_of(script)})
        report.update(res or {})

        def extract():
            ss._extract_canon(ep, script)
            from story_os.roadmap import mark_episode
            mark_episode(project_id, int(ep.get('season_number') or 1),
                         int(ep.get('episode_number') or 1), 'written')
            q = ep_dir / 'quality' / 'extraction_report.json'
            if q.exists():
                r = json.loads(q.read_text(encoding='utf-8'))
                return {'accepted': r.get('accepted'), 'rejected': r.get('rejected')}
            return {}
        res = stage('extract', extract, config={'lines': _lines_of(script)})
        report['stages']['extract'].update(res or {})

        if audio:
            from audio_pipeline import generate_episode_audio

            def render():
                meta = generate_episode_audio(eid, {})
                if meta.get('error'):
                    raise RuntimeError(f"Audio failed: {meta['error']}")
                out = {k: meta.get(k) for k in (
                    'full_episode_file', 'total_duration', 'lines_rendered',
                    'lines_from_cache', 'lines_failed', 'cues_placed', 'loudness',
                    'blocking', 'assets_not_cleared_for_commercial_use')}
                out['cues_missing'] = len(meta.get('cues_missing') or [])
                return out
            fmt = projects.load_format(project_id)
            res = stage('audio', render, inputs=[projects.voices_path(project_id)],
                        config={'lines': _lines_of(script),
                                'theme': [fmt.theme_intro_path, fmt.theme_outro_path,
                                          fmt.intro_template, fmt.outro_template]})
            report['stages']['audio'].update(res or {})
    finally:
        job.release()
    report['total_seconds'] = round(time.time() - t0, 1)
    report['llm_usage'] = llm.usage_totals
    with open(ep_dir / 'production_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
    return report


def _choose_premise(ss, project, minutes, report) -> Optional[str]:
    from story_os.canon_store import CanonStore
    from story_os.roadmap import milestone_for
    from story_os.writers_room import choose_premise
    pid = project.project_id
    n_next = 1 + max([e.get('episode_number', 0) for e in ss.list_episodes()
                      if e.get('project_id') == pid], default=0)
    slot = milestone_for(pid, 1, n_next) or {}
    identity = projects.load_identity(pid)
    ctx = (projects.format_brief(project, projects.load_format(pid), identity)
           + f"\nCAST: {', '.join(m.name for m in identity.cast)}"
           + f"\nSEASON MILESTONE FOR EPISODE {n_next}: {slot.get('arc_beat', project.idea)}"
           + f"\nLENGTH: {minutes or project.episode_minutes} minutes")
    started = time.time()
    premise = choose_premise(ctx, CanonStore(projects.project_dir(pid)))
    report['stages']['premises'] = {'seconds': round(time.time() - started, 1),
                                    'chosen': premise}
    return premise['logline'] if premise else None
