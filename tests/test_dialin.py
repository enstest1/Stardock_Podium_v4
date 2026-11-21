"""Dial-in knobs: mix presets, pacing presets, phone style swap, settings file."""

import json

import pytest

import audio_dialin
import audio_mix
from audio_timeline import PACING_PRESETS, VOICE_FX, build_timeline


def _script():
    return {'scenes': [{'scene_number': 1, 'lines': [
        {'type': 'dialogue', 'character': 'A', 'content': 'hi', 'line_id': 'l1'},
        {'type': 'dialogue', 'character': 'B', 'content': 'yo', 'line_id': 'l2', 'fx': 'phone'},
    ]}, {'scene_number': 2, 'lines': [
        {'type': 'dialogue', 'character': 'A', 'content': 'ok', 'line_id': 'l3'}]}]}


LA = {k: {'path': f'{k}.wav', 'duration': 1.0} for k in ('l1', 'l2', 'l3')}


def test_mix_presets_resolve_and_override():
    base = audio_mix.mix_settings(None)
    assert base['bus_gain_db'] == audio_mix.BUS_GAIN_DB
    dry = audio_mix.mix_settings('dry')
    assert dry['bus_gain_db']['ambience'] < base['bus_gain_db']['ambience']
    custom = audio_mix.mix_settings({'preset': 'dry', 'bus_gain_db': {'sfx': 1.0}})
    assert custom['bus_gain_db']['sfx'] == 1.0
    assert custom['bus_gain_db']['ambience'] == dry['bus_gain_db']['ambience']


def test_pacing_changes_gaps_and_fx_map_swaps_phone():
    nat = build_timeline(_script(), LA, lambda *a: None)
    tight = build_timeline(_script(), LA, lambda *a: None, pacing='tight',
                           fx_map={'phone': 'phone_old'})
    gap = lambda tl: tl['clips'][1]['start'] - (tl['clips'][0]['start'] + 1.0)
    assert gap(nat) == pytest.approx(PACING_PRESETS['natural']['line_gap'])
    assert gap(tight) == pytest.approx(PACING_PRESETS['tight']['line_gap'])
    assert tight['duration'] < nat['duration']
    assert nat['clips'][1]['fx'] == 'phone' and tight['clips'][1]['fx'] == 'phone_old'
    assert all(s in VOICE_FX for s in audio_dialin.PHONE_STYLES)


def test_settings_file_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(audio_dialin, '_path', lambda pid: tmp_path / pid / 'mix.json')
    assert audio_dialin.load_settings('p') == audio_dialin.DEFAULTS
    cur = audio_dialin.save_settings('p', mix='intimate', pacing='tight', phone_style='phone_old')
    assert json.loads((tmp_path / 'p' / 'mix.json').read_text())['mix'] == 'intimate'
    assert audio_dialin.fx_map(cur) == {'phone': 'phone_old'}
    with pytest.raises(ValueError):
        audio_dialin.save_settings('p', mix='nope')
    with pytest.raises(ValueError):
        audio_dialin.save_settings('p', loudness_lufs=-3)


def test_crop_keeps_window_only():
    tl = {'clips': [{'bus': 'dialogue', 'path': 'a', 'start': 0.0, 'length': 2.0},
                    {'bus': 'dialogue', 'path': 'b', 'start': 5.0, 'length': 4.0},
                    {'bus': 'dialogue', 'path': 'c', 'start': 20.0, 'length': 1.0}],
          'chapters': [], 'duration': 21}
    out = audio_dialin.crop(tl, 4.0, 7.0)
    assert [c['path'] for c in out['clips']] == ['b']
    assert out['clips'][0]['start'] == 1.0 and out['clips'][0]['length'] == 2.0
