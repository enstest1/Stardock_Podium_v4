"""STORYOS-002/003, PLAN-001..003: roadmap, validation, replanning, assembler."""
import json
import random
from unittest.mock import patch

import pytest

from story_os import llm, projects, roadmap
from story_os.project_models import ProjectConfig


def ms(n, role='none', commit='guided', **kw):
    return {'episode_number': n, 'title': f'T{n}', 'arc_beat': f'beat {n}',
            'structural_role': role, 'commitment': commit, **kw}


def arc_reply(n=6, midpoint=True, clue_at=2, payoff=5):
    roles = {1: 'inciting', n: 'climax'}
    if midpoint:
        roles[n // 2] = 'midpoint_reversal'
    return {'title': 'S1', 'season_question': 'Will Ada find her brother?',
            'opposition': 'the sea', 'locked_commitments': ['E6: the truth'],
            'mysteries': [{'mystery_id': 'M1', 'question': 'Who calls?',
                           'solution': 'the drowned twin', 'payoff_episode': payoff,
                           'required_clues': [{'clue': 'his song', 'by_episode': clue_at},
                                              {'clue': 'his watch', 'by_episode': 1}]}],
            'milestones': [ms(i, roles.get(i, 'none'), 'locked' if i == n else 'guided',
                              character_focus=['Ada']) for i in range(1, n + 1)]}


@pytest.fixture
def project(tmp_path):
    with patch('config.paths.DATA_DIR', tmp_path):
        cfg = ProjectConfig(project_id='lamp', show_id='lamp', title='The Lamp',
                            idea='a keeper hears the radio', mode='serialized_fiction')
        ident = projects.Identity.model_validate({'cast': [{'name': 'Ada Moreau'}]})
        projects.create_project(cfg, ident, casting='simple')
        yield cfg
    llm.set_test_backend(None)


def test_validator_rejects_seeded_bad_roadmaps():
    def rm(data):
        d = dict(data)
        mys = [roadmap.Mystery.model_validate(m) for m in d.pop('mysteries')]
        mil = [roadmap.EpisodeMilestone.model_validate(m) for m in d.pop('milestones')]
        return roadmap.SeasonRoadmap(project_id='p', season=1, milestones=mil,
                                     **{k: v for k, v in d.items()}), mys
    good, mys = rm(arc_reply())
    assert roadmap.validate_roadmap(good, mys, ['Ada Moreau']) == []
    no_mid, mys = rm(arc_reply(midpoint=False))
    assert 'no midpoint_reversal milestone' in roadmap.validate_roadmap(no_mid, mys, ['Ada Moreau'])
    dup, mys = rm(arc_reply())
    dup.milestones[2].episode_number = 2
    assert any('episode numbers' in i for i in roadmap.validate_roadmap(dup, mys, ['Ada Moreau']))
    late, mys = rm(arc_reply(clue_at=5, payoff=5))
    assert any('at or after its payoff' in i for i in roadmap.validate_roadmap(late, mys, ['Ada Moreau']))


def test_create_season_retries_once_then_saves(project):
    replies = [arc_reply(midpoint=False), arc_reply()]
    calls = []

    def fake(role, system, user, **kw):
        calls.append(user)
        return json.dumps(replies[len(calls) - 1])
    llm.set_test_backend(fake)
    rm = roadmap.create_season('lamp', 1, 6)
    assert len(calls) == 2 and 'REJECTED' in calls[1]
    assert rm.version == 1 and len(rm.milestones) == 6
    assert (roadmap.season_dir('lamp', 1) / 'mystery_solutions.json').exists()
    assert roadmap.milestone_for('lamp', 1, 3)['arc_beat'] == 'beat 3'


def test_create_season_fails_after_two_bad_plans(project):
    llm.set_test_backend(lambda *a, **k: json.dumps(arc_reply(midpoint=False)))
    with pytest.raises(RuntimeError):
        roadmap.create_season('lamp', 1, 6)


def test_replan_property_frozen_and_locked_never_change(project):
    llm.set_test_backend(lambda *a, **k: json.dumps(arc_reply()))
    roadmap.create_season('lamp', 1, 6)
    rng = random.Random(7)
    fields = ['arc_beat', 'purpose', 'must_plant', 'title', 'commitment', 'status']
    for trial in range(60):
        rm = roadmap.load_roadmap('lamp', 1)
        rm.milestones[0].status = 'approved'
        rm.milestones[1].status = 'written'
        before = {m.episode_number: m.model_dump() for m in rm.milestones}
        props = [{'episode_number': rng.randint(1, 6), 'field': rng.choice(fields),
                  'after': f'x{trial}', 'reason': rng.choice(['', 'canon says so']),
                  'triggered_by_event_id': 'EV-1'} for _ in range(rng.randint(1, 5))]
        try:
            applied = roadmap.apply_changes(rm, props)
        except roadmap.LockedCommitmentConflict:
            applied = []
        for m in rm.milestones:
            if m.episode_number in (1, 2) or before[m.episode_number]['commitment'] == 'locked':
                assert m.model_dump() == before[m.episode_number]
            assert m.commitment == before[m.episode_number]['commitment']
            assert m.status == before[m.episode_number]['status']
        assert all(c.reason and c.triggered_by_event_id for c in applied)
        assert len({c.episode_number for c in applied}) <= max(1, int(4 * 0.4))


def test_slate_curriculum_and_none(tmp_path):
    with patch('config.paths.DATA_DIR', tmp_path):
        for mode, reply, kind in (
                ('anthology', {'title': 'A', 'season_question': 'q', 'milestones':
                               [ms(1), ms(2)]}, 'slate'),
                ('educational', {'title': 'E', 'season_question': 'q', 'milestones':
                                 [ms(1, objectives=['o1']), ms(2, objectives=['o2'])]},
                 'curriculum')):
            cfg = ProjectConfig(project_id=mode, show_id=mode, title=mode, idea='i', mode=mode)
            projects.create_project(cfg, projects.Identity.model_validate(
                {'cast': [{'name': 'Host'}]}), casting='simple')
            llm.set_test_backend(lambda *a, r=reply, **k: json.dumps(r))
            rm = roadmap.create_season(mode, 1, 2)
            assert rm.plan_type == kind and roadmap.load_roadmap(mode, 1).version == 1
        cfg = ProjectConfig(project_id='solo', show_id='solo', title='s', idea='i',
                            mode='standalone_drama')
        projects.create_project(cfg, projects.Identity.model_validate(
            {'cast': [{'name': 'Host'}]}), casting='simple')
        assert roadmap.create_season('solo', 1, 2) is None
        assert roadmap.milestone_for('solo', 1, 1) is None
    llm.set_test_backend(None)


def test_assembler_hides_solutions_when_writing_and_follows_edits(project):
    llm.set_test_backend(lambda *a, **k: json.dumps(arc_reply()))
    roadmap.create_season('lamp', 1, 6)
    ep = {'project_id': 'lamp', 'episode_id': 'e2', 'episode_number': 2, 'season_number': 1}
    plan_ctx = roadmap.assemble_context(ep, 'plan')
    assert 'the drowned twin' in plan_ctx and 'his song' in plan_ctx
    assert 'the drowned twin' not in roadmap.assemble_context(ep, 'write')
    rm = roadmap.load_roadmap('lamp', 1)
    rm.milestones[1].arc_beat = 'Ada climbs the tower in a storm'
    roadmap.save_roadmap(rm, 'edit')
    assert 'climbs the tower' in roadmap.assemble_context(ep, 'plan')


def test_series_directions_filtered_by_canon(project):
    from story_os.canon_models import CanonEvent, Evidence, Verification
    from story_os.canon_store import CanonStore
    store = CanonStore(projects.project_dir('lamp'))
    store.append('events', [CanonEvent(
        event_id='EV-1', episode_id='e1', summary='s',
        evidence=Evidence(episode_id='e1', line_ids=['u'], quote='a b c'),
        verification=Verification(quote_ok=True))])
    store.set_status('e1', 'canon')
    kept = roadmap.series_directions('lamp', [
        {'title': 'ok', 'requires_canon': ['EV-1']},
        {'title': 'no', 'requires_canon': ['EV-404']}])
    assert [d['title'] for d in kept] == ['ok']
