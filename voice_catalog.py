"""Voice catalog, casting and voice design (AUDIO-006, voice part).

Owns ``voices/catalog.json`` (one record per usable or known voice) and
``voices/designed/*.pt`` (new Kokoro voices made by blending presets).

Sources catalogued:

- ``preset``    Kokoro v1 built-in voices (Apache-2.0, publishable, auto-cast)
- ``designed``  blends of presets created for a show (publishable, auto-cast)
- ``sample``    WAV/MP3 reference samples under ``voices/samples`` used by
                XTTS cloning: Coqui CPML is non-commercial and a cloned voice
                needs consent, so these are ``publishable: false`` and are
                never auto-cast (user decision 2026-11-20)
- ``legacy_elevenlabs``  entries of the old ``voices/registry.json``; listed
                for history, not usable by the Kokoro pipeline

``used_by`` records which project/character each voice plays, so a new show
is cast with voices that do not already belong to another show's lead.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Approximate, by-ear descriptors for Kokoro v1 presets (grade order follows
# the Kokoro voice card; descriptors are ours and only guide casting).
PRESETS: Dict[str, Dict[str, Any]] = {
    'af_heart':   {'traits': ['warm', 'clear', 'mid-pitch', 'friendly']},
    'af_bella':   {'traits': ['bright', 'expressive', 'youthful', 'energetic']},
    'af_nicole':  {'traits': ['soft', 'breathy', 'intimate', 'calm']},
    'af_sarah':   {'traits': ['mature', 'composed', 'measured']},
    'af_nova':    {'traits': ['crisp', 'confident', 'modern']},
    'af_sky':     {'traits': ['light', 'airy', 'young']},
    'af_river':   {'traits': ['relaxed', 'smooth', 'low-key']},
    'af_jessica': {'traits': ['casual', 'chatty', 'young adult']},
    'af_kore':    {'traits': ['steady', 'serious', 'low']},
    'af_aoede':   {'traits': ['gentle', 'melodic']},
    'af_alloy':   {'traits': ['neutral', 'even', 'plain']},
    'am_michael': {'traits': ['warm', 'baritone', 'trustworthy']},
    'am_fenrir':  {'traits': ['deep', 'gravelly', 'intense']},
    'am_puck':    {'traits': ['playful', 'quick', 'wry']},
    'am_adam':    {'traits': ['young', 'earnest', 'plain']},
    'am_liam':    {'traits': ['youthful', 'bright', 'casual']},
    'am_onyx':    {'traits': ['low', 'smooth', 'authoritative']},
    'am_echo':    {'traits': ['soft', 'resonant', 'calm']},
    'am_eric':    {'traits': ['brisk', 'businesslike']},
    'bf_emma':    {'traits': ['clear', 'precise', 'refined']},
    'bf_isabella': {'traits': ['elegant', 'warm', 'poised']},
    'bf_alice':   {'traits': ['crisp', 'young', 'proper']},
    'bf_lily':    {'traits': ['soft', 'sweet', 'young']},
    'bm_george':  {'traits': ['older', 'dignified', 'gravelly']},
    'bm_fable':   {'traits': ['storyteller', 'warm', 'expressive']},
    'bm_lewis':   {'traits': ['deep', 'measured', 'serious']},
    'bm_daniel':  {'traits': ['calm', 'gentle', 'even']},
}


def _voices_dir() -> Path:
    from config.paths import VOICES_DIR
    return Path(VOICES_DIR)


def catalog_path() -> Path:
    return _voices_dir() / 'catalog.json'


def designed_dir() -> Path:
    return _voices_dir() / 'designed'


def preset_gender(name: str) -> str:
    return 'male' if name[1:2] == 'm' else 'female'


def preset_accent(name: str) -> str:
    return 'british' if name[:1] == 'b' else 'american'


def _slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')[:40] or 'voice'


# ------------------------------------------------------------ storage ----

def load_catalog() -> Dict[str, Any]:
    p = catalog_path()
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return refresh_catalog(save=False)


def save_catalog(cat: Dict[str, Any]) -> None:
    p = catalog_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cat, f, indent=2, ensure_ascii=False)
    os.replace(tmp, p)


def refresh_catalog(save: bool = True) -> Dict[str, Any]:
    """(Re)build entries for presets, samples and legacy registry.

    Designed voices and every ``used_by`` record are kept.
    """
    old: Dict[str, Any] = {}
    p = catalog_path()
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            old = json.load(f).get('voices', {})
    voices: Dict[str, Any] = {k: v for k, v in old.items()
                              if v.get('source') == 'designed'}

    def keep_usage(vid: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        entry['used_by'] = (old.get(vid) or {}).get('used_by', entry.get('used_by', []))
        return entry

    for name, meta in PRESETS.items():
        vid = f'kokoro:{name}'
        voices[vid] = keep_usage(vid, {
            'voice_id': vid, 'source': 'preset', 'engine': 'kokoro',
            'kokoro_voice': name, 'gender': preset_gender(name),
            'accent': preset_accent(name), 'traits': meta['traits'],
            'licence': 'Apache-2.0 (Kokoro-82M)', 'publishable': True,
            'auto_cast': True, 'consent_record': None, 'used_by': []})

    samples_root = _voices_dir() / 'samples'
    if samples_root.exists():
        seen = set()
        for f in sorted(samples_root.rglob('*')):
            if f.suffix.lower() not in ('.wav', '.mp3'):
                continue
            stem_key = (f.parent.name, f.stem)
            if stem_key in seen:      # wav + mp3 of the same sample
                continue
            seen.add(stem_key)
            vid = f'sample:{_slug(f.parent.name)}/{_slug(f.stem)[:24]}'
            voices[vid] = keep_usage(vid, {
                'voice_id': vid, 'source': 'sample', 'engine': 'xtts',
                'speaker_wav': f.relative_to(_voices_dir().parent).as_posix(),
                'collection': f.parent.name, 'label': f.stem[:60],
                'licence': 'Coqui CPML (non-commercial)', 'publishable': False,
                'auto_cast': False, 'consent_record': None, 'used_by': []})

    reg = _voices_dir() / 'registry.json'
    if reg.exists():
        try:
            with open(reg, 'r', encoding='utf-8') as f:
                for rid, r in json.load(f).items():
                    vid = f'legacy:{rid}'
                    voices[vid] = keep_usage(vid, {
                        'voice_id': vid, 'source': 'legacy_elevenlabs',
                        'engine': 'elevenlabs', 'label': r.get('name'),
                        'elevenlabs_voice_id': r.get('voice_id'),
                        'description': r.get('description', ''),
                        'publishable': False, 'auto_cast': False,
                        'available': False, 'used_by': []})
        except (OSError, json.JSONDecodeError) as e:
            logger.warning('Legacy registry not read: %s', e)

    # Usage by the legacy show (global voice_config.json)
    vc = _voices_dir() / 'voice_config.json'
    if vc.exists():
        try:
            with open(vc, 'r', encoding='utf-8') as f:
                chars = json.load(f).get('characters', {})
            for key, entry in chars.items():
                kv = entry.get('kokoro_voice')
                vid = f'kokoro:{kv}' if kv else None
                if vid in voices:
                    _add_usage(voices[vid], 'legacy_global', key)
        except (OSError, json.JSONDecodeError):
            pass

    cat = {'schema_version': SCHEMA_VERSION, 'updated_at': time.time(),
           'voices': voices}
    if save:
        save_catalog(cat)
    return cat


def _add_usage(entry: Dict[str, Any], project_id: str, character: str) -> None:
    rec = {'project_id': project_id, 'character': character}
    if rec not in entry.setdefault('used_by', []):
        entry['used_by'].append(rec)


def record_usage(cat: Dict[str, Any], voice_id: str, project_id: str,
                 character: str) -> None:
    _add_usage(cat['voices'][voice_id], project_id, character)


def castable(cat: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [v for v in cat['voices'].values()
            if v.get('auto_cast') and v.get('publishable')]


# ------------------------------------------------------------- design ----

def normalise_recipe(recipe: Dict[str, float]) -> Dict[str, float]:
    clean = {k: float(w) for k, w in (recipe or {}).items()
             if k in PRESETS and float(w) > 0}
    total = sum(clean.values())
    if len(clean) < 2 or total <= 0:
        raise ValueError(f'recipe needs two or more known presets: {recipe!r}')
    return {k: round(w / total, 3) for k, w in clean.items()}


def design_voice(cat: Dict[str, Any], name: str, recipe: Dict[str, float], *,
                 traits: Optional[List[str]] = None, description: str = '',
                 project_id: Optional[str] = None) -> Dict[str, Any]:
    """Blend presets into a new Kokoro voice tensor and catalogue it."""
    import torch
    from tts_engine import get_kokoro_engine
    recipe = normalise_recipe(recipe)
    genders = {preset_gender(k) for k in recipe}
    pipeline = get_kokoro_engine()._pipeline
    blended = None
    for preset, weight in recipe.items():
        pack = pipeline.load_single_voice(preset) * weight
        blended = pack if blended is None else blended + pack
    base = _slug(name)
    vid, n = f'design:{base}', 2
    while vid in cat['voices']:
        vid, n = f'design:{base}_{n}', n + 1
    out = designed_dir() / f'{vid.split(":", 1)[1]}.pt'
    out.parent.mkdir(parents=True, exist_ok=True)
    torch.save(blended, out)
    main = max(recipe, key=recipe.get)
    entry = {
        'voice_id': vid, 'source': 'designed', 'engine': 'kokoro',
        'kokoro_voice': out.relative_to(_voices_dir().parent).as_posix(),
        'recipe': recipe,
        'gender': genders.pop() if len(genders) == 1 else 'neutral',
        'accent': preset_accent(main),
        'traits': traits or list(PRESETS[main]['traits']),
        'description': description, 'designed_for': project_id,
        'licence': 'Apache-2.0 (blend of Kokoro-82M presets)',
        'publishable': True, 'auto_cast': True, 'consent_record': None,
        'created_at': time.time(), 'used_by': []}
    cat['voices'][vid] = entry
    logger.info('Designed voice %s from %s', vid, recipe)
    return entry


def audition(voice_entry: Dict[str, Any], text: str, out_path: Path) -> Path:
    from tts_engine import get_kokoro_engine
    get_kokoro_engine().synth(text=text, speaker_wav=voice_entry['kokoro_voice'],
                              language='en', output_path=str(out_path))
    return out_path


# ------------------------------------------------------------ casting ----

def _fallback_pick(cat, wanted_gender, wanted_accent, taken, avoid_ids):
    pool = castable(cat)

    def score(v):
        s = 0
        s += 4 if v.get('gender') == wanted_gender else 0
        s += 2 if v.get('accent') == wanted_accent else 0
        s -= 3 if v['voice_id'] in avoid_ids else 0
        s -= len(v.get('used_by', []))
        return s
    for v in sorted(pool, key=score, reverse=True):
        if v['voice_id'] not in taken:
            return v
    return pool[0]


def cast_show(project_id: str, speakers: List[Dict[str, str]], *,
              use_llm: bool = True, max_designs: int = 3) -> Dict[str, str]:
    """Pick or design a catalog voice for every speaker.

    ``speakers``: ``[{key, name, gender, accent, voice_description, lead}]``
    (``key`` is the voice_config key). Returns ``{key: voice_id}`` and saves
    the catalog (designs + usage). Voices already used by another project's
    speakers are avoided where possible, so shows sound distinct.
    """
    cat = load_catalog()
    if not catalog_path().exists():
        save_catalog(cat)
    in_use_elsewhere = {v['voice_id'] for v in castable(cat)
                        if any(u['project_id'] != project_id
                               for u in v.get('used_by', []))}
    plan: Dict[str, Any] = {}
    if use_llm:
        try:
            plan = _llm_casting(cat, speakers, in_use_elsewhere, max_designs)
        except Exception as e:
            logger.warning('LLM casting failed (%s); using rule-based casting.', e)
            plan = {}
    result: Dict[str, str] = {}
    taken: set = set()
    designs = 0
    for sp in speakers:
        choice = plan.get(sp['key']) or {}
        vid = None
        if choice.get('design') and designs < max_designs:
            try:
                d = choice['design']
                recipe = normalise_recipe(d.get('recipe') or {})
                if {preset_gender(k) for k in recipe} == {sp['gender']}:
                    entry = design_voice(
                        cat, d.get('name') or f"{project_id} {sp['name']}",
                        recipe, traits=d.get('traits'),
                        description=sp.get('voice_description', ''),
                        project_id=project_id)
                    vid = entry['voice_id']
                    designs += 1
            except Exception as e:
                logger.warning('Design for %s rejected: %s', sp['name'], e)
        if vid is None and choice.get('voice_id') in cat['voices']:
            v = cat['voices'][choice['voice_id']]
            if (v.get('auto_cast') and v.get('publishable')
                    and v.get('gender') == sp['gender'] and v['voice_id'] not in taken):
                vid = v['voice_id']
        if vid is None:
            vid = _fallback_pick(cat, sp['gender'], sp.get('accent', 'american'),
                                 taken, in_use_elsewhere)['voice_id']
        taken.add(vid)
        record_usage(cat, vid, project_id, sp['key'])
        result[sp['key']] = vid
    save_catalog(cat)
    return result


def _llm_casting(cat, speakers, in_use_elsewhere, max_designs) -> Dict[str, Any]:
    from story_os import llm
    rows = []
    for v in castable(cat):
        tag = ' (used by another show)' if v['voice_id'] in in_use_elsewhere else ''
        rows.append(f"{v['voice_id']}: {v['gender']}, {v['accent']}, "
                    f"{', '.join(v.get('traits', []))}{tag}")
    people = '\n'.join(
        f"- key={s['key']} name={s['name']} gender={s['gender']} "
        f"accent={s.get('accent', '')} lead={bool(s.get('lead'))} "
        f"wants: {s.get('voice_description', '')}" for s in speakers)
    presets = ', '.join(PRESETS)
    system = ('You are a casting director for audio drama. You cast by ear: '
              'every speaker in one show must be easy to tell apart. Answer '
              'with JSON only.')
    user = (f'SPEAKERS:\n{people}\n\nCATALOG:\n' + '\n'.join(rows) +
            f'\n\nFor each speaker either pick a catalog voice_id of the same '
            f'gender, or design a new voice by blending 2-3 presets of the '
            f'same gender (presets: {presets}). Design at most {max_designs} '
            'voices, preferring designs for leads and for anyone whose best '
            'match is used by another show. No two speakers share a voice.\n'
            'Return JSON: {"cast": [{"key": "...", "voice_id": "kokoro:..."} '
            'or {"key": "...", "design": {"name": "short evocative name", '
            '"recipe": {"af_x": 0.6, "af_y": 0.4}, "traits": ["..."]}}]}')
    raw = llm.complete('planner', system, user, json=True, max_tokens=1200,
                       temperature=0.4)
    from story_os.projects import _json_from
    data = _json_from(raw)
    return {c['key']: c for c in data.get('cast', []) if c.get('key')}
