"""NARRATIVE-002/003, CHAR-001: frameworks, character briefs, profiles."""
import json
from unittest.mock import patch

import pytest

from story_os import frameworks as fw
from story_os import llm


def test_every_framework_shares_sum_to_one_and_families_exist():
    for f in fw.REGISTRY.values():
        assert abs(sum(s.share for s in f.steps) - 1) < 1e-6
    fams = {f.family for f in fw.REGISTRY.values()}
    assert fams == {'fiction', 'nonfiction', 'educational', 'conversational'}
    assert len([f for f in fw.REGISTRY.values() if f.family == 'fiction']) == 10


def test_rotation_over_simulated_season():
    history = []
    milestones = [{'arc_beat': 'ordinary trouble', 'structural_role': 'none'}] * 10
    for m in milestones:
        fid, _ = fw.select_framework(m, history, family='fiction', genre='drama')
        history.append(fid)
    assert all(a != b for a, b in zip(history, history[1:]))
    assert len(set(history[:8])) >= 3
    for i in range(len(history)):
        assert history[max(0, i - 3):i + 1].count(history[i]) <= 2


def test_rules_mystery_family_and_chooser():
    fid, why = fw.select_framework({'arc_beat': 'the clue to who wrote the notes',
                                    'must_payoff': ['reveal']}, [], family='fiction')
    assert fid == 'mystery_fairplay' and 'rule' in why
    fid, _ = fw.select_framework({'arc_beat': 'x'}, [], family='educational')
    assert fw.REGISTRY[fid].family == 'educational'
    seen = []
    fid, why = fw.select_framework({'arc_beat': 'x'}, [], family='fiction', genre='',
                                   chooser=lambda c: seen.append([f.id for f in c]) or c[1].id)
    assert seen and len(seen[0]) <= 3 and fid == seen[0][1]
    block = fw.render_framework_block(fw.REGISTRY['bottle'], 10)
    assert 'trap' in block and 'not one scene each' in block


@pytest.fixture
def proj(tmp_path):
    from story_os import projects
    from story_os.project_models import ProjectConfig
    with patch('config.paths.DATA_DIR', tmp_path):
        cfg = ProjectConfig(project_id='p', show_id='p', title='P', idea='i',
                            mode='serialized_fiction')
        ident = projects.Identity.model_validate({'cast': [
            {'name': 'Mara Quill', 'want': 'find the truth', 'never_says': ['sorry'],
             'speech_rhythm': 'clipped'},
            {'name': 'Marla Quinn'}, {'name': 'Ilen Voss'}]})
        projects.create_project(cfg, ident, casting='simple')
        yield projects
    llm.set_test_backend(None)


def test_profiles_briefs_and_knowledge_scoping(proj):
    from story_os.characters import load_profiles, render_character_briefs
    from story_os.canon_models import Belief, Evidence, Verification
    from story_os.canon_store import CanonStore
    profiles = load_profiles('p')
    assert profiles['Mara Quill'].dialogue.never_says == ['sorry']
    warn = json.loads((proj.project_dir('p') / 'name_warnings.json').read_text())
    assert any('Mara Quill / Marla Quinn' in w for w in warn)
    store = CanonStore(proj.project_dir('p'))
    ev = Evidence(episode_id='e1', line_ids=['u'], quote='a b c')
    store.append('beliefs', [
        Belief(belief_id='B1', episode_id='e1', holder='Mara Quill', proposition='the key is gone',
               stance='knows', truth='true', evidence=ev, verification=Verification(quote_ok=True)),
        Belief(belief_id='B2', episode_id='e1', holder='Ilen Voss', proposition='Ilen burned the log',
               stance='knows', truth='true', evidence=ev, verification=Verification(quote_ok=True))])
    store.set_status('e1', 'canon')
    card = {'present': ['Mara Quill'], 'objectives': {'Mara Quill': 'get Ilen to confess'},
            'withheld': {'Mara Quill': 'she has the key'}}
    text = render_character_briefs(card, profiles, store)
    assert 'never says: sorry' in text and 'get Ilen to confess' in text
    assert 'the key is gone' in text and 'burned the log' not in text


def test_arc_step_requires_canon_and_enrich_never_overwrites(proj):
    from story_os.characters import add_arc_step, enrich_profile, load_profiles
    from story_os.canon_store import CanonStore
    store = CanonStore(proj.project_dir('p'))
    prof = load_profiles('p')['Mara Quill']
    with pytest.raises(ValueError):
        add_arc_step('p', prof, 'learns to trust', 'EV-404', store)
    llm.set_test_backend(lambda *a, **k: json.dumps({
        'want': 'OVERWRITE', 'need': 'to let go', 'never_says': ['x']}))
    prof = enrich_profile('p', prof, 'show')
    assert prof.want == 'find the truth' and prof.need == 'to let go'
    assert prof.dialogue.never_says == ['sorry']
