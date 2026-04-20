"""
Lightweight post-render audio checks (duration, peak, silence hints).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

try:
    import ffmpeg
except ImportError:
    ffmpeg = None  # type: ignore

try:
    import soundfile as sf
    import numpy as np
except ImportError:
    sf = None
    np = None


def _peak_sample(path: Path) -> float:
    if sf is None or np is None:
        return -1.0
    data, _sr = sf.read(str(path), always_2d=True)
    if data.size == 0:
        return 0.0
    return float(np.max(np.abs(data)))


def run_episode_audio_qa(episode_id: str, audio_dir: Path) -> Dict[str, Any]:
    """Scan scene WAVs and episode mix; write ``audio_qa_report.json``."""
    report: Dict[str, Any] = {
        'episode_id': episode_id,
        'files': [],
        'issues': [],
    }
    if ffmpeg is None:
        report['issues'].append('ffmpeg-python not available for probing')
        return report

    wavs: List[Path] = sorted(audio_dir.rglob('*.wav'))
    for wav in wavs[:200]:
        entry: Dict[str, Any] = {'path': str(wav)}
        try:
            probe = ffmpeg.probe(str(wav))
            dur = float(probe['format'].get('duration', 0) or 0)
            entry['duration_s'] = dur
            if dur < 0.05:
                report['issues'].append(f'Very short clip: {wav.name}')
        except Exception as e:
            entry['error'] = str(e)
            report['issues'].append(f'Probe failed {wav.name}: {e}')
        pk = _peak_sample(wav)
        if pk >= 0:
            entry['peak_abs'] = round(pk, 4)
            if pk > 0.99:
                report['issues'].append(f'Possible clipping: {wav.name}')
        report['files'].append(entry)

    out = audio_dir / 'audio_qa_report.json'
    try:
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
    except OSError as e:
        logger.warning('Could not write audio QA report: %s', e)
    return report
