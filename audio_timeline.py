"""Cue syntax and episode timeline (AUDIO-002).

Owns: ``parse_cue`` for sound lines, ``CUE_GUIDE`` (writer prompt text) and
``build_timeline`` which turns a script + rendered line audio into a list of
clips on four buses (dialogue, sfx, ambience, music) with start times in
seconds. ``audio_mix.render`` plays the timeline sample-accurately.

Cue grammar (tolerant of case and spacing)::

    (SFX: a kettle starts to whistle)
    (SFX: door slams | wait)            wait = dialogue resumes after it
    (AMB: steady rain on a tin roof)    ambience bed for the rest of the scene
    (MUS: tense low strings | dur: 8)   music cue under the scene

A legacy parenthetical without a track prefix is an SFX placed 150 ms after
the previous line.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

CUE_GUIDE = (
    'Sound cues go on their own line in parentheses with a track prefix:\n'
    '  (AMB: steady rain on a tin roof)  - the background bed of the scene, '
    'one per scene, first line\n'
    '  (SFX: a kettle starts to whistle) - a specific sound at that moment; '
    'add | wait if the characters react to it\n'
    '  (MUS: low uneasy piano | dur: 8)  - rare, only for a big moment\n'
    'Describe what is heard in plain words (4-10 words).\n'
    'Never put spoken words inside a cue: anything a person says, even a '
    'distorted or ghostly voice, is a NAME: line.')

# Delivery effects applied to a voice (AUDIO-003 extension): name -> ffmpeg filter.
VOICE_FX = {
    'phone': 'highpass=f=320,highpass=f=320,lowpass=f=3300,lowpass=f=3300,acompressor=threshold=-22dB:ratio=3:attack=5:release=60,volume=1.6',
    'hollow': 'aecho=0.8:0.75:70|140:0.35|0.2,lowpass=f=5000',
    'radio': 'highpass=f=180,lowpass=f=5200,acompressor=threshold=-20dB:ratio=4,volume=1.3',
}
_SPEECH_CUE = re.compile(r"^(?P<who>[^:]*?\bvoice\b[^:]*|[^:]*?\b(?:says|whispers|calls|"
                         r"sings)\b[^:]*):\s*[\"\u201c]?(?P<words>[^\"\u201d]{3,}?)[\"\u201d]?\s*$",
                         re.I)


def speech_in_cue(text: str):
    """``(SFX: Della's voice, hollowed: I know...)`` -> (who_hint, words, fx)."""
    cue = parse_cue(text)
    if not cue or cue['track'] != 'sfx':
        return None
    m = _SPEECH_CUE.match(cue['sound'])
    if not m:
        return None
    who = m.group('who')
    fx = next((k for k in VOICE_FX if k in who.lower()), None)
    if fx is None and re.search(r'hollow|echo|ghost|distant|strange', who, re.I):
        fx = 'hollow'
    name = re.match(r"\s*([A-Z][a-z]+)'s\b", who)
    return (name.group(1) if name else None), m.group('words').strip(), fx

_CUE = re.compile(r'^\(?\s*(SFX|AMB|AMBIENCE|MUS|MUSIC)\s*:\s*(?P<body>.+?)\)?\s*$',
                  re.I | re.S)
_TRACK = {'sfx': 'sfx', 'amb': 'ambience', 'ambience': 'ambience',
          'mus': 'music', 'music': 'music'}

LINE_GAP = 0.30          # pause between spoken lines (s)
SAME_SPEAKER_GAP = 0.15
NARRATION_GAP = 0.45
SFX_LEAD = 0.15          # legacy cue offset after previous line
SCENE_GAP = 1.4
AMB_PREROLL = 0.8
AMB_TAIL = 1.2


def parse_cue(text: str) -> Optional[Dict[str, Any]]:
    """Parse a sound line into ``{track, sound, options}`` (None if empty)."""
    raw = (text or '').strip()
    if not raw:
        return None
    if re.match(r'^\(?\s*(SFX|AMB|AMBIENCE|MUS|MUSIC)\s*:\s*\)?\s*$', raw, re.I):
        return None
    m = _CUE.match(raw)
    if m:
        track = _TRACK[m.group(1).lower()]
        body = m.group('body')
    else:
        track, body = 'sfx', raw.strip('()')
    parts = [p.strip() for p in body.split('|')]
    cue: Dict[str, Any] = {'track': track, 'sound': parts[0].strip(' "\''),
                           'options': {}, 'legacy': m is None}
    for p in parts[1:]:
        if not p:
            continue
        if ':' in p:
            k, v = p.split(':', 1)
            cue['options'][k.strip().lower()] = v.strip()
        else:
            cue['options'][p.lower()] = True
    if not cue['sound']:
        return None
    return cue


def _f(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_timeline(script: Dict[str, Any], line_audio: Dict[str, Dict[str, Any]],
                   resolve: Callable[[str, str, float], Optional[Dict[str, Any]]],
                   *, intro: Optional[Dict[str, Any]] = None,
                   outro: Optional[Dict[str, Any]] = None,
                   scene_fallback_ambience: Optional[Callable[[Dict], str]] = None,
                   ) -> Dict[str, Any]:
    """Place every clip. ``line_audio[line_id] = {path, duration}``.

    ``resolve(kind, text, seconds) -> asset record with 'file'/'duration'``
    or None. ``intro``/``outro``: ``{narration: {path, duration},
    music: {path, duration}|None}``.
    Returns ``{clips, missing, chapters, duration}``.
    """
    clips: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    chapters: List[Dict[str, Any]] = []
    t = 0.0

    if intro and intro.get('narration'):
        music = intro.get('music')
        narr = intro['narration']
        lead = 1.2 if music else 0.0
        if music:
            mlen = min(music['duration'], lead + narr['duration'] + 4.0)
            clips.append({'bus': 'music', 'path': music['path'], 'start': 0.0,
                          'length': mlen, 'gain_db': -4.0, 'fade_in': 0.3,
                          'fade_out': 2.5, 'duck': True, 'role': 'intro_theme'})
        clips.append({'bus': 'dialogue', 'path': narr['path'], 'start': lead,
                      'length': narr['duration'], 'role': 'intro_narration'})
        t = lead + narr['duration'] + (2.2 if music else 0.8)
        chapters.append({'title': 'Intro', 'start': 0.0})

    for s_idx, scene in enumerate(script.get('scenes') or []):
        scene_start = t
        chapters.append({'title': f"Scene {scene.get('scene_number', s_idx + 1)}",
                         'start': round(scene_start, 3)})
        amb_text = None
        prev_end = t
        prev_speaker = None
        pending_amb: List[Dict[str, Any]] = []
        for line in scene.get('lines') or []:
            kind = line.get('type')
            lid = line.get('line_id')
            if kind in ('dialogue', 'narration'):
                la = line_audio.get(lid)
                if not la:
                    continue
                speaker = line.get('character') or line.get('speaker') or 'NARRATOR'
                if t > scene_start:
                    gap = (NARRATION_GAP if kind == 'narration' else
                           SAME_SPEAKER_GAP if speaker == prev_speaker else LINE_GAP)
                    t = max(t, prev_end + gap)
                clips.append({'bus': 'dialogue', 'path': la['path'], 'start': t,
                              'length': la['duration'], 'line_id': lid,
                              'role': kind, 'fx': line.get('fx') or la.get('fx')})
                prev_end = t + la['duration']
                t = prev_end
                prev_speaker = speaker
            elif kind == 'sound_effect':
                cue = parse_cue(line.get('content', ''))
                if not cue:
                    continue
                if cue['track'] == 'ambience':
                    if amb_text is None:
                        amb_text = cue['sound']
                    continue
                dur = _f(cue['options'].get('dur'), 2.5 if cue['track'] == 'sfx' else 8.0)
                rec = resolve(cue['track'], cue['sound'], dur)
                if not rec:
                    missing.append({'kind': cue['track'], 'text': cue['sound'],
                                    'line_id': lid})
                    continue
                start = (prev_end + SFX_LEAD) if t > scene_start else t
                length = min(rec['duration'] or dur, max(dur, 0.5) + 1.0)
                clip = {'bus': 'sfx' if cue['track'] == 'sfx' else 'music',
                        'path': rec['file'], 'start': start, 'length': length,
                        'gain_db': -6.0 if cue['track'] == 'sfx' else -10.0,
                        'fade_in': 0.02 if cue['track'] == 'sfx' else 0.8,
                        'fade_out': 0.25 if cue['track'] == 'sfx' else 1.5,
                        'duck': cue['track'] == 'music', 'line_id': lid,
                        'role': 'cue', 'cue': cue['sound']}
                clips.append(clip)
                if 'wait' in cue['options'] or length < 1.6:
                    prev_end = max(prev_end, start + length * (1.0 if 'wait' in cue['options'] else 0.6))
                    t = max(t, prev_end)
        scene_end = max(t, prev_end)
        if amb_text is None and scene_fallback_ambience:
            amb_text = scene_fallback_ambience(scene)
        if amb_text:
            length = (scene_end - scene_start) + AMB_PREROLL + AMB_TAIL
            rec = resolve("ambience", amb_text, 10.0)
            if rec:
                clips.append({'bus': 'ambience', 'path': rec['file'],
                              'start': max(0.0, scene_start - AMB_PREROLL),
                              'length': length, 'loop': True, 'gain_db': -14.0,
                              'fade_in': 1.0, 'fade_out': 1.5, 'duck': True,
                              'role': 'ambience', 'cue': amb_text})
            else:
                missing.append({'kind': 'ambience', 'text': amb_text,
                                'scene': scene.get('scene_number')})
        t = scene_end + SCENE_GAP

    if outro and outro.get('narration'):
        narr = outro['narration']
        music = outro.get('music')
        chapters.append({'title': 'Credits', 'start': round(t, 3)})
        if music:
            mlen = max(music['duration'], narr['duration'] + 3.0)
            clips.append({'bus': 'music', 'path': music['path'], 'start': t,
                          'length': min(mlen, music['duration'] or mlen),
                          'gain_db': -5.0, 'fade_in': 0.8, 'fade_out': 2.5,
                          'duck': True, 'role': 'outro_theme'})
        clips.append({'bus': 'dialogue', 'path': narr['path'], 'start': t + 0.8,
                      'length': narr['duration'], 'role': 'outro_narration'})
        end = t + 0.8 + narr['duration']
        if music:
            end = max(end, t + min(mlen, music['duration'] or mlen))
        t = end + 0.5
    clips.sort(key=lambda c: (round(c['start'], 6), c['bus'], c.get('line_id') or ''))
    return {'clips': clips, 'missing': missing, 'chapters': chapters,
            'duration': round(t, 3)}
