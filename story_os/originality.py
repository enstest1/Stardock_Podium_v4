"""Originality and repetition metrics (QUALITY-002).

Owns ``data/projects/<id>/metrics/quality.jsonl`` (append-only; the last
record per episode wins). Character names are masked before n-gram work.
Thresholds are UNCALIBRATED defaults (doc 07 §8 was not supplied).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

THRESHOLDS = {'self_repeat_4gram': 0.08, 'cross_episode_jaccard': 0.12,
              'slop_per_1k_words': 3.0, 'distinct_2_min': 0.55}
SLOP = ['a testament to', 'shiver down', 'shivers down', 'little did', 'tapestry of',
        'in that moment', 'the weight of', 'a wave of', 'barely above a whisper',
        'let out a breath', "didn't know she was holding", 'eyes widened',
        'time seemed to stop', 'something shifted', 'the air was thick',
        'a mix of', 'couldn\'t help but', 'it was as if', 'heart pounding']


def _text(script: Dict[str, Any], names: List[str]) -> str:
    t = ' '.join((l.get('content') or '') for sc in script.get('scenes') or []
                 for l in sc.get('lines') or [] if l.get('type') in ('dialogue', 'narration'))
    t = t.lower()
    for n in names:
        for part in n.lower().replace('.', '').split():
            if len(part) > 2:
                t = re.sub(rf'\b{re.escape(part)}\b', 'NAME', t)
    return t


def _ngrams(words: List[str], n: int) -> List[tuple]:
    return [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]


def metrics(script: Dict[str, Any], names: List[str],
            previous: List[Dict[str, Any]] = ()) -> Dict[str, Any]:
    text = _text(script, names)
    words = re.findall(r"[a-z']+|NAME", text)
    n = len(words) or 1
    bi = _ngrams(words, 2)
    four = _ngrams(words, 4)
    repeat4 = (len(four) - len(set(four))) / (len(four) or 1)
    slop_hits = {p: text.count(p) for p in SLOP if p in text}
    shingles = set(_ngrams(words, 5))
    cross = 0.0
    for prev in previous:
        pw = re.findall(r"[a-z']+|NAME", _text(prev, names))
        ps = set(_ngrams(pw, 5))
        if shingles and ps:
            cross = max(cross, len(shingles & ps) / len(shingles | ps))
    m = {'words': n, 'distinct_2': round(len(set(bi)) / (len(bi) or 1), 3),
         'self_repeat_4gram': round(repeat4, 3),
         'slop_per_1k_words': round(1000 * sum(slop_hits.values()) / n, 2),
         'slop_hits': slop_hits, 'cross_episode_jaccard': round(cross, 3)}
    flags = []
    if m['self_repeat_4gram'] > THRESHOLDS['self_repeat_4gram']:
        flags.append('self_repetition')
    if m['cross_episode_jaccard'] > THRESHOLDS['cross_episode_jaccard']:
        flags.append('similar_to_previous_episode')
    if m['slop_per_1k_words'] > THRESHOLDS['slop_per_1k_words']:
        flags.append('cliche_density')
    if m['distinct_2'] < THRESHOLDS['distinct_2_min']:
        flags.append('low_lexical_variety')
    m['flags'] = flags
    m['thresholds'] = 'uncalibrated'
    return m


def record(project_id: str, episode_id: str, data: Dict[str, Any]) -> Path:
    from story_os.projects import project_dir
    p = project_dir(project_id) / 'metrics' / 'quality.jsonl'
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'episode_id': episode_id, 'at': time.time(), **data}) + '\n')
    return p
