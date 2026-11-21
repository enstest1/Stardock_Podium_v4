"""Pairwise judge (QUALITY-003).

``compare(a, b, question)`` asks two judge roles (``judge_a``, ``judge_b``),
each in both orders: four calls. A judge that prefers the same *position*
in both orders is counted as a tie (order bias neutralised). The decision
needs a strict majority of non-tie votes, else ``undecided``.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SYSTEM = ('You are a strict, fair story judge. Compare two texts on the '
          'question only. Answer JSON: {"winner": 1 or 2 or 0, "reason": "..."} '
          '(0 = no meaningful difference).')


def _ask(role: str, question: str, context: str, t1: str, t2: str) -> int:
    from story_os import llm
    user = (f'QUESTION: {question}\n' + (f'CONTEXT: {context}\n' if context else '')
            + f'\nText 1:\n{t1}\n\nText 2:\n{t2}')
    try:
        raw = llm.complete(role, SYSTEM, user, json=True, max_tokens=200, temperature=0.0)
        start, end = raw.find('{'), raw.rfind('}')
        w = int(json.loads(raw[start:end + 1]).get('winner', 0))
        return w if w in (0, 1, 2) else 0
    except Exception as e:
        logger.warning('Judge %s answer unusable (%s); counted as tie', role, e)
        return 0


def compare(a: str, b: str, question: str, context: str = '') -> Dict[str, Any]:
    by_judge: Dict[str, str] = {}
    wins_a = wins_b = ties = flips = 0
    for role in ('judge_a', 'judge_b'):
        first = _ask(role, question, context, a, b)      # a is Text 1
        second = _ask(role, question, context, b, a)     # a is Text 2
        pref1 = {1: 'a', 2: 'b'}.get(first)
        pref2 = {1: 'b', 2: 'a'}.get(second)
        if pref1 and pref1 == pref2:
            by_judge[role] = pref1
            if pref1 == 'a':
                wins_a += 1
            else:
                wins_b += 1
        else:
            by_judge[role] = 'tie'
            ties += 1
            if first and second and first == second:
                flips += 1
    decided = wins_a + wins_b
    winner = 'undecided'
    if decided and wins_a > decided / 2 and wins_a > wins_b:
        winner = 'a'
    elif decided and wins_b > decided / 2 and wins_b > wins_a:
        winner = 'b'
    return {'winner': winner, 'wins_a': wins_a, 'wins_b': wins_b, 'ties': ties,
            'order_flips': flips, 'by_judge': by_judge}


def rank(items: List[str], question: str, context: str = '') -> List[int]:
    """Round-robin (<= 4 items). Returns indices best first; ties keep order."""
    score = [0] * len(items)
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            v = compare(items[i], items[j], question, context)['winner']
            if v == 'a':
                score[i] += 1
            elif v == 'b':
                score[j] += 1
    return sorted(range(len(items)), key=lambda k: (-score[k], k))
