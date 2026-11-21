"""Per-show theme music (AUDIO-007, music provider part).

Owns ``data/projects/<id>/music/theme_intro.mp3`` / ``theme_outro.mp3`` and
the rights record stored in the project's ``format.json`` (``theme_rights``).

Provider: ElevenLabs Music, ``POST https://api.elevenlabs.io/v1/music``
(body: ``prompt``, ``music_length_ms`` 3000-600000, ``force_instrumental``).
API access needs a paid ElevenLabs plan; free-plan output is non-commercial
with attribution. When the provider refuses, nothing is written and the
caller keeps the studio's default theme.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ELEVEN_MUSIC_URL = 'https://api.elevenlabs.io/v1/music'
ELEVEN_SUB_URL = 'https://api.elevenlabs.io/v1/user/subscription'
INTRO_MS = 20000
OUTRO_MS = 12000


class MusicUnavailable(RuntimeError):
    """Provider missing, refused (plan/credits) or failed."""


def _key() -> str:
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        raise MusicUnavailable('ELEVENLABS_API_KEY is not set')
    return key


def eleven_plan() -> Dict[str, Any]:
    req = urllib.request.Request(ELEVEN_SUB_URL, headers={'xi-api-key': _key()})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    return {'tier': d.get('tier'), 'status': d.get('status'),
            'character_count': d.get('character_count'),
            'character_limit': d.get('character_limit')}


def compose(prompt: str, length_ms: int, out_path: Path,
            opener=urllib.request.urlopen) -> Path:
    """Generate one instrumental track. Raises MusicUnavailable on refusal."""
    body = json.dumps({'prompt': prompt, 'music_length_ms': int(length_ms),
                       'force_instrumental': True}).encode('utf-8')
    req = urllib.request.Request(
        ELEVEN_MUSIC_URL + '?output_format=mp3_44100_128', data=body,
        headers={'xi-api-key': _key(), 'Content-Type': 'application/json'},
        method='POST')
    try:
        with opener(req, timeout=300) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        detail = e.read()[:400].decode('utf-8', 'replace')
        raise MusicUnavailable(f'ElevenLabs Music HTTP {e.code}: {detail}') from e
    except urllib.error.URLError as e:
        raise MusicUnavailable(f'ElevenLabs Music unreachable: {e}') from e
    if len(data) < 2000:
        raise MusicUnavailable(f'ElevenLabs Music returned {len(data)} bytes')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return out_path


def import_show_theme(project_id: str, intro_file: str,
                      outro_file: Optional[str] = None, *,
                      provider: str = 'Suno (web)', commercial_ok: bool = False,
                      attribution: str = '') -> Dict[str, Any]:
    """Use music you made elsewhere (e.g. on Suno's website) as a show theme.

    The files are converted to MP3 in the project's music folder; the outro
    defaults to the last 12 seconds of the intro track. ``commercial_ok``
    must reflect the licence you hold (Suno: paid plan at creation time).
    """
    import subprocess
    from story_os import projects
    fmt = projects.load_format(project_id)
    music_dir = projects.project_dir(project_id) / 'music'
    music_dir.mkdir(parents=True, exist_ok=True)
    intro, outro = music_dir / 'theme_intro.mp3', music_dir / 'theme_outro.mp3'
    for src, dst, extra in ((intro_file, intro, []),
                            (outro_file or intro_file, outro,
                             [] if outro_file else ['-sseof', '-12'])):
        if not Path(src).is_file():
            raise FileNotFoundError(src)
        cmd = ['ffmpeg', '-nostdin', '-y', '-loglevel', 'error', *extra,
               '-i', str(src), '-ac', '2', '-ar', '44100', '-b:a', '256k', str(dst)]
        subprocess.run(cmd, check=True)
    fmt.theme_intro_path, fmt.theme_outro_path = intro.as_posix(), outro.as_posix()
    fmt.theme_rights = {'provider': provider,
                        'commercial_ok': 'yes' if commercial_ok else 'no',
                        'attribution': attribution, 'source_file': str(intro_file)}
    projects.atomic_write_json(projects.project_dir(project_id) / 'format.json',
                               fmt.model_dump())
    if not commercial_ok:
        project = projects.load_project(project_id)
        project.publishable = False
        projects.atomic_write_json(projects.project_dir(project_id) / 'project.json',
                                   project.model_dump())
    return {'status': 'imported', 'intro': str(intro), 'outro': str(outro),
            'rights': fmt.theme_rights}


def make_show_theme(project_id: str, *, prompt: Optional[str] = None,
                    regenerate: bool = False) -> Dict[str, Any]:
    """Create intro/outro themes for a project and record their rights.

    Returns a status dict; never raises for provider refusal.
    """
    from story_os import projects
    fmt = projects.load_format(project_id)
    project = projects.load_project(project_id)
    music_dir = projects.project_dir(project_id) / 'music'
    intro, outro = music_dir / 'theme_intro.mp3', music_dir / 'theme_outro.mp3'
    if intro.exists() and outro.exists() and not regenerate:
        return {'status': 'exists', 'intro': str(intro), 'outro': str(outro)}
    brief = (prompt or fmt.theme_prompt or
             f'Instrumental podcast theme for {fmt.genre_phrase}; memorable '
             'motif, clean ending').strip()
    try:
        plan = eleven_plan()
    except Exception as e:
        plan = {'tier': 'unknown', 'error': str(e)}
    try:
        compose(f'{brief}. Podcast opening theme, builds then resolves.',
                INTRO_MS, intro)
        compose(f'{brief}. Short closing sting version of the same theme, '
                'gentle ending.', OUTRO_MS, outro)
    except MusicUnavailable as e:
        logger.warning('Theme music not generated for %s: %s', project_id, e)
        return {'status': 'unavailable', 'reason': str(e), 'plan': plan,
                'fallback': 'studio default theme'}
    commercial = (plan.get('tier') or 'free') != 'free'
    fmt.theme_intro_path = intro.as_posix()
    fmt.theme_outro_path = outro.as_posix()
    fmt.theme_prompt = brief
    fmt.theme_rights = {
        'provider': 'ElevenLabs Music', 'plan_tier': str(plan.get('tier')),
        'commercial_ok': 'yes' if commercial else 'no',
        'attribution': '' if commercial else 'Eleven Music',
    }
    projects.atomic_write_json(projects.project_dir(project_id) / 'format.json',
                               fmt.model_dump())
    if not commercial:
        project.publishable = False
        projects.atomic_write_json(projects.project_dir(project_id) / 'project.json',
                                   project.model_dump())
    return {'status': 'created', 'intro': str(intro), 'outro': str(outro),
            'rights': fmt.theme_rights}
