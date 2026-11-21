"""CANON-001..005: ledger, extraction, beliefs, promises, Mem0 infer=False."""
import json
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from story_os import llm
from story_os.canon_extract import approve_episode, extract_episode, omniscience_check
from story_os.canon_models import CanonEvent, Evidence, Verification
from story_os.canon_store import CanonStore

SCRIPT = {'scenes': [
    {'scene_number': 1, 'lines': [
        {'line_id': 'u1', 'type': 'dialogue', 'character': 'MARA',
         'content': 'Did you open the flight log last night?'},
        {'line_id': 'u2', 'type': 'dialogue', 'character': 'ILEN',
         'content': 'I never opened the log, I swear it.'},
        {'line_id': 'u3', 'type': 'narration', 'content': 'Mara pockets the brass key and walks out.'},
    ]},
    {'scene_number': 2, 'lines': [
        {'line_id': 'u4', 'type': 'dialogue', 'character': 'DACE',
         'content': 'Who took the brass key from the drawer?'},
    ]},
]}
EPISODE = {'episode_id': 'ep1', 'episode_number': 1,
           'characters': [{'name': 'Mara Quill'}, {'name': 'Ilen Voss'},
                          {'name': 'Dace Hart'}]}


def good_scene1():
    return {
        'events': [{'kind': 'action', 'summary': 'Mara takes the brass key',
                    'actors': ['Mara'], 'line_ids': ['L0003'],
                    'quote': 'pockets the brass key'}],
        'state_changes': [{'entity': 'brass key', 'attribute': 'possession',
                           'after': 'with Mara', 'line_ids': ['L0003'],
                           'quote': 'Mara pockets the brass key'}],
        'beliefs': [{'holder': 'Ilen', 'proposition': 'Ilen never opened the log',
                     'stance': 'claims', 'truth': 'unknown', 'line_ids': ['L0002'],
                     'quote': 'I never opened the log'}],
        'relationships': [],
        'promises': [{'kind': 'mystery', 'statement': 'Who opened the flight log?',
                      'horizon': 'season', 'line_ids': ['L0001'],
                      'quote': 'open the flight log'}],
        'events_bad': [],
    }


@pytest.fixture(autouse=True)
def _reset():
    yield
    llm.set_test_backend(None)


def _backend(replies):
    calls = []

    def fake(role, system, user, **kw):
        calls.append(user)
        if 'You check one claim' in system:
            return json.dumps({'supported': replies.get('judge', True), 'line': 'x'})
        key = 'scene2' if 'SCENE 2' in user else 'scene1'
        if 'were rejected' in user:
            key += '_fix'
        return json.dumps(replies.get(key, {}))
    llm.set_test_backend(fake)
    return calls


def test_store_roundtrip_status_supersede_and_rebuild(tmp_path):
    store = CanonStore(tmp_path)
    ev = CanonEvent(event_id='EV-1', episode_id='ep1', summary='x happens',
                    evidence=Evidence(episode_id='ep1', line_ids=['u1'], quote='a b c'),
                    verification=Verification(quote_ok=True))
    store.append('events', [ev])
    assert store.query('events') == []                       # draft hidden
    assert len(store.query('events', include_draft_episode='ep1')) == 1
    approve_episode(store, 'ep1')
    assert store.query('events')[0]['status'] == 'canon'
    new = ev.model_copy(update={'event_id': 'EV-2', 'summary': 'y happens'})
    store.correct('events', 'EV-1', new, 'continuity fix')
    statuses = {r['event_id']: r['status'] for r in store.records('events')}
    assert statuses == {'EV-1': 'superseded', 'EV-2': 'canon'}
    a = store.rebuild_index().read_bytes()
    b = store.rebuild_index().read_bytes()
    assert a == b                                             # deterministic
    with pytest.raises(ValueError):
        CanonEvent(event_id='EV-3', episode_id='e', summary='s', status='canon',
                   evidence=Evidence(episode_id='e', line_ids=['u'], quote='q'))


def test_extraction_accepts_verified_and_stores_claim_as_belief(tmp_path):
    _backend({'scene1': good_scene1()})
    store = CanonStore(tmp_path)
    rep = extract_episode(EPISODE, SCRIPT, store)
    assert rep['accepted']['events'] == 1 and rep['rejected'] == 0
    approve_episode(store, 'ep1')
    ev = store.query('events')[0]
    assert ev['evidence']['line_ids'] == ['u3']               # mapped to real line ids
    assert ev['actors'] == ['Mara Quill']                     # canonical cast name
    claim = [b for b in store.query('beliefs') if b['stance'] == 'claims'][0]
    assert claim['holder'] == 'Ilen Voss' and 'never opened' in claim['proposition']
    assert not any('never opened' in e['summary'] for e in store.query('events'))
    knows = [b for b in store.query('beliefs') if b['stance'] == 'knows']
    assert {b['holder'] for b in knows} == {'Mara Quill', 'Ilen Voss'}
    assert store.character_state('brass key') == {'possession': 'with Mara'}
    assert store.open_promises()[0]['statement'] == 'Who opened the flight log?'
    assert 'Who opened the flight log?' in store.continuity_brief()


def test_fabricated_wrong_scene_and_unknown_character_rejected_with_one_reask(tmp_path):
    bad = good_scene1()
    bad['events'] = [
        {'summary': 'fabricated', 'actors': ['Mara'], 'line_ids': ['L0001'],
         'quote': 'she burned the whole log'},
        {'summary': 'other scene', 'actors': ['Mara'], 'line_ids': ['L0004'],
         'quote': 'Who took the brass'},
        {'summary': 'stranger', 'actors': ['Zed'], 'line_ids': ['L0003'],
         'quote': 'pockets the brass key'},
    ]
    calls = _backend({'scene1': bad, 'scene1_fix': {'events': []}})
    store = CanonStore(tmp_path)
    rep = extract_episode(EPISODE, SCRIPT, store)
    reasons = [r for s in rep['scenes'] for x in s['rejected'] for r in x['reasons']]
    assert any('quote not found' in r for r in reasons)
    assert any('not in this scene' in r for r in reasons)
    assert any("unknown character 'Zed'" in r for r in reasons)
    assert rep['accepted']['events'] == 0
    assert sum('were rejected' in c for c in calls) == 1      # exactly one re-ask


def test_irreversible_change_needs_judge(tmp_path):
    s1 = good_scene1()
    s1['state_changes'] = [{'entity': 'Ilen', 'attribute': 'condition', 'after': 'dead',
                            'line_ids': ['L0003'], 'quote': 'walks out'}]
    s1['state_changes'][0]['quote'] = 'pockets the brass key'
    _backend({'scene1': s1, 'judge': False})
    store = CanonStore(tmp_path)
    rep = extract_episode(EPISODE, SCRIPT, store)
    assert rep['accepted']['state_changes'] == 0 and rep['judged'][0]['ok'] is False


def test_promise_paid_only_when_judge_agrees(tmp_path):
    store = CanonStore(tmp_path)
    _backend({'scene1': good_scene1()})
    extract_episode(EPISODE, SCRIPT, store)
    approve_episode(store, 'ep1')
    pid = store.open_promises()[0]['promise_id']
    ep2 = dict(EPISODE, episode_id='ep2', episode_number=2)
    pay = {'pays_off': [{'promise_id': pid, 'line_ids': ['L0001'],
                         'quote': 'open the flight log'}]}
    for verdict, expected_open in ((False, 1), (True, 0)):
        _backend({'scene1': pay, 'judge': verdict})
        extract_episode(ep2, SCRIPT, store)
        approve_episode(store, 'ep2')
        assert len(store.open_promises()) == expected_open


def test_omniscience_flags_speaker_who_cannot_know(tmp_path):
    store = CanonStore(tmp_path)
    ev = CanonEvent(event_id='EV-9', episode_id='ep1', summary='Ilen secretly burned the shipping manifest',
                    actors=['Ilen Voss'], witnesses=['Ilen Voss'],
                    evidence=Evidence(episode_id='ep1', line_ids=['u'], quote='a b c'),
                    verification=Verification(quote_ok=True))
    store.append('events', [ev])
    approve_episode(store, 'ep1')
    script = {'scenes': [{'lines': [
        {'line_id': 'x1', 'type': 'dialogue', 'character': 'Dace Hart',
         'content': 'Ilen secretly burned the shipping manifest, I know it.'},
        {'line_id': 'x2', 'type': 'dialogue', 'character': 'Ilen Voss',
         'content': 'I secretly burned the shipping manifest myself.'}]}]}
    issues = omniscience_check(script, store, 'ep2')
    assert [i['line_id'] for i in issues] == ['x1']


def test_mem0_add_memory_is_verbatim(monkeypatch):
    import mem0_client
    c = object.__new__(mem0_client.Mem0Client) if hasattr(mem0_client, 'Mem0Client') else None
    if c is None:
        pytest.skip('Mem0Client class not found')
    c.client = MagicMock()
    c.add_memory('text', user_id='u', memory_type='t')
    assert c.client.add.call_args.kwargs['infer'] is False

    class Old:
        def add(self, content, user_id=None, metadata=None):
            raise AssertionError('should not be called without infer')
    c2 = object.__new__(mem0_client.Mem0Client)
    c2.client = MagicMock()
    c2.client.add.side_effect = TypeError("add() got an unexpected keyword argument 'infer'")
    assert c2.add_memory('t', user_id='u', memory_type='t')['refused'] is True


def test_only_canon_store_writes_the_ledger():
    root = Path(__file__).resolve().parents[1]
    hits = []
    for py in root.rglob('*.py'):
        if any(p in py.parts for p in ('tests', '.venv', '.venv-xtts', 'site-packages')):
            continue
        text = py.read_text(encoding='utf-8', errors='ignore')
        if re.search(r"open\([^)]*\.jsonl['\"][^)]*['\"]a['\"]", text) or \
                re.search(r"(events|beliefs|promises)\.jsonl", text):
            hits.append(py.name)
    assert set(hits) <= {'canon_store.py'}, hits
