"""Canon behaviour found by the long-run stress test (tools/longrun_stress.py)."""

from story_os.canon_extract import omniscience_check
from story_os.canon_store import CanonStore


def _base(ep, n):
    return {'episode_id': ep, 'episode_number': n, 'status': 'draft',
            'evidence': {'episode_id': ep, 'line_ids': ['l1'], 'quote': 'q'},
            'verification': {'quote_ok': True}}


def test_brief_keeps_oldest_long_horizon_promise(tmp_path):
    s = CanonStore(tmp_path)
    s.append('promises', [{**_base('ep001', 1), 'promise_id': 'PR-OLD', 'kind': 'mystery',
                           'statement': 'Who rang the dead line?', 'horizon': 'series',
                           'planted_in': 'ep001'}])
    for n in range(2, 30):
        s.append('promises', [{**_base(f'ep{n:03d}', n), 'promise_id': f'PR-{n}',
                               'kind': 'question', 'statement': f'q{n}', 'horizon': 'episode'}])
    for n in range(1, 30):
        s.set_status(f'ep{n:03d}', 'canon')
    brief = s.continuity_brief()
    assert 'PR-OLD' in brief and 'Who rang the dead line?' in brief
    assert 'PR-29' in brief                      # newest still shown
    assert '29 open' in brief


def test_records_cache_invalidates_on_append(tmp_path):
    s = CanonStore(tmp_path)
    ev = lambda i: {**_base('e1', 1), 'event_id': f'EV-{i}', 'kind': 'action',
                    'summary': f'thing {i}', 'actors': ['A']}
    s.append('events', [ev(1)])
    assert len(s.records('events')) == 1
    s.append('events', [ev(2)])
    assert len(s.records('events')) == 2
    s.set_status('e1', 'canon')
    assert {r['status'] for r in s.records('events')} == {'canon'}


def test_omniscience_ignores_common_words_and_flags_specific_leak(tmp_path):
    s = CanonStore(tmp_path)
    evs = [{**_base('e1', 1), 'event_id': f'EV-{i}', 'kind': 'action',
            'summary': f'Della found the reel inside the studio cabinet {i}', 'actors': ['Della'],
            'witnesses': []} for i in range(60)]
    evs.append({**_base('e1', 1), 'event_id': 'EV-X', 'kind': 'reveal',
                'summary': 'Calloway buried the Pellham ledger beneath Quarrystone chapel',
                'actors': ['Owen'], 'witnesses': []})
    s.append('events', evs)
    s.set_status('e1', 'canon')
    script = {'scenes': [{'lines': [
        {'type': 'dialogue', 'character': 'Rosa', 'line_id': 'a',
         'content': 'Della found the reel inside the studio cabinet.'},     # common words only
        {'type': 'dialogue', 'character': 'Rosa', 'line_id': 'b',
         'content': 'Calloway buried the Pellham ledger under Quarrystone chapel.'},
    ]}]}
    flags = omniscience_check(script, s, 'e2')
    assert [f['line_id'] for f in flags] == ['b']
