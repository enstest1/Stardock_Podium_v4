"""Tests for GEN-001 projects (stub planner, no network, isolated data dir)."""
import json
from unittest.mock import patch

import pytest

from story_os import llm, projects
from story_os.project_models import MODE_CAPABILITIES

CAP_KEYS = {'season_plan', 'continuity', 'beliefs', 'promises_horizon', 'cast',
            'outline', 'frameworks', 'editorial', 'claims', 'feed_type'}

IDENTITY = {
    'logline': 'A lighthouse keeper hears her drowned brother on the radio.',
    'tone': 'quiet dread', 'world': 'A rock in the North Sea. One radio.',
    'dialogue_rules': ['short sentences'], 'narrator_gender': 'male',
    'narrator_accent': 'british',
    'cast': [
        {'name': 'Dr. Ada Moreau', 'role': 'keeper', 'gender': 'female',
         'accent': 'british'},
        {'name': 'Tomas Reyes', 'role': 'radio voice', 'gender': 'male',
         'accent': 'american'},
    ],
}


@pytest.fixture
def data_dir(tmp_path):
    with patch('config.paths.DATA_DIR', tmp_path),             patch('config.paths.VOICES_DIR', tmp_path / 'voices'):
        yield tmp_path


@pytest.fixture(autouse=True)
def _no_backend():
    yield
    llm.set_test_backend(None)


def test_every_mode_has_every_capability():
    for mode, caps in MODE_CAPABILITIES.items():
        assert set(caps) == CAP_KEYS, mode


@pytest.mark.parametrize('idea,mode', [
    ('Ten-minute lessons on how bridges stay up, for teenagers.', 'educational'),
    ('An interview show with retired lighthouse keepers.', 'conversational'),
    ('A horror anthology of tales told at a night station.', 'anthology'),
])
def test_keyword_fallback_on_invalid_planner_json(idea, mode, data_dir):
    llm.set_test_backend(lambda *a, **k: 'not json')
    cfg = projects.propose_project(idea)
    assert cfg.mode == mode
    assert cfg.mode_rationale == 'keyword fallback'


def test_mode_override_recorded_as_user(data_dir):
    llm.set_test_backend(lambda *a, **k: json.dumps({
        'title': 'The Lamp', 'mode': 'anthology', 'genre': 'gothic horror',
        'episode_minutes': 12}))
    cfg = projects.propose_project('x', mode='standalone_drama', minutes=3)
    assert cfg.mode == 'standalone_drama' and cfg.mode_source == 'user'
    assert cfg.episode_minutes == 3 and cfg.project_id == 'the_lamp'


def test_create_project_writes_files_and_distinct_voices(data_dir):
    llm.set_test_backend(lambda *a, **k: json.dumps(IDENTITY))
    cfg = projects.propose_project('x', mode='anthology', title='The Lamp')
    identity = projects.design_identity(cfg)
    d = projects.create_project(cfg, identity)
    for name in ('project.json', 'format.json', 'bible.json', 'voices.json'):
        assert (d / name).exists()
    voices = json.loads((d / 'voices.json').read_text())
    picked = [v['kokoro_voice'] for v in voices['characters'].values()]
    assert len(picked) == len(set(picked))
    assert voices['engine_order'] == ['kokoro']
    # first/last-name aliases resolve to the full cast key, honorific dropped
    from dialogue_engine import resolve_character_voice_config
    for spoken in ('ADA', 'MOREAU', 'Dr. Ada Moreau', 'TOMAS', 'MR. REYES', 'NARRATOR'):
        assert resolve_character_voice_config(spoken, voices), spoken
    fmt = projects.load_format(cfg.project_id)
    assert 'star trek' not in json.dumps(fmt.model_dump()).lower()
    assert projects.is_fiction(cfg)
    with pytest.raises(FileExistsError):
        projects.create_project(cfg, identity)


def test_creation_never_touches_book_ingestion(data_dir):
    llm.set_test_backend(lambda *a, **k: json.dumps(IDENTITY))
    with patch('epub_processor.EPUBProcessor', side_effect=AssertionError), \
            patch('book_knowledge.get_knowledge_context',
                  side_effect=AssertionError):
        cfg = projects.propose_project('x', mode='anthology', title='A')
        projects.create_project(cfg, projects.design_identity(cfg))


def test_project_prompts_have_no_franchise_words(data_dir, tmp_path):
    """Project episode: card and script prompts carry no legacy wording."""
    from story_os.scene_cards import cards_to_scenes, parse_cards
    from tests.test_scene_cards import cards_json
    llm.set_test_backend(lambda *a, **k: json.dumps(IDENTITY))
    cfg = projects.propose_project('x', mode='anthology', title='The Lamp',
                                   minutes=3)
    projects.create_project(cfg, projects.design_identity(cfg))

    prompts = []
    with patch('story_structure.get_mem0_client'), \
            patch('story_structure.get_knowledge_context') as kn:
        kn.return_value.series_bible = {'main_cast': [{'name': 'Kirk'}]}
        kn.return_value.build_system_prompt.side_effect = AssertionError
        kn.return_value.get_rag_context.side_effect = AssertionError
        from story_structure import StoryStructure
        ss = StoryStructure(episodes_dir=str(tmp_path / 'eps'))

        def fake(role, system, user, **kw):
            prompts.append(system + '\n' + user)
            if 'JSON only' in system:
                return cards_json(overrides={i: {'present': ['Dr. Ada Moreau'],
                                                 'focus': 'Dr. Ada Moreau'}
                                             for i in range(1, 7)})
            return 'ADA: Who is there?\n\n(static)\n\nTOMAS: It is me.'
        llm.set_test_backend(fake)
        ep = ss.generate_episode_structure({'project_id': 'the_lamp',
                                            'title': 'Pilot'})
        cast = ss.generate_character_cast(ep['episode_id'])
        assert [c['name'] for c in cast] == ['Dr. Ada Moreau', 'Tomas Reyes']
        from story_os.asyncio_compat import run_coro
        scenes = run_coro(ss.generate_scenes(ep['episode_id']))
        assert len(scenes) == 6
        script = ss.generate_episode_script(ep['episode_id'])
    assert script['scenes'][0]['lines'][0]['character'] == 'ADA'
    joined = '\n'.join(prompts).lower()
    for word in ('star trek', 'starfleet', 'stardate', 'kirk', 'enterprise'):
        assert word not in joined, word
    assert any('PREVIOUS SCENE' in p for p in prompts)
    assert any('continuity editor' in p for p in prompts)   # canon extraction ran
