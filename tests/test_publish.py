"""PUB-001..003 (T14 with fixtures): assets, feed, rights gate."""
import json
import re
import xml.dom.minidom
from pathlib import Path

import pytest

from publish import assets, rights
from publish.hosts import DryRunHost


def test_vtt_monotonic_with_speakers():
    script = {'scenes': [{'lines': [
        {'line_id': 'a', 'type': 'narration', 'content': 'Night.'},
        {'line_id': 'b', 'type': 'dialogue', 'character': 'MARA', 'content': 'Hello.'}]}]}
    tl = {'clips': [{'bus': 'dialogue', 'line_id': 'b', 'start': 3.0, 'length': 1.0},
                    {'bus': 'dialogue', 'line_id': 'a', 'start': 1.0, 'length': 1.5},
                    {'bus': 'sfx', 'start': 0.5, 'length': 1}]}
    tr = assets.build_transcript(script, tl)
    times = re.findall(r'(\d\d:\d\d:\d\d\.\d{3}) --> (\d\d:\d\d:\d\d\.\d{3})', tr['vtt'])
    assert tr['vtt'].startswith('WEBVTT') and times == sorted(times)
    assert '<v Narrator>Night.' in tr['vtt'] and '<v Mara>Hello.' in tr['vtt']


def test_chapters_shape_and_spoiler_rule():
    ep = {'scenes': [{'card': {'setting': 'The vault where the treasure hides'}},
                     {'card': {'setting': 'Kitchen, midnight'}}]}
    tl = {'chapters': [{'title': 'Intro', 'start': 0}, {'title': 'Scene 1', 'start': 5},
                       {'title': 'Scene 2', 'start': 40}]}
    ch = assets.build_chapters(ep, tl, [{'statement': 'Where is the hidden treasure?'}])
    assert ch['version'] and [c['startTime'] for c in ch['chapters']] == [0, 5, 40]
    titles = [c['title'] for c in ch['chapters']]
    assert titles[1] == 'Scene 1'                     # spoiler (treasure) kept generic
    assert titles[2] == 'Kitchen'
    desc = assets.build_description({'episode_id': 'e', 'theme': 'A heist'}, None,
                                    'AI disclosure.', [{'statement': 'the treasure'}])
    assert 'AI disclosure.' in desc


def test_feed_valid_enclosure_and_stable_guid(tmp_path, monkeypatch):
    monkeypatch.setattr('config.paths.DATA_DIR', tmp_path)
    audio = tmp_path / 'ep.mp3'
    audio.write_bytes(b'x' * 1234)
    meta = {'guid': 'ep_1', 'title': 'Pilot & <Friends>', 'description': 'd', 'length': 1234,
            'audio_file': str(audio), 'duration': 61, 'episode': 1, 'season': 1}
    ch = {'title': 'Show', 'itunes_type': 'serial'}
    host = DryRunHost('p')
    first = host.publish(meta, ch)
    pub1 = json.loads((host.dir / 'items.json').read_text())[0]['pub_date']
    second = DryRunHost('p').publish(meta, ch)
    feed = Path(second['feed']).read_text()
    doc = xml.dom.minidom.parseString(feed)
    items = doc.getElementsByTagName('item')
    assert len(items) == 1                                   # same GUID, not duplicated
    enc = items[0].getElementsByTagName('enclosure')[0]
    assert enc.getAttribute('length') == '1234'
    assert items[0].getElementsByTagName('guid')[0].firstChild.data == 'ep_1'
    assert json.loads((host.dir / 'items.json').read_text())[0]['pub_date'] == pub1
    assert '<itunes:type>serial</itunes:type>' in feed and 'Pilot &amp; &lt;Friends&gt;' in feed


def test_rights_gate_blocks_and_waivers():
    rep = {'blocking': ['XTTS voice cloning (Coqui CPML, non-commercial) is in use',
                        'sound asset not cleared for commercial use: rain']}
    with pytest.raises(rights.NotPublishable):
        rights.assert_publishable(rep, [])
    with pytest.raises(rights.NotPublishable):           # waiver without date is ignored
        rights.assert_publishable(rep, [{'item': rep['blocking'][0], 'by': 'me'}])
    waivers = [{'item': b, 'by': 'Producer', 'date': '2026-11-20'} for b in rep['blocking']]
    assert len(rights.assert_publishable(rep, waivers)) == 2
    assert rights.assert_publishable({'blocking': []}) == []


def test_live_publish_requires_authorisation(monkeypatch):
    from publish import hosts
    monkeypatch.setattr('publish.rights.build_rights_report', lambda e: {'blocking': [], 'publishable': True})
    monkeypatch.setattr('publish.assets.build_publish_assets', lambda e: {'project_id': 'p'})
    with pytest.raises(Exception):
        hosts.publish_episode('e', live=True, authorise=False)
