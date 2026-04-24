"""
Star Trek–aware text tweaks before Kokoro / misaki phonemization.

Kokoro has no SSML; cardinal readings of stardates (e.g. 871 → "eight hundred
seventy-one") and odd G2P for franchise terms are fixed by expanding stardates
to spoken digits and respelling select proper nouns.
"""

from __future__ import annotations

import re
from typing import List, Tuple

_DIGIT_WORDS = {
    '0': 'zero',
    '1': 'one',
    '2': 'two',
    '3': 'three',
    '4': 'four',
    '5': 'five',
    '6': 'six',
    '7': 'seven',
    '8': 'eight',
    '9': 'nine',
}


def _spell_digits(digits: str) -> str:
    return ' '.join(_DIGIT_WORDS[c] for c in digits if c in _DIGIT_WORDS)


# Longest-first regex replacements (species / franchise lexicon).
# Spellings tuned for English G2P: approximate screen pronunciations.
_LEXICON: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r'\bBajorians\b', re.IGNORECASE), 'Bay-jor-uns'),
    (re.compile(r'\bBajorian\b', re.IGNORECASE), 'Bay-jor-un'),
    (re.compile(r'\bBajorans\b', re.IGNORECASE), 'Bay-jor-uns'),
    (re.compile(r'\bBajoran\b', re.IGNORECASE), 'Bay-jor-un'),
    (re.compile(r'\bCardassians\b', re.IGNORECASE), 'Car-dass-ee-uns'),
    (re.compile(r'\bCardassian\b', re.IGNORECASE), 'Car-dass-ee-un'),
    (re.compile(r'\bRomulans\b', re.IGNORECASE), 'Rom-yoo-luns'),
    (re.compile(r'\bRomulan\b', re.IGNORECASE), 'Rom-yoo-lun'),
    (re.compile(r'\bVulcans?\b', re.IGNORECASE), 'Vul-kuns'),
    (re.compile(r'\bKlingons?\b', re.IGNORECASE), 'Kling-ons'),
    (re.compile(r'\bFerengi\b', re.IGNORECASE), 'Feh-ren-gee'),
    (re.compile(r'\bBetazoids?\b', re.IGNORECASE), 'Bay-tah-zoyds'),
    (re.compile(r'\bTrill\b'), 'Trill'),
]


_STARDATE_RE = re.compile(
    r'\b(?P<label>[Ss]tardate)\s*:?\s*(?P<num>[\d][\d\s,]*\.?[\d\s,]*)'
)


def _expand_stardate_number(raw: str) -> str:
    """Turn a stardate numeral into spoken digits (e.g. 3190.1 → word digits)."""
    t = raw.replace(',', '').replace(' ', '')
    if not any(c.isdigit() for c in t):
        return raw
    if '.' in t:
        whole, frac = t.split('.', 1)
        whole_d = ''.join(c for c in whole if c.isdigit())
        frac_d = ''.join(c for c in frac if c.isdigit())
        if not whole_d:
            return raw
        spoken = _spell_digits(whole_d)
        if frac_d:
            spoken = f'{spoken} point {_spell_digits(frac_d)}'
        return spoken
    whole_d = ''.join(c for c in t if c.isdigit())
    return _spell_digits(whole_d) if whole_d else raw


def expand_stardates_for_speech(text: str) -> str:
    """Replace ``Stardate 47215.2`` with spoken digit form (no cardinal thousands)."""

    def _sub(m: re.Match[str]) -> str:
        label = m.group('label')
        return f'{label} {_expand_stardate_number(m.group("num"))}'

    return _STARDATE_RE.sub(_sub, text)


def apply_trek_lexicon(text: str) -> str:
    """Apply species and name respellings."""
    out = text
    for pat, repl in _LEXICON:
        out = pat.sub(repl, out)
    return out


def normalize_trek_tts_text(text: str) -> str:
    """Full pipeline for dialogue and narration sent to Kokoro."""
    if not text:
        return text
    t = expand_stardates_for_speech(text)
    t = apply_trek_lexicon(t)
    return t
