"""REF-001..005, GEN-002 (T15-T21 subset with stub models)."""
import json
from unittest.mock import patch

import pytest

from story_os import llm, projects
from story_os.project_models import ProjectConfig

TEXT = """# The Bridge
The Harlow Bridge opened in 1931. Engineers said the Harlow Bridge would last a century.
"Steel remembers every load," said the chief engineer of the Harlow Bridge.

# Cables
Each cable holds 9000 strands of wire, according to the 1931 survey.
"""
OTHER = """# Survey
A later survey of the Harlow Bridge counted 8500 strands of wire in each cable.
"""


def fake_llm(role, system, user, **kw):
    if 'checkable factual claims' in system:
        if '9000' in user:
            return json.dumps({'claims': [
                {'text': 'Each Harlow cable holds 9000 strands', 'kind': 'figure',
                 'quote': 'Each cable holds 9000 strands of wire'},
                {'text': 'invented', 'kind': 'fact', 'quote': 'this sentence is not there'}]})
        if '8500' in user:
            return json.dumps({'claims': [
                {'text': 'Each Harlow cable holds 8500 strands', 'kind': 'figure',
                 'quote': 'counted 8500 strands of wire'}]})
        return json.dumps({'claims': []})
    if 'HOW a text is written' in system:
        return json.dumps({'numeric': {'pacing': 0.9, 'atmosphere': 0.8},
                           'categorical': {'tone': 'ominous'}})
    if 'You check one claim' in system:
        return json.dumps({'supported': True, 'line': ''})
    if 'world facts' in system:
        return json.dumps({'facts': [{'summary': 'The bridge opened in 1931',
                                      'quote': 'The Harlow Bridge opened in 1931'}]})
    return '{}'


@pytest.fixture
def two_projects(tmp_path):
    with patch('config.paths.DATA_DIR', tmp_path), \
            patch('config.paths.EPISODES_DIR', tmp_path / 'eps'):
        for pid, mode in (('a', 'documentary'), ('b', 'educational')):
            cfg = ProjectConfig(project_id=pid, show_id=pid, title=pid, idea='bridges', mode=mode)
            projects.create_project(cfg, projects.Identity.model_validate(
                {'cast': [{'name': 'Rae Okafor'}, {'name': 'Tom Hale'}]}), casting='simple')
        (tmp_path / 'bridge.md').write_text(TEXT, encoding='utf-8')
        (tmp_path / 'survey.txt').write_text(OTHER, encoding='utf-8')
        (tmp_path / 'page.html').write_text('<html><body><h1>Hi</h1><p>Plain words here.</p></body></html>')
        llm.set_test_backend(fake_llm)
        yield tmp_path
    llm.set_test_backend(None)


def test_registry_formats_idempotent_rights_and_isolation(two_projects):
    from story_os import references as R
    s1 = R.add_reference(str(two_projects / 'bridge.md'), 'a', ['factual_research'])
    again = R.add_reference(str(two_projects / 'bridge.md'), 'a', ['factual_research'])
    assert s1.source_id == again.source_id and len(R.list_sources('a')) == 1
    assert R.load_sections(two_projects / 'page.html')[0]['text'].strip().startswith('Hi')
    with pytest.raises(ValueError):
        R.add_reference(str(two_projects / 'survey.txt'), 'a', ['world_building'])
    assert R.list_sources('b') == []                       # isolation
    R.set_enabled('a', s1.source_id, False)
    assert R.list_sources('a') == []
    R.set_enabled('a', s1.source_id, True)
    audit = (R.refs_dir('a') / 'audit.jsonl').read_text().splitlines()
    assert [json.loads(l)['op'] for l in audit] == ['add', 'disable', 'enable']


def test_claims_verified_conflicts_linked_and_script_checked(two_projects):
    from story_os import claims as C
    from story_os import references as R
    R.add_reference(str(two_projects / 'bridge.md'), 'a', ['factual_research'])
    R.add_reference(str(two_projects / 'survey.txt'), 'a', ['factual_research'])
    store = C.ClaimStore('a').all()
    texts = sorted(c.text for c in store.values())
    assert texts == ['Each Harlow cable holds 8500 strands', 'Each Harlow cable holds 9000 strands']
    a, b = sorted(store.values(), key=lambda c: c.text)
    assert a.conflicts_with == [b.claim_id] and b.conflicts_with == [a.claim_id]
    assert a.support == 'contested' and a.must_flag_uncertainty
    script = {'scenes': [{'scene_number': 1, 'lines': [
        {'type': 'dialogue', 'character': 'RAE', 'line_id': 'x1',
         'content': 'Each cable holds 9000 strands.', 'claim_refs': [b.claim_id]},
        {'type': 'dialogue', 'character': 'TOM', 'line_id': 'x2',
         'content': 'It cost 40 million to build.'},
        {'type': 'dialogue', 'character': 'RAE', 'line_id': 'x3',
         'content': 'Some say it is 7000 strands.', 'claim_refs': [a.claim_id]}]}]}
    rules = {(f['line_id'], f['rule']) for f in C.check_script(script, 'a')}
    assert ('x1', 'contested_as_settled') in rules
    assert ('x2', 'unsupported_claim') in rules
    assert ('x3', 'figure_mismatch') in rules
    line = C.strip_markers({'content': 'It opened in 1931. [[CL-0001]]'})
    assert line == {'content': 'It opened in 1931.', 'claim_refs': ['CL-0001']}


def test_technique_profile_directives_and_snapshot(two_projects):
    from story_os import references as R
    src = R.add_reference(str(two_projects / 'bridge.md'), 'a', ['writing_techniques'])
    assert not (R.refs_dir('a') / 'claims.jsonl').exists()     # no fact extraction
    R.bind('a', src.source_id, 0.8, {'pacing': 1.0, 'tone': 1.0})
    d = R.style_directives('a')
    blob = ' '.join(d)
    assert d and 'ominous' in blob and '%' not in blob
    assert 'Harlow' not in blob and src.source_id not in blob and 'bridge' not in blob.lower()
    snap = R.snapshot('a', 'ep1', two_projects / 'eps')
    before = snap.read_text()
    R.bind('a', src.source_id, 0.1, {'pacing': 1.0})
    assert snap.read_text() == before                          # approved snapshot unchanged


def test_world_import_needs_rights_and_purge_keeps_cited(two_projects):
    from story_os import claims as C
    from story_os import references as R
    from story_os.canon_store import CanonStore
    with pytest.raises(ValueError):
        R.add_reference(str(two_projects / 'bridge.md'), 'a', ['world_building'])
    src = R.add_reference(str(two_projects / 'bridge.md'), 'a', ['world_building'],
                          rights='owned', holder='me')
    ev = CanonStore(projects.project_dir('a')).query('events')
    assert ev and ev[0]['origin'] == 'source' and ev[0]['source_id'] == src.source_id
    fact = R.add_reference(str(two_projects / 'survey.txt'), 'a', ['factual_research'])
    cid = next(iter(C.ClaimStore('a').all()))
    eps = two_projects / 'eps' / 'ep9'
    eps.mkdir(parents=True)
    (eps / 'script.json').write_text(json.dumps({'scenes': [{'lines': [
        {'content': 'x', 'claim_refs': [cid]}]}]}))
    res = R.purge('a', fact.source_id)
    assert res['kept_cited_claims'] == 1 and cid in C.ClaimStore('a').all()
    assert R.list_sources('a', purpose='factual_research') == []


def test_segment_cards_validation_and_sequential_writing(two_projects):
    from story_os import segment_cards as sg
    hosts = ['Rae Okafor', 'Tom Hale']

    def seg(n, **kw):
        d = {'segment_number': n, 'kind': 'explanation', 'purpose': f'p{n}',
             'speakers': ['Rae Okafor'], 'key_points': [f'point {n}'],
             'claim_ids': ['general knowledge'], 'builds_on': [] if n == 1 else [n - 1],
             'listener_takeaway': f't{n}'}
        d.update(kw)
        return d
    good = [seg(1, kind='cold_open'), seg(2), seg(3, kind='recap')]
    cards, probs = sg.parse_segments(json.dumps({'segments': good}))
    assert probs == [] and sg.validate_segments(cards, hosts, claims_mode=True,
                                                known_claims=set(), objectives=['point'] ) == []
    bad = [seg(1), seg(2, key_points=['It holds 9000 strands'], claim_ids=['general knowledge']),
           seg(3)]
    cards, _ = sg.parse_segments(json.dumps({'segments': bad}))
    issues = sg.validate_segments(cards, hosts, claims_mode=True, known_claims=set(),
                                  objectives=['point'])
    assert any('has no claim id' in i for i in issues)
    assert any('must end with a recap' in i for i in issues)

    with patch('story_structure.get_mem0_client'), \
            patch('story_structure.get_knowledge_context') as kn:
        kn.return_value.series_bible = {}
        from story_structure import StoryStructure
        ss = StoryStructure(episodes_dir=str(two_projects / 'eps'))
        prompts = []

        def fake(role, system, user, **kw):
            prompts.append(user)
            if 'producer planning a nonfiction' in system:
                return json.dumps({'segments': good})
            return 'RAE: Welcome. [[CL-0009]]\n\nTOM: Let us begin.'
        llm.set_test_backend(fake)
        ep = ss.generate_episode_structure({'project_id': 'b', 'title': 'Cables'})
        ss.generate_character_cast(ep['episode_id'])
        from story_os.asyncio_compat import run_coro
        scenes = run_coro(ss.generate_scenes(ep['episode_id']))
        assert len(scenes) == 3 and scenes[0]['segment']['kind'] == 'cold_open'
        script = ss.generate_episode_script(ep['episode_id'])
    writer = [p for p in prompts if 'SEGMENT CARD' in p]
    assert len(writer) == 3 and 'PREVIOUS SEGMENT' not in writer[0]
    assert all('PREVIOUS SEGMENT' in p for p in writer[1:])
    assert all('fictional AI personas' in p for p in writer)
    first = script['scenes'][0]['lines'][0]
    assert first['content'] == 'Welcome.' and first['claim_refs'] == ['CL-0009']
    assert ss.get_episode(ep['episode_id'])['metadata']['outline_mode'] == 'segments'
    fmt = projects.load_format('b')
    assert 'AI-generated voices' in fmt.intro_template
