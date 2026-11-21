"""Podcast hosts (PUB-002). ``publish`` is a dry run unless ``--live``.

``DryRunHost`` records every request it *would* make and writes the feed
locally to ``data/projects/<id>/feed/feed.xml``. A live host adapter
(Transistor or an S3-compatible bucket) is NOT implemented yet: it must be
written against the host's current API reference, and no host key exists in
this environment. Spotify / Apple are reached by submitting the RSS feed once,
by hand; there is no Spotify upload API.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Protocol


class PodcastHost(Protocol):
    def publish(self, meta: Dict[str, Any], channel: Dict[str, Any]) -> Dict[str, Any]: ...


MANUAL_STEPS = [
    'Spotify: open podcasters.spotify.com, choose "add an existing podcast", paste the RSS URL, '
    'verify by the e-mail code; done once per show.',
    'Apple: open podcastsconnect.apple.com, add a show with the RSS URL; review takes a few days.',
    'Never reuse an episode GUID for different audio; to replace audio, unpublish on the host.',
]


class DryRunHost:
    def __init__(self, project_id: str, base_url: str = 'https://example.invalid/podcast'):
        from story_os.projects import project_dir
        self.dir = project_dir(project_id) / 'feed'
        self.base_url = base_url.rstrip('/')
        self.requests: List[Dict[str, Any]] = []

    def _items_path(self) -> Path:
        return self.dir / 'items.json'

    def publish(self, meta: Dict[str, Any], channel: Dict[str, Any]) -> Dict[str, Any]:
        from episode_metadata import EpisodeMetadata
        self.dir.mkdir(parents=True, exist_ok=True)
        items = json.loads(self._items_path().read_text(encoding='utf-8')) \
            if self._items_path().exists() else []
        guid = meta['guid']
        audio_url = f"{self.base_url}/{guid}.mp3"
        existing = next((i for i in items if i['guid'] == guid), None)
        item = {'guid': guid, 'title': meta['title'], 'description': meta['description'],
                'enclosure_url': audio_url, 'length': meta['length'],
                'pub_date': (existing or {}).get('pub_date', time.time()),
                'duration': meta.get('duration') or 0, 'episode': meta.get('episode'),
                'season': meta.get('season'),
                'transcript_url': f"{self.base_url}/{guid}.vtt",
                'chapters_url': f"{self.base_url}/{guid}.chapters.json"}
        items = [i for i in items if i['guid'] != guid] + [item]
        items.sort(key=lambda i: (i.get('season') or 0, i.get('episode') or 0))
        self._items_path().write_text(json.dumps(items, indent=1), encoding='utf-8')
        self.requests += [{'method': 'PUT', 'url': audio_url, 'file': meta['audio_file'],
                           'bytes': meta['length']},
                          {'method': 'PUT', 'url': item['transcript_url']},
                          {'method': 'PUT', 'url': item['chapters_url']}]
        feed = EpisodeMetadata.build_show_feed(channel, items)
        (self.dir / 'feed.xml').write_text(feed, encoding='utf-8')
        (self.dir / 'requests.log.json').write_text(json.dumps(self.requests, indent=1),
                                                    encoding='utf-8')
        return {'feed': str(self.dir / 'feed.xml'), 'items': len(items),
                'requests': self.requests, 'manual_steps': MANUAL_STEPS}


def publish_episode(episode_id: str, *, live: bool = False, authorise: bool = False) -> Dict[str, Any]:
    from publish.assets import build_publish_assets
    from publish.rights import assert_publishable, build_rights_report, load_waivers
    from story_os import projects
    report = build_rights_report(episode_id)
    meta = build_publish_assets(episode_id)
    pid = meta['project_id']
    project = projects.load_project(pid)
    fmt = projects.load_format(pid)
    channel = {'title': project.title, 'description': f"{fmt.tagline or project.idea}\n\n"
               'Produced with AI-generated writing and voices.',
               'language': project.language, 'author': 'Stardock Podium',
               'itunes_type': 'serial' if project.capability('feed_type') == 'serial' else 'episodic',
               'category': 'Fiction' if project.capability('outline') == 'scene_cards' else 'Education',
               'image_url': 'https://example.invalid/podcast/cover.jpg'}
    result = {'rights': report, 'metadata': meta}
    if live:
        if not authorise:
            raise PermissionError('live publish needs --i-authorise-publication')
        result['waivers_used'] = assert_publishable(report, load_waivers(pid))
        raise NotImplementedError('No live host adapter is configured yet (see publish/hosts.py).')
    result['dry_run'] = DryRunHost(pid).publish(meta, channel)
    return result
