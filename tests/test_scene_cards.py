"""Tests for NARRATIVE-001 scene cards and sequential writing. No network."""
import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from story_os import scene_cards as sc

CAST = ['Mara', 'Ilen', 'Dace']
OUTCOMES = ['yes', 'no', 'yes_but', 'no_and', 'no', 'yes_but']


def card(i, **kw):
    d = {
        'scene_number': i, 'kind': 'scene', 'setting': 'Bridge',
        'present': ['Mara', 'Ilen'], 'focus': 'Mara',
        'goal': f'goal {i}', 'opposition': f'opposition {i}',
        'turn': f'turn {i}', 'outcome': OUTCOMES[(i - 1) % len(OUTCOMES)],
        'value_shift': f'trust step {i}', 'audience_learns': '',
        'caused_by': [] if i == 1 else [i - 1],
        'hands_off': f'left open {i}', 'sound_design': ['engine hum'],
    }
    d.update(kw)
    return d


def cards_json(n=6, overrides=None):
    items = [card(i) for i in range(1, n + 1)]
    for idx, patch_kw in (overrides or {}).items():
        items[idx - 1].update(patch_kw)
    return json.dumps({'scenes': items})


def test_good_cards_parse_and_validate():
    cards, problems = sc.parse_cards('```json\n' + cards_json() + '\n```')
    assert problems == []
    assert sc.validate_cards(cards, CAST) == []
    scenes = sc.cards_to_scenes(cards, 600)
    assert len(scenes) == 6
    for s in scenes:
        for key in ('scene_id', 'scene_number', 'beat', 'setting',
                    'characters', 'plot', 'duration_seconds', 'card'):
            assert key in s
    assert sum(s['duration_seconds'] for s in scenes) <= 600


def test_uncaused_scene_and_unknown_character_rejected():
    cards, _ = sc.parse_cards(cards_json(overrides={3: {'caused_by': []},
                                                     4: {'present': ['Mara', 'Zed']}}))
    issues = sc.validate_cards(cards, CAST)
    assert any('scene 3: caused_by is empty' in i for i in issues)
    assert any("unknown character 'Zed'" in i for i in issues)


def test_forward_cause_and_empty_value_shift_rejected():
    cards, _ = sc.parse_cards(cards_json(overrides={2: {'caused_by': [5]},
                                                     3: {'value_shift': ' '}}))
    issues = sc.validate_cards(cards, CAST)
    assert any('caused_by 5 is not an earlier scene' in i for i in issues)
    assert any('scene 3: empty value_shift' in i for i in issues)


def test_bad_json_and_missing_field_reported():
    cards, problems = sc.parse_cards('not json at all')
    assert cards == [] and problems and 'invalid JSON' in problems[0]
    broken = json.loads(cards_json())
    del broken['scenes'][1]['goal']
    cards, problems = sc.parse_cards(json.dumps(broken))
    assert any('scene 2: missing field goal' in p for p in problems)


def test_render_block_has_handoff_and_spoken_tail_not_descriptions():
    cards, _ = sc.parse_cards(cards_json())
    scenes = sc.cards_to_scenes(cards, 600)
    prev_script = {'card': scenes[0]['card'], 'lines': [
        {'type': 'description', 'content': 'The hatch groans.'},
        {'type': 'dialogue', 'character': 'Mara', 'content': 'Seal it.'},
    ]}
    block = sc.render_card_block(scenes[1], prev_script, scenes[2])
    assert block.startswith('SCENE CARD')
    assert 'Goal: goal 2' in block
    assert 'Do NOT resolve this (it belongs to the next scene): goal 3' in block
    assert 'PREVIOUS SCENE' in block
    assert 'It left unresolved: left open 1' in block
    assert 'MARA: Seal it.' in block
    assert 'The hatch groans.' not in block
    assert sc.render_card_block({'plot': 'x'}) == ''


# ---------------------------------------------------- StoryStructure path ----

@pytest.fixture
def structure():
    tmp = tempfile.mkdtemp()
    patches = [
        patch.dict('os.environ', {'OPENAI_API_KEY': 'fake'}),
        patch('story_structure.get_mem0_client'),
        patch('story_structure.OpenAI'),
        patch('story_structure.AsyncOpenAI'),
        patch('story_structure.get_knowledge_context'),
        patch('story_structure.get_episode_memory'),
    ]
    mocks = [p.start() for p in patches]
    knowledge = mocks[4].return_value
    knowledge.series_bible = {}
    knowledge.is_ready.return_value = True
    knowledge.get_rag_context.return_value = ''
    knowledge.build_system_prompt.side_effect = lambda base: base
    from story_structure import StoryStructure
    ss = StoryStructure(episodes_dir=tmp)
    yield ss
    for p in patches:
        p.stop()
    shutil.rmtree(tmp, ignore_errors=True)


def _episode(ss):
    ep = {'episode_id': 'ep_test', 'title': 'T', 'theme': 'th',
          'episode_number': 1, 'target_duration_minutes': 10,
          'characters': [{'name': n, 'role': 'crew'} for n in CAST],
          'scenes': []}
    ss._save_episode(ep)
    return ep


def test_rejected_first_answer_triggers_one_reask(structure):
    replies = [cards_json(overrides={2: {'caused_by': []}}), cards_json()]
    calls = []

    def fake(system, user, max_tokens=800):
        calls.append(user)
        return replies[len(calls) - 1]
    structure.complete_text = fake
    scenes = structure._generate_scenes_from_cards(_episode(structure))
    assert len(calls) == 2
    assert 'YOUR PREVIOUS ANSWER WAS REJECTED' in calls[1]
    assert 'scene 2: caused_by is empty' in calls[1]
    assert len(scenes) == 6
    saved = structure.get_episode('ep_test')
    assert saved['metadata']['outline_mode'] == 'cards'


def test_two_failures_return_empty_after_two_calls(structure):
    calls = []

    def fake(system, user, max_tokens=800):
        calls.append(user)
        return 'nope'
    structure.complete_text = fake
    assert structure._generate_scenes_from_cards(_episode(structure)) == []
    assert len(calls) == 2


def test_scene_prompts_are_sequential(structure):
    ep = _episode(structure)
    cards, _ = sc.parse_cards(cards_json())
    ep['scenes'] = sc.cards_to_scenes(cards, 600)
    structure._save_episode(ep)
    prompts = []

    def fake_llm(role, system, user, **kw):
        prompts.append(user)
        i = len(prompts)
        return f'MARA: Line from scene {i}.\n\nILEN: Reply {i}.'
    structure._llm = fake_llm
    script = structure.generate_episode_script('ep_test')
    assert len(prompts) == 6
    assert 'PREVIOUS SCENE' not in prompts[0]
    for i in range(1, 6):
        p = prompts[i]
        assert f'Goal: goal {i + 1}' in p
        assert f'It left unresolved: left open {i}' in p
        assert f'MARA: Line from scene {i}.' in p
    for scene in script['scenes']:
        assert scene['card']
        assert all(line.get('line_id') for line in scene['lines'])


def test_legacy_scene_prompt_unchanged_without_card(structure):
    ep = _episode(structure)
    prompts = []

    def fake_llm(role, system, user, **kw):
        prompts.append(user)
        return 'MARA: Hello.'
    structure._llm = fake_llm
    structure._generate_scene_script(ep, {'scene_number': 1, 'beat': 'Setup',
                                          'setting': 'Bridge'})
    assert prompts[0].startswith(
        'Generate a detailed script for a Star Trek audio drama scene.')
    assert 'SCENE CARD' not in prompts[0]
    assert 'PREVIOUS SCENE' not in prompts[0]
