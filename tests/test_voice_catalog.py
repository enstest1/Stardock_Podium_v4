"""Voice catalog, casting and design (AUDIO-006 voice part). No network."""
import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import voice_catalog as vcat
from story_os import llm


@pytest.fixture
def voices_dir(tmp_path):
    vd = tmp_path / 'voices'
    (vd / 'samples' / 'OG').mkdir(parents=True)
    (vd / 'samples' / 'OG' / 'abc.wav').write_bytes(b'RIFF')
    (vd / 'samples' / 'OG' / 'abc.mp3').write_bytes(b'ID3')
    (vd / 'registry.json').write_text(json.dumps({
        'voice_1': {'name': 'Old', 'voice_id': 'EL123'}}))
    (vd / 'voice_config.json').write_text(json.dumps({
        'characters': {'captain': {'kokoro_voice': 'af_bella'}}}))
    with patch('config.paths.VOICES_DIR', vd):
        yield vd
    llm.set_test_backend(None)


class FakeTensor:
    def __init__(self, v):
        self.v = v

    def __mul__(self, w):
        return FakeTensor(self.v * w)

    def __add__(self, o):
        return FakeTensor(self.v + o.v)


@pytest.fixture
def fake_kokoro():
    eng = MagicMock()
    eng._pipeline.load_single_voice.side_effect = lambda n: FakeTensor(
        float(len(n)))
    saved = {}
    with patch('tts_engine.get_kokoro_engine', return_value=eng), \
            patch('torch.save', side_effect=lambda t, p: saved.update(
                {str(p): t.v})):
        yield saved


def test_refresh_catalogs_presets_samples_legacy_and_usage(voices_dir):
    cat = vcat.refresh_catalog()
    v = cat['voices']
    assert len([x for x in v.values() if x['source'] == 'preset']) == len(vcat.PRESETS)
    samples = [x for x in v.values() if x['source'] == 'sample']
    assert len(samples) == 1                       # wav+mp3 counted once
    assert samples[0]['publishable'] is False and samples[0]['auto_cast'] is False
    assert v['legacy:voice_1']['auto_cast'] is False
    assert {'project_id': 'legacy_global', 'character': 'captain'} in \
        v['kokoro:af_bella']['used_by']
    assert vcat.catalog_path().exists()


def test_samples_are_never_castable(voices_dir):
    cat = vcat.refresh_catalog()
    assert all(x['source'] in ('preset', 'designed') for x in vcat.castable(cat))


def test_design_voice_blends_and_catalogues(voices_dir, fake_kokoro):
    cat = vcat.refresh_catalog()
    entry = vcat.design_voice(cat, 'Ember Host', {'af_bella': 3, 'af_sarah': 1},
                              project_id='p1')
    assert entry['voice_id'] == 'design:ember_host'
    assert entry['recipe'] == {'af_bella': 0.75, 'af_sarah': 0.25}
    assert entry['gender'] == 'female' and entry['publishable'] is True
    assert entry['kokoro_voice'].endswith('voices/designed/ember_host.pt')
    again = vcat.design_voice(cat, 'Ember Host', {'af_bella': 1, 'af_sky': 1})
    assert again['voice_id'] == 'design:ember_host_2'
    with pytest.raises(ValueError):
        vcat.normalise_recipe({'af_bella': 1})


SPEAKERS = [
    {'key': 'narrator', 'name': 'Narrator', 'gender': 'male', 'accent': 'british', 'lead': True},
    {'key': 'ada', 'name': 'Ada', 'gender': 'female', 'accent': 'british', 'lead': True},
    {'key': 'tom', 'name': 'Tom', 'gender': 'male', 'accent': 'american'},
    {'key': 'extra', 'name': 'Extra', 'gender': 'female', 'accent': 'american'},
]


def test_rule_casting_distinct_gender_matched_and_avoids_other_shows(voices_dir):
    first = vcat.cast_show('show_a', SPEAKERS, use_llm=False)
    second = vcat.cast_show('show_b', SPEAKERS, use_llm=False)
    for picks in (first, second):
        assert len(set(picks.values())) == len(SPEAKERS)
        for sp in SPEAKERS:
            assert vcat.load_catalog()['voices'][picks[sp['key']]]['gender'] == sp['gender']
    assert not set(first.values()) & set(second.values())
    cat = vcat.load_catalog()
    assert {'project_id': 'show_b', 'character': 'ada'} in \
        cat['voices'][second['ada']]['used_by']


def test_llm_casting_designs_and_rejects_bad_choices(voices_dir, fake_kokoro):
    plan = {'cast': [
        {'key': 'narrator', 'design': {'name': 'Night Narrator',
                                       'recipe': {'bm_fable': 0.6, 'bm_lewis': 0.4}}},
        {'key': 'ada', 'voice_id': 'kokoro:am_michael'},          # wrong gender
        {'key': 'tom', 'design': {'name': 'Bad', 'recipe': {'am_puck': 1, 'af_sky': 1}}},
        {'key': 'extra', 'voice_id': 'kokoro:af_nicole'},
    ]}
    llm.set_test_backend(lambda *a, **k: json.dumps(plan))
    picks = vcat.cast_show('show_c', SPEAKERS)
    cat = vcat.load_catalog()
    assert picks['narrator'] == 'design:night_narrator'
    assert cat['voices'][picks['ada']]['gender'] == 'female'
    assert cat['voices'][picks['tom']]['gender'] == 'male'      # mixed blend refused
    assert picks['extra'] == 'kokoro:af_nicole'
    assert len(set(picks.values())) == 4


def test_project_cast_voices_writes_catalog_ids(voices_dir, tmp_path):
    from story_os import projects
    ident = projects.Identity.model_validate({
        'cast': [{'name': 'Mara Okafor', 'gender': 'female'},
                 {'name': 'Jon Pike', 'gender': 'male'}]})
    voices = projects.cast_voices('p9', ident, use_llm=False)
    ids = [c['voice_id'] for c in voices['characters'].values()]
    assert len(set(ids)) == 4 and all(i.startswith('kokoro:') for i in ids)
    assert voices['aliases']['mara'] == 'mara_okafor'
    assert ident.cast[0].kokoro_voice == voices['characters']['mara_okafor']['kokoro_voice']


# ------------------------------------------------------------- music ----

def test_music_compose_writes_file_and_refusal_is_reported(tmp_path, monkeypatch):
    from story_os import music
    monkeypatch.setenv('ELEVENLABS_API_KEY', 'k')
    resp = MagicMock()
    resp.__enter__.return_value.read.return_value = b'x' * 5000
    sent = {}

    def ok_opener(req, timeout=0):
        sent['body'] = json.loads(req.data)
        sent['url'] = req.full_url
        return resp
    out = music.compose('dark folk', 20000, tmp_path / 'a.mp3', opener=ok_opener)
    assert out.read_bytes() == b'x' * 5000
    assert sent['url'].startswith('https://api.elevenlabs.io/v1/music')
    assert sent['body'] == {'prompt': 'dark folk', 'music_length_ms': 20000,
                            'force_instrumental': True}

    def refuse(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 402, 'pay', {}, None)
    with pytest.raises(music.MusicUnavailable):
        music.compose('x', 3000, tmp_path / 'b.mp3', opener=refuse)
    assert not (tmp_path / 'b.mp3').exists()


def test_import_show_theme_from_own_file(tmp_path):
    import subprocess
    from story_os import projects, music
    from story_os.project_models import ProjectConfig
    src = tmp_path / 'suno_song.wav'
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'sine=frequency=440:duration=20', str(src)], check=True)
    with patch('config.paths.DATA_DIR', tmp_path):
        cfg = ProjectConfig(project_id='p', show_id='p', title='P', idea='i',
                            mode='anthology')
        projects.atomic_write_json(projects.project_dir('p') / 'project.json',
                                   cfg.model_dump())
        res = music.import_show_theme('p', str(src), commercial_ok=False)
        fmt = projects.load_format('p')
        assert Path(fmt.theme_intro_path).is_file()
        assert Path(fmt.theme_outro_path).is_file()
        assert fmt.theme_rights['provider'] == 'Suno (web)'
        assert projects.load_project('p').publishable is False
    assert res['status'] == 'imported'
