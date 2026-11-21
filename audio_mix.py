"""Multitrack timeline mixer and mastering (AUDIO-003, AUDIO-004).

Owns: rendering a ``audio_timeline`` timeline into stems and a 48 kHz stereo
mix (sample-accurate placement, per-line dialogue levelling, sidechain
ducking of music/ambience under speech, crossfaded loops, peak limiter), and
mastering that mix with two-pass ffmpeg ``loudnorm`` to -16 LUFS / -1 dBTP in
a single lossy encode with tags. No GPL DSP (no pedalboard).
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

SR = 48000
DIALOGUE_RMS_DB = -20.0
DUCK_DB = {'music': -11.0, 'ambience': -7.0}
BUS_GAIN_DB = {'dialogue': 0.0, 'sfx': -2.0, 'ambience': -3.0, 'music': -3.0}
LIMIT_DB = -2.0

_cache: Dict[str, np.ndarray] = {}


def db(x: float) -> float:
    return 10 ** (x / 20.0)


def load(path: str, fx: Optional[str] = None) -> np.ndarray:
    """Decode any audio file to float32 (N, 2) at 48 kHz via ffmpeg.

    ``fx`` names a delivery effect from ``audio_timeline.VOICE_FX``.
    """
    key = str(Path(path).resolve()) + f'|{fx or ""}'
    if key in _cache:
        return _cache[key]
    from audio_timeline import VOICE_FX
    af = ['-af', VOICE_FX[fx]] if fx in VOICE_FX else []
    proc = subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path), *af, '-f', 'f32le',
         '-acodec', 'pcm_f32le', '-ac', '2', '-ar', str(SR), '-'],
        capture_output=True, check=True)
    arr = np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2).copy()
    _cache[key] = arr
    return arr


def fade(x: np.ndarray, fin: float, fout: float) -> np.ndarray:
    n = len(x)
    a, b = min(n, int(fin * SR)), min(n, int(fout * SR))
    if a > 1:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)[:, None]
    if b > 1:
        x[n - b:] *= np.linspace(1, 0, b, dtype=np.float32)[:, None]
    return x


def loop_to_length(x: np.ndarray, n: int, xfade: float = 0.75) -> np.ndarray:
    if len(x) >= n:
        return x[:n].copy()
    xf = min(int(xfade * SR), len(x) // 3)
    out = np.zeros((n, 2), dtype=np.float32)
    out[:len(x)] = x
    pos = len(x)
    ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None] if xf > 1 else None
    while pos < n:
        start = pos - (xf if ramp is not None else 0)
        seg = x.copy()
        if ramp is not None:                 # equal-gain crossfade at the seam
            out[start:pos] *= (1 - ramp)
            seg[:xf] *= ramp
        end = min(n, start + len(seg))
        out[start:end] += seg[: end - start]
        pos = start + len(seg)
    return out


def rms_db(x: np.ndarray) -> float:
    v = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    return 20 * np.log10(v) if v > 1e-9 else -120.0


def presence_envelope(dialogue: np.ndarray, attack: float = 0.05,
                      release: float = 0.45, thresh_db: float = -42.0) -> np.ndarray:
    """0..1 speech presence from the dialogue bus (vectorised, hop 10 ms)."""
    hop = SR // 100
    mono = np.abs(dialogue).max(axis=1)
    n_hops = int(np.ceil(len(mono) / hop))
    padded = np.pad(mono, (0, n_hops * hop - len(mono)))
    frames = padded.reshape(n_hops, hop).max(axis=1)
    gate = (frames > db(thresh_db)).astype(np.float32)
    env = np.zeros_like(gate)
    a = 1 - np.exp(-1 / (attack * 100))
    r = 1 - np.exp(-1 / (release * 100))
    level = 0.0
    for i, g in enumerate(gate):          # n_hops is small (100/s)
        level += (a if g > level else r) * (g - level)
        env[i] = level
    return np.repeat(env, hop)[: len(mono)]


def limit(x: np.ndarray, ceiling_db: float = LIMIT_DB) -> np.ndarray:
    """Smoothed gain-reduction peak limiter (lookahead 5 ms)."""
    ceiling = db(ceiling_db)
    peak = np.abs(x).max(axis=1)
    la = int(0.005 * SR)
    # running max over the lookahead window
    padded = np.pad(peak, (0, la))
    win = np.lib.stride_tricks.sliding_window_view(padded, la + 1).max(axis=1)[: len(peak)]
    gain = np.minimum(1.0, ceiling / np.maximum(win, 1e-9)).astype(np.float32)
    hop = SR // 200
    g = gain[::hop]
    for i in range(1, len(g)):            # release smoothing
        g[i] = min(g[i], g[i - 1] + 0.02)
    gain = np.repeat(g, hop)[: len(peak)]
    return x * gain[:, None]


def render(timeline: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    """Render stems + mix.wav. Returns paths and stats."""
    import soundfile as sf
    total = int((timeline['duration'] + 0.5) * SR)
    buses = {b: np.zeros((total, 2), dtype=np.float32)
             for b in ('dialogue', 'sfx', 'ambience', 'music')}
    for clip in timeline['clips']:
        try:
            src = load(clip['path'], clip.get('fx'))
        except Exception as e:
            logger.warning('Skipping unreadable clip %s: %s', clip['path'], e)
            continue
        n = max(1, int(clip.get('length', len(src) / SR) * SR))
        seg = loop_to_length(src, n) if clip.get('loop') else src[:n].copy()
        if clip['bus'] == 'dialogue':
            level = rms_db(seg[np.abs(seg).max(axis=1) > db(-45)]) if len(seg) else -120
            if level > -90:
                seg *= db(max(-12.0, min(12.0, DIALOGUE_RMS_DB - level)))
        seg *= db(clip.get('gain_db', 0.0))
        seg = fade(seg, clip.get('fade_in', 0.005), clip.get('fade_out', 0.01))
        start = int(round(clip['start'] * SR))
        end = min(total, start + len(seg))
        if end > start:
            buses[clip['bus']][start:end] += seg[: end - start]
    env = presence_envelope(buses['dialogue'])
    for bus, depth in DUCK_DB.items():
        gain = 1 - (1 - db(depth)) * env
        buses[bus] *= gain[:, None]
    mix = sum(buses[b] * db(BUS_GAIN_DB[b]) for b in buses)
    pre_peak = float(np.abs(mix).max()) if len(mix) else 0.0
    mix = limit(mix)
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = {}
    for b, arr in buses.items():
        p = out_dir / 'stems' / f'{b}.wav'
        p.parent.mkdir(parents=True, exist_ok=True)
        sf.write(p, np.clip(arr, -1, 1), SR, subtype='PCM_24')
        stems[b] = str(p)
    mix_path = out_dir / 'mix.wav'
    sf.write(mix_path, np.clip(mix, -1, 1), SR, subtype='PCM_24')
    return {'mix': str(mix_path), 'stems': stems, 'seconds': total / SR,
            'pre_limit_peak_db': round(20 * np.log10(max(pre_peak, 1e-9)), 2),
            'duck_active_ratio': round(float((env > 0.5).mean()), 3)}


# ----------------------------------------------------------- mastering ----

def _loudnorm_json(stderr: str) -> Dict[str, Any]:
    m = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', stderr, re.S)
    if not m:
        raise RuntimeError('loudnorm analysis printed no JSON')
    return json.loads(m[-1])


def measure(path: str) -> Dict[str, float]:
    proc = subprocess.run(
        ['ffmpeg', '-nostdin', '-hide_banner', '-i', str(path), '-af',
         'loudnorm=I=-16:TP=-1:LRA=11:print_format=json', '-f', 'null', '-'],
        capture_output=True, text=True)
    d = _loudnorm_json(proc.stderr)
    return {'lufs_i': float(d['input_i']), 'true_peak_dbtp': float(d['input_tp']),
            'lra': float(d['input_lra'])}


def master(mix_wav: str, out_path: str, *, target: float = -16.0,
           tp: float = -1.0, bitrate: str = '192k',
           metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Two-pass loudnorm, single MP3 encode with tags, then verify."""
    proc = subprocess.run(
        ['ffmpeg', '-nostdin', '-hide_banner', '-i', mix_wav, '-af',
         f'loudnorm=I={target}:TP={tp}:LRA=11:print_format=json', '-f', 'null', '-'],
        capture_output=True, text=True)
    m = _loudnorm_json(proc.stderr)
    af = (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={m['input_i']}:"
          f"measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,"
          f"alimiter=limit={10 ** ((tp - 0.5) / 20):.4f}:level=false")
    tags: List[str] = []
    for k, v in (metadata or {}).items():
        tags += ['-metadata', f'{k}={v}']
    cmd = ['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', mix_wav, '-af', af,
           '-ar', '44100', '-c:a', 'libmp3lame', '-b:a', bitrate, *tags, out_path]
    subprocess.run(cmd, check=True)
    result = measure(out_path)
    result['ok'] = (abs(result['lufs_i'] - target) <= 1.0
                    and result['true_peak_dbtp'] <= tp + 0.3)
    result['encodes'] = 1
    return result
