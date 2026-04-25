"""
Star Trek–aware text tweaks before Kokoro / misaki phonemization.

Kokoro has no SSML; cardinal readings of stardates (e.g. 871 → "eight hundred
seventy-one") and odd G2P for franchise terms are fixed by expanding stardates
to spoken digits and respelling select proper nouns.

XTTS and other engines should run the same :func:`normalize_trek_tts_text`
pipeline so species names stay consistent across backends.
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
    # --- Dominion & Alpha/Beta quadrant (longer phrases first) ---
    (re.compile(r"\bJem'?Hadars\b", re.IGNORECASE), 'Jem-hah-darz'),
    (re.compile(r"\bJem'?Hadar\b", re.IGNORECASE), 'Jem-hah-dar'),
    (re.compile(r'\bNausicaans\b', re.IGNORECASE), 'Naw-sik-ee-unz'),
    (re.compile(r'\bNausicaan\b', re.IGNORECASE), 'Naw-sik-ee-un'),
    (re.compile(r'\bTalaxians\b', re.IGNORECASE), 'Tah-lak-see-unz'),
    (re.compile(r'\bTalaxian\b', re.IGNORECASE), 'Tah-lak-see-un'),
    (re.compile(r'\bDenobulans\b', re.IGNORECASE), 'Den-obb-yoo-lunz'),
    (re.compile(r'\bDenobulan\b', re.IGNORECASE), 'Den-obb-yoo-lun'),
    (re.compile(r'\bTellarites\b', re.IGNORECASE), 'Tell-er-ights'),
    (re.compile(r'\bTellarite\b', re.IGNORECASE), 'Tell-er-ight'),
    (re.compile(r'\bCardassians\b', re.IGNORECASE), 'Car-dass-ee-unz'),
    (re.compile(r'\bCardassian\b', re.IGNORECASE), 'Car-dass-ee-un'),
    (re.compile(r'\bBajorians\b', re.IGNORECASE), 'Bay-jor-uns'),
    (re.compile(r'\bBajorian\b', re.IGNORECASE), 'Bay-jor-un'),
    (re.compile(r'\bBajorans\b', re.IGNORECASE), 'Bay-jor-unz'),
    (re.compile(r'\bBajoran\b', re.IGNORECASE), 'Bay-jor-un'),
    (re.compile(r'\bRomulans\b', re.IGNORECASE), 'Rom-yoo-lunz'),
    (re.compile(r'\bRomulan\b', re.IGNORECASE), 'Rom-yoo-lun'),
    (re.compile(r'\bAndorians\b', re.IGNORECASE), 'An-dore-ee-unz'),
    (re.compile(r'\bAndorian\b', re.IGNORECASE), 'An-dore-ee-un'),
    (re.compile(r'\bBolians\b', re.IGNORECASE), 'Bow-lee-unz'),
    (re.compile(r'\bBolian\b', re.IGNORECASE), 'Bow-lee-un'),
    (re.compile(r'\bCaitians\b', re.IGNORECASE), 'Kay-shunz'),
    (re.compile(r'\bCaitian\b', re.IGNORECASE), 'Kay-shun'),
    (re.compile(r'\bOrions\b', re.IGNORECASE), 'Oh-ree-unz'),
    (re.compile(r'\bOrion\b', re.IGNORECASE), 'Oh-ree-un'),
    (re.compile(r'\bSulibans\b', re.IGNORECASE), 'Soo-lee-bunz'),
    (re.compile(r'\bSuliban\b', re.IGNORECASE), 'Soo-lee-bun'),
    (re.compile(r'\bHirogen\b', re.IGNORECASE), 'High-row-jen'),
    (re.compile(r'\bRemans\b', re.IGNORECASE), 'Ree-munz'),
    (re.compile(r'\bReman\b', re.IGNORECASE), 'Ree-mun'),
    (re.compile(r'\bChangelings\b', re.IGNORECASE), 'Change-lingz'),
    (re.compile(r'\bChangeling\b', re.IGNORECASE), 'Change-ling'),
    (re.compile(r'\bFounders\b', re.IGNORECASE), 'Fown-ders'),
    (re.compile(r'\bFounder\b', re.IGNORECASE), 'Fown-der'),
    (re.compile(r'\bProphets\b', re.IGNORECASE), 'Prof-its'),
    (re.compile(r'\bProphet\b', re.IGNORECASE), 'Prof-it'),
    (re.compile(r'\bPah-?wraiths\b', re.IGNORECASE), 'Pah-rayths'),
    (re.compile(r'\bPah-?wraith\b', re.IGNORECASE), 'Pah-rayth'),
    (re.compile(r'\bEl-?Aurians\b', re.IGNORECASE), 'El-aw-ree-unz'),
    (re.compile(r'\bEl-?Aurian\b', re.IGNORECASE), 'El-aw-ree-un'),
    (re.compile(r'\bSymbionts\b', re.IGNORECASE), 'Sim-bee-onts'),
    (re.compile(r'\bSymbiont\b', re.IGNORECASE), 'Sim-bee-ont'),
    (re.compile(r'\bTrills\b', re.IGNORECASE), 'Trillz'),
    (re.compile(r'\bTrill\b'), 'Trill'),
    (re.compile(r'\bVulcans\b', re.IGNORECASE), 'Vul-kunz'),
    (re.compile(r'\bVulcan\b', re.IGNORECASE), 'Vul-kun'),
    (re.compile(r'\bKlingons\b', re.IGNORECASE), 'Kling-onz'),
    (re.compile(r'\bKlingon\b', re.IGNORECASE), 'Kling-on'),
    (re.compile(r'\bFerengi\b', re.IGNORECASE), 'Feh-ren-gee'),
    (re.compile(r'\bFerenginar\b', re.IGNORECASE), 'Feh-ren-gee-nar'),
    (re.compile(r'\bBetazoids\b', re.IGNORECASE), 'Bay-tah-zoydz'),
    (re.compile(r'\bBetazoid\b', re.IGNORECASE), 'Bay-tah-zoyd'),
    (re.compile(r'\bBreen\b', re.IGNORECASE), 'Breen'),
    (re.compile(r'\bGorn\b', re.IGNORECASE), 'Gorn'),
    (re.compile(r'\bHorta\b', re.IGNORECASE), 'Hor-tah'),
    (re.compile(r'\bBorg\b', re.IGNORECASE), 'Borg'),
    (re.compile(r'\bTribbles\b', re.IGNORECASE), 'Trib-ulz'),
    (re.compile(r'\bTribble\b', re.IGNORECASE), 'Trib-ul'),
    (re.compile(r'\bQomar\b', re.IGNORECASE), 'Koh-mar'),
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
    """Full pipeline for dialogue and narration sent to TTS."""
    if not text:
        return text
    t = expand_stardates_for_speech(text)
    t = apply_trek_lexicon(t)
    return t
