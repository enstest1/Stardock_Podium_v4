"""Per-show sound settings and A/B "dial-in" sample packs.

Owns ``data/projects/<id>/sound/mix.json``:

    {"mix": "balanced", "pacing": "natural", "phone_style": "phone",
     "loudness_lufs": -16.0}

``mix`` is an ``audio_mix.MIX_PRESETS`` name (or a dict with ``preset`` plus
``bus_gain_db`` / ``duck_db`` overrides), ``pacing`` an
``audio_timeline.PACING_PRESETS`` name (or dict of gaps), ``phone_style`` the
``VOICE_FX`` used wherever a script or voice asks for ``phone``.

``make_samples(episode_id)`` re-renders excerpts of an already rendered
episode with each option (no LLM calls, no new TTS except voice auditions) so
a person can listen and pick.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULTS: Dict[str, Any] = {'mix': 'balanced', 'pacing': 'natural',
                            'phone_style': 'phone', 'loudness_lufs': -16.0}
PHONE_STYLES = ('phone_light', 'phone', 'phone_old', 'radio')


def _path(project_id: str) -> Path:
    from story_os.projects import project_dir
    return project_dir(project_id) / 'sound' / 'mix.json'


def load_settings(project_id: Optional[str]) -> Dict[str, Any]:
    out = dict(DEFAULTS)
    if project_id:
        p = _path(project_id)
        if p.exists():
            try:
                out.update(json.loads(p.read_text(encoding='utf-8')))
            except (OSError, json.JSONDecodeError):
                pass
    return out


def validate(settings: Dict[str, Any]) -> List[str]:
    from audio_mix import MIX_PRESETS
    from audio_timeline import PACING_PRESETS, VOICE_FX
    errs = []
    mix = settings.get('mix')
    name = mix.get('preset', 'balanced') if isinstance(mix, dict) else mix
    if name not in MIX_PRESETS:
        errs.append(f'unknown mix preset {name!r} (have {sorted(MIX_PRESETS)})')
    pace = settings.get('pacing')
    if isinstance(pace, str) and pace not in PACING_PRESETS:
        errs.append(f'unknown pacing {pace!r} (have {sorted(PACING_PRESETS)})')
    if settings.get('phone_style') not in VOICE_FX:
        errs.append(f"unknown phone_style {settings.get('phone_style')!r}")
    lufs = settings.get('loudness_lufs')
    if not isinstance(lufs, (int, float)) or not -24 <= lufs <= -12:
        errs.append('loudness_lufs must be between -24 and -12')
    return errs


def save_settings(project_id: str, **changes: Any) -> Dict[str, Any]:
    cur = load_settings(project_id)
    cur.update({k: v for k, v in changes.items() if v is not None})
    errs = validate(cur)
    if errs:
        raise ValueError('; '.join(errs))
    p = _path(project_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cur, indent=2), encoding='utf-8')
    return cur


def fx_map(settings: Dict[str, Any]) -> Dict[str, str]:
    style = settings.get('phone_style') or 'phone'
    return {} if style == 'phone' else {'phone': style}


def set_voice_speed(project_id: str, character_key: str, speed: float) -> Dict[str, Any]:
    """Store a Kokoro speaking-rate multiplier for one cast member."""
    from story_os.projects import project_dir
    if not 0.7 <= speed <= 1.3:
        raise ValueError('speed must be between 0.7 and 1.3')
    p = project_dir(project_id) / 'voices.json'
    cfg = json.loads(p.read_text(encoding='utf-8'))
    key = (cfg.get('aliases') or {}).get(character_key, character_key)
    if key not in cfg.get('characters', {}):
        raise KeyError(f'{character_key!r} is not in {project_id} voices '
                       f'({sorted(cfg.get("characters", {}))})')
    if abs(speed - 1.0) < 1e-6:
        cfg['characters'][key].pop('speed', None)
    else:
        cfg['characters'][key]['speed'] = round(float(speed), 3)
    p.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    return cfg['characters'][key]


def set_voice(project_id: str, character_key: str, voice_id: str) -> Dict[str, Any]:
    """Swap one cast member to another catalog voice (records usage)."""
    from story_os.projects import project_dir
    from voice_catalog import castable, load_catalog, record_usage, save_catalog
    cat = load_catalog()
    if voice_id not in {v['voice_id'] for v in castable(cat)}:
        raise KeyError(f'{voice_id!r} is not a castable catalog voice')
    p = project_dir(project_id) / 'voices.json'
    cfg = json.loads(p.read_text(encoding='utf-8'))
    key = (cfg.get('aliases') or {}).get(character_key, character_key)
    if key not in cfg.get('characters', {}):
        raise KeyError(f'{character_key!r} is not in {project_id} voices')
    entry = cfg['characters'][key]
    entry['kokoro_voice'] = cat['voices'][voice_id]['kokoro_voice']
    entry['voice_id'] = voice_id
    p.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    record_usage(cat, voice_id, project_id, key)
    save_catalog(cat)
    return entry


# ------------------------------------------------------------ samples ----

def _episode_inputs(episode_id: str):
    """Rebuild what ``build_timeline`` needs from a rendered episode."""
    import audio_assets
    import ffmpeg
    ep = Path('episodes') / episode_id
    audio = ep / 'audio'
    script = json.loads((ep / 'script.json').read_text(encoding='utf-8'))
    old = json.loads((audio / 'timeline.json').read_text(encoding='utf-8'))
    fx_by_line = {c.get('line_id'): c.get('fx') for c in old['clips']
                  if c['bus'] == 'dialogue' and c.get('line_id')}
    line_audio = {}
    for meta in (audio / 'lines').glob('*.json'):
        m = json.loads(meta.read_text(encoding='utf-8'))
        wav = meta.with_suffix('.wav')
        if wav.exists():
            line_audio[m['line_id']] = {'path': str(wav), 'duration': m['duration'],
                                        'fx': fx_by_line.get(m['line_id'])}
    idx = audio_assets.load_index()['assets']
    by_file = {Path(r['file']).as_posix(): r for r in idx.values()}
    by_cue: Dict[tuple, Dict[str, Any]] = {}
    for c in old['clips']:
        if c.get('cue'):
            kind = 'ambience' if c['bus'] == 'ambience' else ('sfx' if c['bus'] == 'sfx' else 'music')
            rec = by_file.get(Path(c['path']).as_posix()) or {'file': c['path'],
                                                              'duration': c['length']}
            by_cue[(kind, c['cue'])] = rec

    def resolve(kind, text, seconds):
        return by_cue.get((kind, text))

    def part(role):
        c = next((c for c in old['clips'] if c.get('role') == role), None)
        if not c:
            return None
        return {'path': c['path'],
                'duration': float(ffmpeg.probe(c['path'])['format']['duration'])}
    intro = {'narration': part('intro_narration'), 'music': part('intro_theme')}
    outro = {'narration': part('outro_narration'), 'music': part('outro_theme')}
    return script, line_audio, resolve, intro, outro


def _chapter(tl: Dict[str, Any], title: str) -> float:
    return next(c['start'] for c in tl['chapters'] if c['title'] == title)


def crop(tl: Dict[str, Any], start: float, end: float) -> Dict[str, Any]:
    clips = []
    for c in tl['clips']:
        if c['start'] < start - 1e-6 or c['start'] >= end:
            continue
        c = dict(c, start=c['start'] - start)
        if c['start'] + c['length'] > end - start:
            c['length'] = end - start - c['start']
            c['fade_out'] = max(c.get('fade_out', 0.01), 1.0)
        clips.append(c)
    return {'clips': clips, 'missing': [], 'chapters': [], 'duration': end - start}


def _render_excerpt(tl, out_mp3: Path, mix, lufs, title):
    import audio_mix
    tmp = Path(tempfile.mkdtemp(prefix='dialin_'))
    try:
        mixed = audio_mix.render(tl, tmp, settings=mix)
        res = audio_mix.master(mixed['mix'], str(out_mp3), target=lufs,
                               metadata={'title': title, 'comment': 'dial-in sample'})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return res


def make_samples(episode_id: str, out_dir: Optional[Path] = None, *,
                 project_id: Optional[str] = None, voices: bool = True,
                 voice_candidates: Optional[Dict[str, List[str]]] = None) -> Path:
    from audio_timeline import build_timeline
    script, line_audio, resolve, intro, outro = _episode_inputs(episode_id)
    out = Path(out_dir or Path('episodes') / episode_id / 'dialin')
    out.mkdir(parents=True, exist_ok=True)
    base = load_settings(project_id)
    rows: List[Dict[str, Any]] = []

    def tl_for(pacing=None, fxm=None):
        return build_timeline(script, line_audio, resolve, intro=intro, outro=outro,
                              pacing=pacing or base['pacing'],
                              fx_map=fxm if fxm is not None else fx_map(base))

    def add(name, group, setting, tl, a, b, mix=None, lufs=None, note=''):
        f = out / f'{name}.mp3'
        res = _render_excerpt(crop(tl, a, b), f, mix or base['mix'],
                              lufs or base['loudness_lufs'], name)
        rows.append({'file': f.name, 'group': group, 'setting': setting,
                     'seconds': round(b - a, 1), 'lufs': res['lufs_i'], 'note': note})

    tl = tl_for()
    s2, s3 = _chapter(tl, 'Scene 2'), _chapter(tl, 'Scene 3')
    mix_end = min(s3, s2 + 28)
    notes = {'balanced': 'current default', 'intimate': 'beds low, voices close',
             'cinematic': 'beds and effects up, lighter ducking',
             'dry': 'almost no bed, effects soft'}
    for i, preset in enumerate(('balanced', 'intimate', 'cinematic', 'dry'), 1):
        add(f'A{i}_mix_{preset}', 'A mix', preset, tl, 0.0, mix_end, mix=preset,
            note=notes[preset])
    for i, pace in enumerate(('tight', 'natural', 'relaxed'), 1):
        t = tl_for(pacing=pace)
        add(f'B{i}_pacing_{pace}', 'B pacing', pace, t, _chapter(t, 'Scene 1') - 0.8,
            _chapter(t, 'Scene 2') - 0.2)
    pnotes = {'phone_light': 'clear cell/landline', 'phone': 'current default',
              'phone_old': 'narrow, crunchy old line', 'radio': 'broadcast/radio set'}
    for i, style in enumerate(PHONE_STYLES, 1):
        t = tl_for(fxm={} if style == 'phone' else {'phone': style})
        add(f'C{i}_phone_{style}', 'C phone voice', style, t,
            _chapter(t, 'Scene 2') - 0.8, _chapter(t, 'Scene 3') - 0.2, note=pnotes[style])
    for i, lufs in enumerate((-19.0, -16.0, -14.0), 1):
        add(f'D{i}_loudness_{abs(int(lufs))}', 'D loudness', f'{lufs} LUFS', tl, 0.0,
            min(s2, 40.0), lufs=lufs,
            note={-19.0: 'quieter, more dynamic', -16.0: 'podcast standard (Apple)',
                  -14.0: 'louder (Spotify/YouTube)'}[lufs])
    if voices:
        rows += _voice_auditions(episode_id, script, out, voice_candidates or {})
    (out / 'index.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
    _write_readme(out, rows, base)
    return out


def _voice_auditions(episode_id, script, out, candidates):
    """Each lead's first long line in current voice at 3 speeds + alternatives."""
    import audio_mix
    from tts_engine import get_kokoro_engine
    from voice_catalog import load_catalog
    meta_dir = Path('episodes') / episode_id / 'audio' / 'lines'
    cat = load_catalog()['voices']
    by_speaker: Dict[str, Dict[str, Any]] = {}
    for scene in script['scenes']:
        for l in scene['lines']:
            if l.get('type') not in ('dialogue', 'narration'):
                continue
            m = meta_dir / f"{l.get('line_id')}.json"
            if not m.exists():
                continue
            meta = json.loads(m.read_text(encoding='utf-8'))
            sp = meta['speaker']
            words = len(l['content'].split())
            if 12 <= words <= 40 and words > by_speaker.get(sp, {}).get('words', 0):
                by_speaker[sp] = {'words': words, 'text': l['content'], 'voice': meta['voice']}
    rows = []
    eng = get_kokoro_engine()
    vdir = out / 'voices'
    vdir.mkdir(exist_ok=True)
    for sp, info in sorted(by_speaker.items()):
        cur = info['voice']
        cur_entry = next((v for v in cat.values() if v.get('kokoro_voice') == cur), {})
        gender = cur_entry.get('gender') or ('male' if '/am_' in cur or cur.startswith(('am_', 'bm_')) else 'female')
        alts = candidates.get(sp.lower())
        if alts is None:
            pool = [v for v in cat.values() if v.get('engine') == 'kokoro'
                    and v.get('auto_cast', True) and v.get('gender') == gender
                    and v.get('kokoro_voice') != cur]
            pool.sort(key=lambda v: (v.get('source') != 'designed', len(v.get('used_by') or [])))
            alts = [v['voice_id'] for v in pool[:4]]
        tries = [(f'{cur_entry.get("voice_id", cur)} @{s}', cur, s) for s in (0.92, 1.0, 1.08)]
        tries += [(vid, cat[vid]['kokoro_voice'], 1.0) for vid in alts if vid in cat]
        for j, (label, voice, speed) in enumerate(tries, 1):
            safe = label.replace(':', '-').replace('/', '-').replace(' @', '_x').replace('.', '')
            wav = vdir / f'{sp.lower()}_{j:02d}_{safe}.wav'
            mp3 = wav.with_suffix('.mp3')
            eng.synth(text=info['text'], speaker_wav=voice, language='en',
                      output_path=str(wav), speed=speed)
            audio_mix.master(str(wav), str(mp3), target=-16.0)
            wav.unlink(missing_ok=True)
            rows.append({'file': f'voices/{mp3.name}', 'group': f'E voice {sp}',
                         'setting': label, 'note': 'current voice' if voice == cur and speed == 1.0
                         else ('current voice, speed' if voice == cur else 'alternative')})
    return rows


def _write_readme(out: Path, rows, base):
    lines = ['# Dial-in samples', '',
             f"Current show settings: mix **{base['mix']}**, pacing **{base['pacing']}**, "
             f"phone **{base['phone_style']}**, loudness **{base['loudness_lufs']} LUFS**.",
             '', 'Pick one per group, then run e.g.:', '',
             '    python main.py sound-settings <project> --mix intimate --pacing tight '
             '--phone phone_old --loudness -16 --speed della=0.95', '']
    group = None
    for r in rows:
        if r['group'] != group:
            group = r['group']
            lines += ['', f'## {group}', '']
        lines.append(f"- `{r['file']}` — {r['setting']}" + (f" ({r['note']})" if r.get('note') else ''))
    (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
