"""Publish assets (PUB-001): metadata, VTT transcript, chapters, description, cover.

Written to ``episodes/<id>/publish/``. Times come from the resolved audio
timeline (``audio/timeline.json``), so transcript and chapters match the mix.
"""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Any, Dict, List


def _vtt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def build_transcript(script: Dict[str, Any], timeline: Dict[str, Any]) -> Dict[str, Any]:
    lines = {l.get('line_id'): l for sc in script.get('scenes') or [] for l in sc.get('lines') or []}
    cues = []
    for c in timeline.get('clips') or []:
        if c['bus'] != 'dialogue' or not c.get('line_id') or c['line_id'] not in lines:
            continue
        l = lines[c['line_id']]
        who = (l.get('character') or ('Narrator' if l.get('type') == 'narration' else '')).title()
        cues.append({'start': round(c['start'], 3), 'end': round(c['start'] + c['length'], 3),
                     'speaker': who, 'text': l.get('content', '')})
    cues.sort(key=lambda x: x['start'])
    vtt = ['WEBVTT', '']
    for i, q in enumerate(cues, 1):
        vtt += [str(i), f"{_vtt_time(q['start'])} --> {_vtt_time(q['end'])}",
                f"<v {q['speaker']}>{q['text']}", '']
    return {'vtt': '\n'.join(vtt), 'json': {'version': '1.0.0', 'segments': cues}}


def _spoiler_terms(open_promises: List[Dict[str, Any]]) -> set:
    return {w for p in open_promises for w in re.findall(r'[a-z]{5,}', p.get('statement', '').lower())}


def build_chapters(episode: Dict[str, Any], timeline: Dict[str, Any],
                   open_promises: List[Dict[str, Any]] = (), claims_mode: bool = False) -> Dict[str, Any]:
    spoil = set() if claims_mode else _spoiler_terms(open_promises)
    scenes = episode.get('scenes') or []
    out = []
    scene_i = 0
    for ch in timeline.get('chapters') or []:
        title = ch['title']
        if title.startswith('Scene') and scene_i < len(scenes):
            sc = scenes[scene_i]
            scene_i += 1
            card = sc.get('card') or {}
            seg = sc.get('segment') or {}
            cand = seg.get('purpose') if claims_mode else (card.get('setting') or '').split(',')[0]
            if cand and not (set(re.findall(r'[a-z]{5,}', cand.lower())) & spoil):
                title = cand.strip()[:60]
        out.append({'startTime': round(ch['start'], 3), 'title': title})
    return {'version': '1.2.0', 'chapters': out}


def build_description(episode: Dict[str, Any], store=None, disclosure: str = '',
                      open_promises: List[Dict[str, Any]] = ()) -> str:
    spoil = _spoiler_terms(open_promises)
    parts = [episode.get('theme') or '']
    if store is not None:
        evs = [e for e in store.query('events', include_draft_episode=episode['episode_id'])
               if e['episode_id'] == episode['episode_id']]
        half = evs[: max(1, len(evs) // 2)]
        safe = [e['summary'] for e in half
                if not (set(re.findall(r'[a-z]{5,}', e['summary'].lower())) & spoil)][:2]
        if safe:
            parts.append(' '.join(safe))
    if disclosure:
        parts.append(disclosure)
    return '\n\n'.join(p for p in parts if p)


def make_cover(path: Path, title: str, subtitle: str = '', size: int = 3000) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (size, size), (18, 22, 30))
    d = ImageDraw.Draw(img)
    for i in range(0, size, 6):                      # vertical gradient
        shade = int(30 + 60 * i / size)
        d.line([(0, i), (size, i)], fill=(shade // 2, shade // 3 + 10, shade))
    try:
        font = ImageFont.truetype('arialbd.ttf', size // 11)
        small = ImageFont.truetype('arial.ttf', size // 28)
    except OSError:
        font = small = ImageFont.load_default()
    y = size // 3
    for line in textwrap.wrap(title, 14)[:4]:
        w = d.textlength(line, font=font)
        d.text(((size - w) / 2, y), line, font=font, fill=(240, 226, 200))
        y += size // 9
    if subtitle:
        w = d.textlength(subtitle, font=small)
        d.text(((size - w) / 2, size - size // 6), subtitle, font=small, fill=(190, 190, 200))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, 'JPEG', quality=88)
    return path


def validate_cover(path: Path, min_px: int = 1400, max_px: int = 3000,
                   max_bytes: int = 512_000 * 2) -> List[str]:
    from PIL import Image
    issues = []
    with Image.open(path) as im:
        w, h = im.size
        if w != h:
            issues.append('cover is not square')
        if not min_px <= w <= max_px:
            issues.append(f'cover is {w}px; needs {min_px}-{max_px}')
    if path.stat().st_size > max_bytes:
        issues.append(f'cover is {path.stat().st_size} bytes (> {max_bytes})')
    return issues


def build_publish_assets(episode_id: str) -> Dict[str, Any]:
    from config.paths import EPISODES_DIR
    from story_structure import get_episode
    from story_os import projects
    from story_os.canon_store import CanonStore
    ep = get_episode(episode_id)
    pid = ep['project_id']
    project = projects.load_project(pid)
    fmt = projects.load_format(pid)
    edir = Path(EPISODES_DIR) / episode_id
    out = edir / 'publish'
    out.mkdir(parents=True, exist_ok=True)
    timeline = json.loads((edir / 'audio' / 'timeline.json').read_text(encoding='utf-8'))
    store = CanonStore.for_episode(ep)
    open_p = store.open_promises(horizons=('episode', 'season', 'series'),
                                 include_draft_episode=episode_id) if store else []
    claims_mode = bool(project.capability('claims'))
    tr = build_transcript(ep.get('script') or {}, timeline)
    (out / 'transcript.vtt').write_text(tr['vtt'], encoding='utf-8')
    (out / 'transcript.json').write_text(json.dumps(tr['json'], indent=1), encoding='utf-8')
    chapters = build_chapters(ep, timeline, open_p, claims_mode)
    (out / 'chapters.json').write_text(json.dumps(chapters, indent=1), encoding='utf-8')
    disclosure = 'Produced with AI-generated writing and voices by Stardock Podium.'
    desc = build_description(ep, store, disclosure, open_p)
    sources = []
    if claims_mode:
        from story_os.claims import ClaimStore
        from story_os.references import list_sources
        titles = {s.source_id: s for s in list_sources(pid, enabled_only=False)}
        used = {r for sc in (ep.get('script') or {}).get('scenes', [])
                for l in sc.get('lines') or [] for r in l.get('claim_refs') or []}
        for cid in sorted(used):
            c = ClaimStore(pid).all().get(cid)
            for ci in (c.citations if c else []):
                s = titles.get(ci.source_id)
                sources.append({'claim': cid, 'title': s.title if s else ci.source_id,
                                'author': s.author if s else '', 'locator': ci.locator})
        if sources:
            desc += '\n\nSources:\n' + '\n'.join(f"- {s['title']} ({s['locator']})" for s in sources)
    cover = projects.project_dir(pid) / 'cover.jpg'
    if not cover.exists():
        make_cover(cover, project.title, fmt.tagline or project.genre)
    audio_file = edir / 'audio' / 'full_episode.mp3'
    meta = {'project_id': pid, 'mode': project.mode, 'guid': episode_id,
            'title': ep.get('title'), 'show': project.title, 'description': desc,
            'episode': ep.get('episode_number'), 'season': ep.get('season_number'),
            'duration': timeline.get('duration'), 'audio_file': str(audio_file),
            'length': audio_file.stat().st_size if audio_file.exists() else 0,
            'cover': str(cover), 'cover_issues': validate_cover(cover),
            'sources': sources, 'attributions': [fmt.theme_rights.get('attribution')]
            if (fmt.theme_rights or {}).get('attribution') else []}
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return meta
