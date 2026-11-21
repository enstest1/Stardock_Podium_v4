"""migrate-shows: legacy shows -> v5 show store + projects (STORYOS-001).

For every ``data/shows/<show_id>/`` folder:
  * ``data/projects/<show_id>/project.json``  (mode serialized_fiction,
    original false, publishable false) + ``legacy.json`` (legacy_namespace)
  * ``format.json`` holding the legacy Star Trek wording, ``voices.json`` copied
    from the global voice config, ``bible.json`` from the show's main cast
  * ``character_id`` C01, C02 ... on each ``main_cast`` entry of the bible
  * ``show_id`` + ``season_number`` on each legacy ``structure.json`` whose
    series maps to the show. Deliberately NOT ``project_id``: that would send
    old episodes through the new pipeline and change their prompts (the golden
    prompt test must stay byte-identical).
  * ``data/shows/index.json`` (slug -> show_id, show_id -> project_id) and
    ``data/active_show.json`` when missing.

Every run writes ``backups/migrate-<ts>.tar.gz`` + ``.manifest.json`` first;
``--rollback <manifest>`` restores modified files and deletes created ones.
A second run reports "nothing to do". This file may name the legacy franchise
(BASE-003 grep exemption).
"""

from __future__ import annotations

import json
import re
import shutil
import tarfile
import time
from pathlib import Path
from typing import Any, Dict, List

LEGACY_SLUGS = {'main_series': 'star_trek_horizon', 'star_trek_horizon': 'star_trek_horizon'}


def _paths():
    from config.paths import DATA_DIR, EPISODES_DIR, VOICES_DIR
    return Path(DATA_DIR), Path(EPISODES_DIR), Path(VOICES_DIR)


def slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')


def plan() -> List[Dict[str, Any]]:
    data, episodes, voices = _paths()
    actions: List[Dict[str, Any]] = []
    shows = [d for d in (data / 'shows').glob('*') if d.is_dir()]
    index_p = data / 'shows' / 'index.json'
    index = json.loads(index_p.read_text(encoding='utf-8')) if index_p.exists() else {}
    slugs = dict(index.get('slugs') or {})
    projects = dict(index.get('projects') or {})
    for show in shows:
        sid = show.name
        pdir = data / 'projects' / sid
        if not (pdir / 'project.json').exists():
            actions.append({'op': 'create_project', 'show_id': sid, 'path': str(pdir)})
        bible_p = show / 'series_bible.json'
        if bible_p.exists():
            bible = json.loads(bible_p.read_text(encoding='utf-8'))
            missing = [c.get('name') for c in bible.get('main_cast', []) if not c.get('character_id', '').startswith('C')]
            if missing:
                actions.append({'op': 'cast_ids', 'show_id': sid, 'path': str(bible_p),
                                'characters': missing})
            for name in (bible.get('show_name'), bible.get('series_name'), sid):
                if name and slug(name) not in slugs:
                    slugs[slug(name)] = sid
        projects.setdefault(sid, sid)
    for k, v in LEGACY_SLUGS.items():
        if (data / 'shows' / v).is_dir():
            slugs.setdefault(k, v)
    if slugs != (index.get('slugs') or {}) or projects != (index.get('projects') or {}):
        actions.append({'op': 'index', 'path': str(index_p), 'slugs': slugs, 'projects': projects})
    for st in sorted(episodes.glob('*/structure.json')):
        ep = json.loads(st.read_text(encoding='utf-8'))
        if ep.get('project_id') or ep.get('show_id'):
            continue
        sid = slugs.get(slug(ep.get('series', '')))
        if sid:
            actions.append({'op': 'episode_show_id', 'path': str(st), 'show_id': sid})
        else:
            actions.append({'op': 'unmapped_episode', 'path': str(st),
                            'series': ep.get('series'), 'note': 'left unchanged'})
    if not (data / 'active_show.json').exists() and shows:
        actions.append({'op': 'active_show', 'path': str(data / 'active_show.json'),
                        'show_id': shows[0].name})
    return actions


def _legacy_format() -> Dict[str, Any]:
    from story_os.legacy import legacy
    from story_os.profile import FormatProfile
    return FormatProfile(
        original=False, writer_persona='an expert screenwriter for audio dramas',
        cast_designer_persona=legacy('cast_system'),
        title_prompt_noun=legacy('title_prompt_prefix'),
        genre_phrase='a Star Trek-style podcast episode',
        outro_template=legacy('outro_text'),
        number_rules=legacy('number_labels'), use_theme_music=True).model_dump()


def run(dry_run: bool = False) -> Dict[str, Any]:
    acts = plan()
    real = [a for a in acts if a['op'] != 'unmapped_episode']
    if dry_run or not real:
        return {'dry_run': dry_run, 'actions': acts,
                'status': 'nothing to do' if not real else 'planned'}
    data, episodes, voices = _paths()
    ts = time.strftime('%Y%m%d-%H%M%S')
    bdir = data.parent / 'backups'
    bdir.mkdir(parents=True, exist_ok=True)
    tar_p = bdir / f'migrate-{ts}.tar.gz'
    modified = sorted({a['path'] for a in real if a['op'] in ('cast_ids', 'episode_show_id', 'index')
                       and Path(a['path']).exists()})
    with tarfile.open(tar_p, 'w:gz') as tar:
        for p in modified:
            tar.add(p, arcname=Path(p).resolve().as_posix().lstrip('/').replace(':', ''))
    created: List[str] = []
    from story_os.projects import atomic_write_json
    from story_os.project_models import ProjectConfig
    for a in real:
        if a['op'] == 'create_project':
            sid = a['show_id']
            pdir = Path(a['path'])
            bible_p = data / 'shows' / sid / 'series_bible.json'
            bible = json.loads(bible_p.read_text(encoding='utf-8')) if bible_p.exists() else {}
            cfg = ProjectConfig(project_id=sid, show_id=sid,
                                title=bible.get('show_name') or sid.replace('_', ' ').title(),
                                idea=bible.get('concept') or bible.get('premise') or '',
                                mode='serialized_fiction', mode_source='user',
                                mode_rationale='migrated legacy show', original=False,
                                publishable=False)
            files = {
                'project.json': cfg.model_dump(),
                'legacy.json': {'legacy_namespace': True, 'migrated_at': ts,
                                'note': 'legacy episodes keep the legacy pipeline'},
                'format.json': _legacy_format(),
                'bible.json': {'logline': bible.get('concept', ''), 'tone': bible.get('tone', ''),
                               'cast': [{'name': c.get('name'), 'role': c.get('role', ''),
                                         'voice_description': c.get('voice_description', '')}
                                        for c in bible.get('main_cast', []) if c.get('name')]
                               or [{'name': 'Narrator'}]},
            }
            vc = voices / 'voice_config.json'
            if vc.exists():
                files['voices.json'] = json.loads(vc.read_text(encoding='utf-8'))
            for name, obj in files.items():
                atomic_write_json(pdir / name, obj)
                created.append(str(pdir / name))
        elif a['op'] == 'cast_ids':
            p = Path(a['path'])
            bible = json.loads(p.read_text(encoding='utf-8'))
            for i, c in enumerate(bible.get('main_cast', []), 1):
                if not str(c.get('character_id', '')).startswith('C'):
                    if c.get('character_id'):
                        c['legacy_character_id'] = c['character_id']
                    c['character_id'] = f'C{i:02d}'
            atomic_write_json(p, bible)
        elif a['op'] == 'index':
            p = Path(a['path'])
            existed = p.exists()
            atomic_write_json(p, {'slugs': a['slugs'], 'projects': a['projects']})
            if not existed:
                created.append(str(p))
        elif a['op'] == 'episode_show_id':
            p = Path(a['path'])
            ep = json.loads(p.read_text(encoding='utf-8'))
            ep['show_id'] = a['show_id']
            ep.setdefault('season_number', 1)
            p.write_text(json.dumps(ep, indent=2), encoding='utf-8')
        elif a['op'] == 'active_show':
            atomic_write_json(Path(a['path']), {'show_id': a['show_id']})
            created.append(a['path'])
    manifest = {'at': ts, 'backup': str(tar_p), 'modified': modified, 'created': created,
                'actions': acts}
    man_p = bdir / f'migrate-{ts}.manifest.json'
    man_p.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return {'status': 'migrated', 'manifest': str(man_p), 'actions': acts}


def rollback(manifest_path: str) -> Dict[str, Any]:
    man = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    removed = 0
    for p in man['created']:
        try:
            Path(p).unlink()
            removed += 1
        except FileNotFoundError:
            pass
    for d in {Path(p).parent for p in man['created']}:
        try:
            d.rmdir()
        except OSError:
            pass
    restored = 0
    with tarfile.open(man['backup'], 'r:gz') as tar:
        members = {m.name: m for m in tar.getmembers()}
        for p in man['modified']:
            key = Path(p).resolve().as_posix().lstrip('/').replace(':', '')
            if key in members:
                src = tar.extractfile(members[key])
                Path(p).write_bytes(src.read())
                restored += 1
    return {'removed': removed, 'restored': restored}
