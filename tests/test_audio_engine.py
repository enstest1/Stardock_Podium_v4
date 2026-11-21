"""AUDIO-002..005: cue parser, timeline, mixer, mastering, asset library."""
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import audio_assets
import audio_mix
from audio_timeline import build_timeline, parse_cue

SR = audio_mix.SR


@pytest.mark.parametrize('text,track,sound,opts', [
    ('SFX: a kettle starts to whistle', 'sfx', 'a kettle starts to whistle', {}),
    ('(sfx:door slams | wait)', 'sfx', 'door slams', {'wait': True}),
    ('AMB: steady rain on a tin roof', 'ambience', 'steady rain on a tin roof', {}),
    ('Ambience: crowd murmur', 'ambience', 'crowd murmur', {}),
    ('MUS: low uneasy piano | dur: 8', 'music', 'low uneasy piano', {'dur': '8'}),
    ('Music: "warm strings" | dur:4 | wait', 'music', 'warm strings', {'dur': '4', 'wait': True}),
    ('brass slot flap snapping shut', 'sfx', 'brass slot flap snapping shut', {}),
    ('(footsteps on gravel)', 'sfx', 'footsteps on gravel', {}),
])
def test_parse_cue_table(text, track, sound, opts):
    cue = parse_cue(text)
    assert (cue['track'], cue['sound'], cue['options']) == (track, sound, opts)


def test_parse_cue_empty():
    assert parse_cue('') is None and parse_cue('SFX:  ') is None


def tone(path: Path, seconds: float, freq: float = 440.0, amp: float = 0.3):
    t = np.arange(int(seconds * SR)) / SR
    sf.write(path, (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32), SR,
             format='WAV')
    return {'path': str(path), 'duration': seconds}


@pytest.fixture
def fixture_scene(tmp_path):
    la = {'l1': tone(tmp_path / 'l1.wav', 1.0, 300),
          'l2': tone(tmp_path / 'l2.wav', 1.5, 500)}
    amb = tone(tmp_path / 'amb.wav', 3.0, 120, 0.2)
    sfx = tone(tmp_path / 'sfx.wav', 0.5, 2000, 0.5)
    script = {'scenes': [{'scene_number': 1, 'lines': [
        {'type': 'sound_effect', 'content': 'AMB: rain on a roof', 'line_id': 'c0'},
        {'type': 'dialogue', 'character': 'A', 'content': 'x', 'line_id': 'l1'},
        {'type': 'sound_effect', 'content': 'SFX: door slams | wait', 'line_id': 'c1'},
        {'type': 'dialogue', 'character': 'B', 'content': 'y', 'line_id': 'l2'},
    ]}]}

    def resolve(kind, text, seconds):
        src = amb if kind == 'ambience' else sfx
        return {'file': src['path'], 'duration': src['duration'], 'sha': kind}
    return script, la, resolve


def test_timeline_places_clips_exactly(fixture_scene):
    script, la, resolve = fixture_scene
    tl = build_timeline(script, la, resolve)
    d = [c for c in tl['clips'] if c['bus'] == 'dialogue']
    s = [c for c in tl['clips'] if c['bus'] == 'sfx']
    a = [c for c in tl['clips'] if c['bus'] == 'ambience']
    assert d[0]['start'] == 0.0
    assert s[0]['start'] == pytest.approx(1.0 + 0.15)          # after line 1
    assert d[1]['start'] >= s[0]['start'] + 0.5                # 'wait' honoured
    assert a[0]['loop'] and a[0]['length'] > 3.0               # bed covers scene
    assert tl['missing'] == []
    assert build_timeline(script, la, resolve) == tl           # deterministic


def test_missing_cue_is_reported_not_dropped(fixture_scene):
    script, la, _ = fixture_scene
    tl = build_timeline(script, la, lambda *a: None)
    kinds = sorted(m['kind'] for m in tl['missing'])
    assert kinds == ['ambience', 'sfx']


def test_render_onset_ducking_and_peak(fixture_scene, tmp_path):
    script, la, resolve = fixture_scene
    tl = build_timeline(script, la, resolve)
    out = audio_mix.render(tl, tmp_path / 'out')
    mix, sr = sf.read(out['mix'])
    assert sr == SR and mix.shape[1] == 2
    assert np.abs(mix).max() <= audio_mix.db(audio_mix.LIMIT_DB) + 1e-3
    dlg, _ = sf.read(out['stems']['dialogue'])
    l2 = [c for c in tl['clips'] if c.get('line_id') == 'l2'][0]
    s2 = int(round(l2['start'] * SR))
    assert np.all(dlg[s2 - 50:s2, 0] == 0)                     # silence before
    assert dlg[s2 + 1, 0] != 0                                 # onset exact (1 sample)
    amb, _ = sf.read(out['stems']['ambience'])
    a_start = int((tl['clips'][0]['start'] + 1.2) * SR)        # bed before speech
    speaking = slice(int(0.4 * SR), int(0.9 * SR))
    gap_lvl = np.sqrt(np.mean(amb[int(tl['duration'] * SR) - int(0.9 * SR):
                                  int(tl['duration'] * SR) - int(0.6 * SR)] ** 2) + 1e-12)
    duck_lvl = np.sqrt(np.mean(amb[speaking] ** 2) + 1e-12)
    assert 20 * np.log10(duck_lvl / gap_lvl) < -4.0            # ducked under speech
    again = audio_mix.render(tl, tmp_path / 'out2')
    assert np.array_equal(sf.read(again['mix'])[0], mix)       # bit-exact repeat


def test_loop_seam_has_no_click():
    x = np.tile(np.linspace(-0.2, 0.2, SR, dtype=np.float32)[:, None], (1, 2))
    y = audio_mix.loop_to_length(x, int(3.5 * SR))
    assert len(y) == int(3.5 * SR)
    assert np.abs(np.diff(y[:, 0])).max() < 0.05


def test_master_hits_loudness_target(fixture_scene, tmp_path):
    script, la, resolve = fixture_scene
    out = audio_mix.render(build_timeline(script, la, resolve), tmp_path / 'o')
    res = audio_mix.master(out['mix'], str(tmp_path / 'ep.mp3'),
                           metadata={'title': 'T'})
    assert res['ok'], res
    assert abs(res['lufs_i'] + 16) <= 1.0 and res['true_peak_dbtp'] <= -0.7
    assert res['encodes'] == 1


# ------------------------------------------------------------- assets ----

@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setenv('STARDOCK_ASSET_LIBRARY', str(tmp_path / 'lib'))
    return tmp_path


def test_ingest_dedup_match_and_generate(library):
    a = tone(library / 'hum.wav', 1.0)['path']
    rec = audio_assets.ingest(Path(a), 'sfx', 'low engine hum',
                              source='legacy', rights={'commercial_ok': 'unknown'})
    again = audio_assets.ingest(Path(a), 'sfx', 'duplicate name',
                                source='legacy', rights={})
    assert again['sha'] == rec['sha'] and len(audio_assets.load_index()['assets']) == 1
    hit = audio_assets.match('sfx', 'the gentle hum of the engines')
    assert hit and hit['sha'] == rec['sha']
    assert audio_assets.match('ambience', 'the gentle hum of the engines') is None

    calls = []

    def fake_gen(prompt, seconds, out):
        calls.append(prompt)
        tone(out, seconds, 900)
        return out
    gen = audio_assets.resolve('sfx', 'a kettle starts to whistle', seconds=1.0,
                               generator=fake_gen)
    assert gen['source'] == 'generated' and len(calls) == 1
    cached = audio_assets.resolve('sfx', 'kettle whistles', generator=fake_gen)
    assert cached['sha'] == gen['sha'] and len(calls) == 1      # reused, not regenerated
    report = audio_assets.rights_report()
    assert 'low engine hum' in report['unknown']


@pytest.mark.parametrize('cue', ['rain dripping in a rainforest canopy',
                                 'a hotel corridor with a humming ice machine',
                                 'a radio studio with a ticking clock'])
def test_generic_settings_resolve_or_report(library, cue):
    got = audio_assets.resolve('ambience', cue, generate=False)
    assert got is None                       # empty library -> reported upstream
