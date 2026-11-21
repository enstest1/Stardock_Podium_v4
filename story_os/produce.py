"""Idea -> finished episode for a project (GEN-001 step 3, minimal runner).

Owns: ``create_podcast`` (proposal, identity, voices, project files) and
``produce_episode`` (structure -> cast -> scene cards -> script -> audio),
writing ``episodes/<id>/production_report.json``.

This is the thin, linear precursor of AUTO-001: no resume or stage hashing
yet. Each stage reuses the existing StoryStructure / AudioPipeline code.
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
    """Propose and write a project from one sentence. Returns (config, dir)."""
    config = projects.propose_project(idea, mode=mode, title=title,
                                      minutes=minutes)
    identity = projects.design_identity(config)
    pdir = projects.create_project(config, identity, overwrite=overwrite)
    try:
        from story_os.music import make_show_theme
        theme = make_show_theme(config.project_id)
    except Exception as e:  # never block creation on music
        theme = {'status': 'unavailable', 'reason': str(e)}
    identity.__dict__['_theme_status'] = theme
    return config, identity, pdir


def produce_episode(project_id: str, *, theme: Optional[str] = None,
                    minutes: Optional[int] = None,
                    audio: bool = True,
                    episode_id: Optional[str] = None,
                    season_episodes: int = 6) -> Dict[str, Any]:
    """Run every stage for one new episode of ``project_id``.

    With ``episode_id`` of an existing episode that already has scene cards,
    only the script and audio stages run again (resume after a failure).
    """
    from story_structure import get_story_structure
    from story_os.asyncio_compat import run_coro

    project = projects.load_project(project_id)
    if not projects.is_fiction(project):
        raise RuntimeError(
            f"Mode {project.mode!r} needs segment cards (GEN-002), which are "
            "not implemented yet. Recreate with a fiction --mode "
            "(standalone_drama, anthology, episodic_fiction, serialized_fiction).")
    ss = get_story_structure()
    report: Dict[str, Any] = {'project_id': project_id, 'stages': {}}
    if not episode_id and project.capability('season_plan') != 'none':
        from story_os.roadmap import create_season, load_roadmap
        if load_roadmap(project_id, 1) is None:
            rm = create_season(project_id, 1, episodes=season_episodes)
            report['season_plan'] = {'type': rm.plan_type if rm else None,
                                     'episodes': len(rm.milestones) if rm else 0,
                                     'title': rm.title if rm else ''}
    t0 = time.time()

    def stage(name, fn):
        started = time.time()
        logger.info('=== stage %s ===', name)
        out = fn()
        report['stages'][name] = {'seconds': round(time.time() - started, 1)}
        return out

    existing = ss.get_episode(episode_id) if episode_id else None
    if existing and existing.get('scenes'):
        eid = episode_id
        report['episode_id'] = eid
        report['resumed'] = True
    else:
        episode = stage('structure', lambda: ss.generate_episode_structure({
            'project_id': project_id, 'theme': theme,
            'target_duration': minutes or project.episode_minutes}))
        eid = episode['episode_id']
        report['episode_id'] = eid
        cast = stage('cast', lambda: ss.generate_character_cast(eid))
        report['stages']['cast']['characters'] = [c['name'] for c in cast]
        scenes = stage('scene_cards', lambda: run_coro(ss.generate_scenes(eid)))
        if not scenes:
            raise RuntimeError('Scene planning failed (see log).')
        report['stages']['scene_cards']['scenes'] = len(scenes)
    script = stage('script', lambda: ss.generate_episode_script(eid))
    if not script or not script.get('scenes'):
        raise RuntimeError('Script generation failed (see log).')
    lines = [ln for sc in script['scenes'] for ln in sc.get('lines', [])]
    words = sum(len((ln.get('content') or '').split()) for ln in lines
                if ln.get('type') in ('dialogue', 'narration'))
    report['stages']['script'].update({
        'lines': len(lines), 'spoken_words': words,
        'empty_scenes': sum(1 for sc in script['scenes'] if not sc.get('lines'))})
    if words == 0 or report['stages']['script']['empty_scenes']:
        raise RuntimeError(
            f"Script incomplete: {report['stages']['script']['empty_scenes']} of "
            f"{len(script['scenes'])} scenes are empty (LLM errors in the log). "
            f"Fix the cause, then: python main.py write-and-render {eid}")
    if audio:
        from audio_pipeline import generate_episode_audio
        meta = stage('audio', lambda: generate_episode_audio(eid, {}))
        if meta.get('error'):
            raise RuntimeError(f"Audio failed: {meta['error']}")
        report['stages']['audio'].update({
            'file': meta.get('full_episode_file'),
            'scenes_ok': f"{meta.get('scenes_successful')}/{meta.get('scenes_generated')}"})
    report['total_seconds'] = round(time.time() - t0, 1)
    report['llm_usage'] = llm.usage_totals
    ep_dir = Path(ss.episodes_dir) / eid
    with open(ep_dir / 'production_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    return report
