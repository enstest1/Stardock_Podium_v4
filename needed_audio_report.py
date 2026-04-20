"""
Track missing sound effects and ambience for library-first audio.

Writes episodes/<episode_id>/needed_audio_assets.json when assets are
missing so creators can add files under assets/ before re-running mix.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def default_report_path(episodes_dir: Path, episode_id: str) -> Path:
    """Path for the needed-assets JSON for an episode."""
    return episodes_dir / episode_id / 'needed_audio_assets.json'


class NeededAudioTracker:
    """Collect missing SFX / ambience cues during a pipeline run."""

    def __init__(self, episode_id: str) -> None:
        self.episode_id = episode_id
        self.items: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def record_sound_effect(
        self,
        description: str,
        line_index: int,
        search_key: str,
        scene_number: Optional[int] = None,
    ) -> None:
        """Record a missing SFX line."""
        row = {
            'type': 'sound_effect',
            'description': description,
            'line_index': line_index,
            'search_key': search_key,
            'scene_number': scene_number,
            'suggested_glob': f'*{search_key}*.wav',
            'hint': 'Add a WAV or MP3 under assets/sound_effects/ matching '
                    'the suggested pattern.',
        }
        with self._lock:
            self.items.append(row)

    def record_ambience(
        self,
        keywords: List[str],
        scene_number: Optional[int] = None,
    ) -> None:
        """Record missing ambience for a scene."""
        row = {
            'type': 'ambience',
            'keywords': keywords,
            'scene_number': scene_number,
            'hint': 'Add ambience under assets/ambience/ using keyword '
                    'substrings in the filename.',
        }
        with self._lock:
            self.items.append(row)

    def write(self, path: Path) -> None:
        """Merge with any existing file and write JSON."""
        existing: List[Dict[str, Any]] = []
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    existing = data.get('needed', [])
            except (json.JSONDecodeError, OSError):
                existing = []
        merged = existing + self.items
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'episode_id': self.episode_id,
            'updated_at': time.time(),
            'needed': merged,
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
