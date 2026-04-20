"""Tests for needed audio asset tracking."""

import json
from pathlib import Path

from needed_audio_report import NeededAudioTracker, default_report_path


def test_tracker_write_merge(tmp_path):
    ep = 'ep_test123'
    t = NeededAudioTracker(ep)
    t.record_sound_effect('door slam', 3, 'door_slam', scene_number=1)
    path = tmp_path / 'needed.json'
    t.write(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    assert len(data['needed']) == 1
    assert data['needed'][0]['type'] == 'sound_effect'

    t2 = NeededAudioTracker(ep)
    t2.record_ambience(['bridge'], scene_number=2)
    t2.write(path)
    data2 = json.loads(path.read_text(encoding='utf-8'))
    assert len(data2['needed']) == 2


def test_default_report_path():
    p = default_report_path(Path('episodes'), 'ep_x')
    assert p.name == 'needed_audio_assets.json'
    assert 'ep_x' in str(p)
