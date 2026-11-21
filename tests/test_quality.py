"""QUALITY-001..004, WRITERS-001: judge, lint, revision caps, premises, originality."""
import json

import pytest

from story_os import judge, llm, originality, writers_room as wr


@pytest.fixture(autouse=True)
def _reset():
    yield
    llm.set_test_backend(None)


def test_judge_neutralises_position_bias_and_finds_real_preference():
    llm.set_test_backend(lambda *a, **k: '{"winner": 1, "reason": "first"}')
    r = judge.compare('short', 'a much longer text', 'which?')
    assert r['winner'] == 'undecided' and r['ties'] == 2 and r['order_flips'] == 2

    def longer(role, system, user, **kw):
        t1 = user.split('Text 1:\n')[1].split('\n\nText 2:')[0]
        t2 = user.split('Text 2:\n')[1]
        return json.dumps({'winner': 1 if len(t1) > len(t2) else 2})
    llm.set_test_backend(longer)
    assert judge.compare('short', 'a much longer text', 'q')['winner'] == 'b'
    assert judge.rank(['aa', 'aaaa', 'a'], 'q') == [1, 0, 2]
    llm.set_test_backend(lambda *a, **k: 'not json')
    assert judge.compare('x', 'y', 'q')['winner'] == 'undecided'


def L(kind, content, who=None, lid=None):
    d = {'type': kind, 'content': content, 'line_id': lid or content[:6]}
    if who:
        d['character'] = who
    return d


def test_lint_rules_fire_and_stay_quiet():
    good = {'scenes': [{'scene_number': 1, 'card': {'turn': 'Mara finds the hidden ledger'},
                        'lines': [L('dialogue', 'I found the hidden ledger.', 'MARA'),
                                  L('dialogue', 'Then we are finished here.', 'ILEN')]}]}
    assert [f for f in wr.lint(good, ['Mara Quill', 'Ilen Voss']) if f['severity'] != 'info'] == []
    bad = {'scenes': [
        {'scene_number': 1, 'card': {'turn': 'the lighthouse explodes violently tonight'},
         'lines': [L('description', 'A crimson lantern hangs beside brass compass, unnoticed sextant gleaming.'),
                   L('dialogue', 'Peter picked purple peppers promptly.', 'MARA'),
                   L('dialogue', 'Hello.', 'ZED'),
                   L('dialogue', ' '.join(['word'] * 50), 'A1'),
                   L('dialogue', 'x', 'B1'), L('dialogue', 'y', 'C1'),
                   L('dialogue', 'z', 'D1')]},
        {'scene_number': 2, 'lines': [L('narration', 'Night falls and the narrator talks a lot about everything here.')]}]}
    rules = {f['rule'] for f in wr.lint(bad, ['Mara Quill'])}
    for r in ('description_only_information', 'tongue_twister', 'unknown_speaker',
              'long_line', 'too_many_speakers', 'turn_off_page', 'no_dialogue'):
        assert r in rules, r
    narr = {'scenes': [{'scene_number': 1, 'lines': [
        L('narration', 'The narrator describes the whole long night in great detail here.'),
        L('dialogue', 'Yes.', 'MARA')]}]}
    assert 'narration_share' in {f['rule'] for f in wr.lint(narr, ['Mara Quill'])}


def test_dead_character_speaking_is_a_canon_contradiction(tmp_path):
    from story_os.canon_models import Evidence, StateChange, Verification
    from story_os.canon_store import CanonStore
    store = CanonStore(tmp_path)
    store.append('state_changes', [StateChange(
        change_id='ST-1', episode_id='e1', entity='Ilen Voss', attribute='condition',
        after='dead', irreversible=True,
        evidence=Evidence(episode_id='e1', line_ids=['u'], quote='a b c'),
        verification=Verification(quote_ok=True, judged=True))])
    store.set_status('e1', 'canon')
    s = {'scenes': [{'scene_number': 1, 'lines': [L('dialogue', 'I am back.', 'ILEN')]}]}
    assert any(f['rule'] == 'canon_contradiction' for f in wr.lint(s, ['Ilen Voss'], store=store))


def test_revision_capped_at_thirty_percent():
    script = {'scenes': [{'scene_number': i} for i in range(1, 11)]}
    few = wr.plan_revision(script, [{'scene_number': 2, 'instruction': 'a'},
                                    {'scene_number': 5, 'instruction': 'b'}])
    assert few['status'] == 'revise' and set(few['scenes']) == {2, 5}
    many = wr.plan_revision(script, [{'scene_number': i, 'instruction': 'x'} for i in range(1, 6)])
    assert many['status'] == 'needs_reoutline'


def test_premises_must_differ_and_screen_drops_dead_protagonist(tmp_path):
    same = [{'logline': f'l{i}', 'protagonist': 'Mara', 'obstacle_type': f'o{i}',
             'ending_type': f'e{i}'} for i in range(3)]
    assert any('protagonist' in p for p in wr.premise_problems(same, 3))
    from story_os.canon_models import Evidence, StateChange, Verification
    from story_os.canon_store import CanonStore
    store = CanonStore(tmp_path)
    store.append('state_changes', [StateChange(
        change_id='ST-1', episode_id='e1', entity='Ilen', attribute='condition', after='dead',
        irreversible=True, evidence=Evidence(episode_id='e1', line_ids=['u'], quote='a b c'),
        verification=Verification(quote_ok=True))])
    store.set_status('e1', 'canon')
    items = [{'logline': 'a', 'protagonist': 'Ilen'}, {'logline': 'b', 'protagonist': 'Mara'}]
    assert [p['logline'] for p in wr.screen(items, store)] == ['b']
    llm.set_test_backend(lambda role, s, u, **k: json.dumps({'premises': [
        {'logline': 'p1', 'protagonist': 'A', 'obstacle_type': 'x', 'ending_type': 'win'},
        {'logline': 'p2', 'protagonist': 'B', 'obstacle_type': 'y', 'ending_type': 'loss'},
        {'logline': 'p3', 'protagonist': 'C', 'obstacle_type': 'z', 'ending_type': 'twist'}]})
        if 'writers room' in s else '{"winner": 0}')
    assert wr.choose_premise('ctx')['logline'] == 'p1'     # undecided keeps first


def test_originality_identical_vs_unrelated():
    a = {'scenes': [{'lines': [L('dialogue', 'The tide took the boat and the boat took my father, so I hate the tide.', 'MARA'),
                               L('narration', 'It was as if the sea itself remembered.')]}]}
    b = {'scenes': [{'lines': [L('dialogue', 'Quarterly invoices must be filed before the auditors arrive on Tuesday morning.', 'ILEN')]}]}
    same = originality.metrics(a, ['Mara Quill'], [a])
    assert 'similar_to_previous_episode' in same['flags'] and same['slop_hits']
    diff = originality.metrics(a, ['Mara Quill'], [b])
    assert diff['cross_episode_jaccard'] == 0.0
