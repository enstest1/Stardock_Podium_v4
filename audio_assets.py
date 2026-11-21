"""Sound asset library, cue resolution and SFX generation (AUDIO-005, AUDIO-007).

Owns ``assets/library/`` : ``<sha>.<ext>`` audio files plus ``index.json``
(one record per asset: kind, tags, description, duration, source, rights).

Resolution order for a cue (doc 08 §9, simplified):
  1. exact slug / id in the library
  2. best token-overlap match of the description among assets of the same
     kind, above a threshold
  3. generation (ElevenLabs sound effects) - cached into the library
  4. reported missing (once per (kind, key))

Legacy folders (``assets/sound_effects``, ``assets/ambience``) are ingested
with ``source: legacy`` and ``license: unknown``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KINDS = ('sfx', 'ambience', 'music')
MATCH_THRESHOLD = 0.5
_STOP = set('a an the of and or to in on at with from by as is are be its it '
            'into over under for this that these those very softly slowly '
            'quietly loud loudly sound sounds noise faint distant gentle low '
            'high sudden suddenly occasional background soft'.split())
ELEVEN_SFX_URL = 'https://api.elevenlabs.io/v1/sound-generation'


def library_dir() -> Path:
    return Path(os.environ.get('STARDOCK_ASSET_LIBRARY', 'assets/library'))


def _index_path() -> Path:
    return library_dir() / 'index.json'


def tokens(text: str) -> List[str]:
    words = re.findall(r"[a-z]+", (text or '').lower())
    out = []
    for w in words:
        if w in _STOP or len(w) < 3:
            continue
        for suf in ('ing', 'ed', 's'):                # crude stemming
            if w.endswith('ss'):
                break
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)]
                break
        out.append(w)
    return out


def slug(text: str) -> str:
    return '_'.join(tokens(text))[:60] or 'sound'


def load_index() -> Dict[str, Any]:
    p = _index_path()
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'schema_version': 1, 'assets': {}}


def save_index(idx: Dict[str, Any]) -> None:
    p = _index_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(idx, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=nw=1:nk=1', str(path)],
            capture_output=True, text=True, check=False).stdout.strip()
        return float(out or 0)
    except Exception:
        return 0.0


def ingest(path: Path, kind: str, description: str, *, source: str,
           rights: Dict[str, Any], idx: Optional[Dict[str, Any]] = None,
           extra_tags: Optional[List[str]] = None) -> Dict[str, Any]:
    """Copy a file into the library (dedup by content hash) and index it."""
    if kind not in KINDS:
        raise ValueError(f'unknown kind {kind!r}')
    own = idx is None
    idx = idx if idx is not None else load_index()
    sha = _sha(path)
    if sha in idx['assets']:
        return idx['assets'][sha]
    dest = library_dir() / f'{sha[:16]}{path.suffix.lower()}'
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(path, dest)
    rec = {'sha': sha, 'file': dest.as_posix(), 'kind': kind,
           'slug': slug(description), 'description': description,
           'tags': sorted(set(tokens(description)) | set(extra_tags or [])),
           'duration': round(probe_duration(dest), 3), 'source': source,
           'rights': rights, 'ingested_at': time.time()}
    idx['assets'][sha] = rec
    if own:
        save_index(idx)
    return rec


def ingest_legacy(base: Path = Path('assets')) -> int:
    idx = load_index()
    n = 0
    for folder, kind in (('sound_effects', 'sfx'), ('ambience', 'ambience')):
        d = base / folder
        if not d.exists():
            continue
        for f in sorted(d.glob('*')):
            if f.suffix.lower() not in ('.mp3', '.wav', '.ogg', '.flac'):
                continue
            before = len(idx['assets'])
            ingest(f, kind, f.stem.replace('_', ' '), source='legacy',
                   rights={'license': 'unknown', 'commercial_ok': 'unknown'},
                   idx=idx)
            n += len(idx['assets']) - before
    save_index(idx)
    return n


def match(kind: str, text: str, idx: Optional[Dict[str, Any]] = None,
          threshold: float = MATCH_THRESHOLD) -> Optional[Dict[str, Any]]:
    """Best library asset of ``kind`` for ``text`` (token overlap), or None."""
    idx = idx or load_index()
    want = set(tokens(text))
    if not want:
        return None
    best, best_score = None, 0.0
    for rec in idx['assets'].values():
        if rec['kind'] != kind:
            continue
        if rec['slug'] == slug(text):
            return rec
        have = set(rec['tags'])
        if not have:
            continue
        score = len(want & have) / (len(want) * len(have)) ** 0.5   # cosine
        if score > best_score:
            best, best_score = rec, score
    return best if best_score >= threshold else None


# ---------------------------------------------------------- generation ----

class SfxUnavailable(RuntimeError):
    pass


def generate_eleven(text: str, seconds: float, out: Path,
                    opener=urllib.request.urlopen) -> Path:
    key = os.environ.get('ELEVENLABS_API_KEY', '').strip()
    if not key:
        raise SfxUnavailable('ELEVENLABS_API_KEY not set')
    body = json.dumps({'text': text, 'duration_seconds': max(0.5, min(22.0, seconds)),
                       'prompt_influence': 0.5}).encode('utf-8')
    req = urllib.request.Request(ELEVEN_SFX_URL + '?output_format=mp3_44100_128',
                                 data=body, method='POST', headers={
                                     'xi-api-key': key,
                                     'Content-Type': 'application/json'})
    try:
        with opener(req, timeout=180) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        raise SfxUnavailable(f'HTTP {e.code}: {e.read()[:300]!r}') from e
    except urllib.error.URLError as e:
        raise SfxUnavailable(str(e)) from e
    if len(data) < 1000:
        raise SfxUnavailable(f'only {len(data)} bytes returned')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return out


_PLAN_CACHE: Dict[str, str] = {}


def _eleven_tier() -> str:
    if 'tier' not in _PLAN_CACHE:
        try:
            from story_os.music import eleven_plan
            _PLAN_CACHE['tier'] = str(eleven_plan().get('tier') or 'unknown')
        except Exception:
            _PLAN_CACHE['tier'] = 'unknown'
    return _PLAN_CACHE['tier']


def resolve(kind: str, text: str, *, seconds: float = 3.0,
            generate: bool = True, idx: Optional[Dict[str, Any]] = None,
            generator=None) -> Optional[Dict[str, Any]]:
    """Library match, else generate + cache, else None."""
    own = idx is None
    idx = idx if idx is not None else load_index()
    rec = match(kind, text, idx)
    if rec or not generate or kind == 'music':
        return rec
    gen = generator or generate_eleven
    prompt = text if kind == 'sfx' else f'{text}, continuous ambient background, seamless loop'
    tmp = library_dir() / 'tmp' / f'{slug(text)}_{int(time.time() * 1000)}.mp3'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        gen(prompt, seconds, tmp)
    except Exception as e:
        logger.warning('Could not generate %s %r: %s', kind, text, e)
        return None
    tier = _eleven_tier() if generator is None else 'test'
    rights = {'provider': 'ElevenLabs sound effects', 'plan_tier': tier,
              'commercial_ok': 'no' if tier in ('free', 'unknown') else 'yes',
              'attribution': 'elevenlabs.io' if tier in ('free', 'unknown') else ''}
    rec = ingest(tmp, kind, text, source='generated', rights=rights, idx=idx)
    try:
        tmp.unlink()
    except OSError:
        pass
    if own:
        save_index(idx)
    return rec


def rights_report(idx: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    idx = idx or load_index()
    out: Dict[str, List[str]] = {'unknown': [], 'non_commercial': []}
    for rec in idx['assets'].values():
        ok = (rec.get('rights') or {}).get('commercial_ok', 'unknown')
        if ok == 'unknown':
            out['unknown'].append(rec['description'])
        elif ok == 'no':
            out['non_commercial'].append(rec['description'])
    return out
