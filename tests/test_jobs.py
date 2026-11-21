"""AUTO-001 (T13): stage skipping, failure state, per-scene resume."""
import json
import os
import time
from unittest.mock import patch

import pytest

from story_os import llm
from story_os.jobs import Job


def test_stage_skips_on_same_inputs_and_reruns_on_change(tmp_path):
    job = Job(tmp_path)
    calls = []
    run = lambda: calls.append(1) or {'ok': True}
    assert job.run_stage('a', run, config={'x': 1})['skipped'] is False
    assert Job(tmp_path).run_stage('a', run, config={'x': 1})['skipped'] is True
    assert Job(tmp_path).run_stage('a', run, config={'x': 2})['skipped'] is False
    assert len(calls) == 2

    def boom():
        raise RuntimeError('fail')
    with pytest.raises(RuntimeError):
        job.run_stage('b', boom)
    assert Job(tmp_path).state['stages']['b']['status'] == 'failed'
    job.invalidate_from(['a', 'b'], 'a')
    assert Job(tmp_path).state['stages']['a']['status'] == 'stale'


def test_lock_and_stale_takeover(tmp_path):
    a = Job(tmp_path)
    a.acquire()
    with pytest.raises(RuntimeError):
        Job(tmp_path).acquire()
    old = time.time() - 3 * 3600
    os.utime(a.lock, (old, old))
    Job(tmp_path).acquire()                       # stale lock taken over


@pytest.fixture
def episode(tmp_path):
    from story_os import projects
    from story_os.project_models import ProjectConfig
    from story_os.scene_cards import cards_to_scenes, parse_cards
    from tests.test_scene_cards import cards_json
    with patch('config.paths.DATA_DIR', tmp_path), \
            patch('story_structure.get_mem0_client'), \
            patch('story_structure.get_knowledge_context') as kn:
        kn.return_value.series_bible = {}
        cfg = ProjectConfig(project_id='p', show_id='p', title='P', idea='i',
                            mode='standalone_drama', episode_minutes=6)
        projects.create_project(cfg, projects.Identity.model_validate(
            {'cast': [{'name': 'Mara Quill'}, {'name': 'Ilen Voss'}]}), casting='simple')
        from story_structure import StoryStructure
        ss = StoryStructure(episodes_dir=str(tmp_path / 'eps'))
        ep = ss.generate_episode_structure({'project_id': 'p', 'title': 'T'})
        ep['characters'] = [{'name': 'Mara Quill'}, {'name': 'Ilen Voss'}]
        cards, _ = parse_cards(cards_json())
        ep['scenes'] = cards_to_scenes(cards, 360)
        ss._save_episode(ep)
        yield ss, ep
    llm.set_test_backend(None)


def test_script_resumes_at_failed_scene_and_after_changed_card(episode):
    ss, ep = episode
    calls = []
    fail_at = {'n': 5}

    def writer(role, system, user, **kw):
        n = int(user.split('This is scene ')[1].split(' ')[0])
        calls.append(n)
        if n == fail_at['n']:
            raise RuntimeError('provider down')
        return f'MARA: Line {n}.\n\nILEN: Reply {n}.'
    llm.set_test_backend(writer)
    ss.defer_canon = True
    first = ss.generate_episode_script(ep['episode_id'])
    assert calls == [1, 2, 3, 4, 5, 6]
    assert not first['scenes'][4]['lines']
    calls.clear()
    fail_at['n'] = -1
    second = ss.generate_episode_script(ep['episode_id'])
    assert calls == [5, 6]                         # 1-4 reused
    ids_1 = [l['line_id'] for l in second['scenes'][0]['lines']]
    assert ids_1 == [l['line_id'] for l in first['scenes'][0]['lines']]   # stable ids
    calls.clear()
    ep2 = ss.get_episode(ep['episode_id'])
    ep2['scenes'][2]['card']['turn'] = 'a completely different turn'
    ss._save_episode(ep2)
    ss.generate_episode_script(ep['episode_id'])
    assert calls == [3, 4, 5, 6]                   # changed card and everything after
    calls.clear()
    ss.generate_episode_script(ep['episode_id'])
    assert calls == []                             # nothing changed -> no calls
