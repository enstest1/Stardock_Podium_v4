"""STORYOS-001: migrate-shows is planned, idempotent, reversible, prompt-neutral."""
import json
from unittest.mock import patch

import pytest


@pytest.fixture
def legacy_world(tmp_path):
    data, eps, voices = tmp_path / 'data', tmp_path / 'episodes', tmp_path / 'voices'
    (data / 'shows' / 'old_show').mkdir(parents=True)
    bible = {'show_name': 'Old Show', 'main_cast': [{'name': 'Aria', 'character_id': 'char_x1'},
                                                   {'name': 'Jalen'}]}
    (data / 'shows' / 'old_show' / 'series_bible.json').write_text(json.dumps(bible))
    for src in ('legacy_format.json', 'legacy_lexicon.json'):
        (data / 'shows' / src).write_text(open(f'data/shows/{src}', encoding='utf-8').read(),
                                          encoding='utf-8')
    (eps / 'ep1').mkdir(parents=True)
    (eps / 'ep1' / 'structure.json').write_text(json.dumps({'episode_id': 'ep1', 'series': 'Old Show'}))
    (eps / 'ep2').mkdir(parents=True)
    (eps / 'ep2' / 'structure.json').write_text(json.dumps({'episode_id': 'ep2', 'series': 'Unknown'}))
    voices.mkdir()
    (voices / 'voice_config.json').write_text(json.dumps({'characters': {'aria': {'kokoro_voice': 'af_bella'}}}))
    from story_os.legacy import _data
    _data.cache_clear()
    with patch('config.paths.DATA_DIR', data), patch('config.paths.EPISODES_DIR', eps), \
            patch('config.paths.VOICES_DIR', voices):
        yield data, eps
    _data.cache_clear()


def test_migrate_idempotent_and_rollback(legacy_world):
    from story_os import migrate
    data, eps = legacy_world
    before = {p: p.read_bytes() for p in [data / 'shows' / 'old_show' / 'series_bible.json',
                                          eps / 'ep1' / 'structure.json']}
    plan = migrate.run(dry_run=True)
    assert plan['status'] == 'planned'
    assert not (data / 'projects').exists()                          # dry run writes nothing
    res = migrate.run()
    assert res['status'] == 'migrated'
    proj = json.loads((data / 'projects' / 'old_show' / 'project.json').read_text())
    assert proj['mode'] == 'serialized_fiction' and proj['publishable'] is False
    bible = json.loads((data / 'shows' / 'old_show' / 'series_bible.json').read_text())
    assert [c['character_id'] for c in bible['main_cast']] == ['C01', 'C02']
    assert bible['main_cast'][0]['legacy_character_id'] == 'char_x1'
    ep1 = json.loads((eps / 'ep1' / 'structure.json').read_text())
    assert ep1['show_id'] == 'old_show' and 'project_id' not in ep1
    assert 'show_id' not in json.loads((eps / 'ep2' / 'structure.json').read_text())
    assert migrate.run(dry_run=True)['status'] == 'nothing to do'   # idempotent
    migrate.rollback(res['manifest'])
    for p, b in before.items():
        assert p.read_bytes() == b
    assert not (data / 'projects' / 'old_show' / 'project.json').exists()


def test_golden_prompts_identical_after_migration(legacy_world):
    from story_os import migrate
    from tests.golden_legacy import FIXTURE, render
    migrate.run()
    assert render() == json.loads(FIXTURE.read_text(encoding='utf-8'))
