"""
Text tweaks before Kokoro / misaki phonemization (generic since BASE-003).

Kokoro has no SSML, so two things are done in text:

1. *number labels*: digits after a label word (for example a log-date label)
   are spoken digit by digit ("47215.2" -> "four seven two one five point
   two") instead of as a cardinal number;
2. a *pronunciation lexicon*: longest-first respellings of invented names.

Both come from data, never from code: the active show's ``format``
(``pronunciation_lexicon``, ``number_rules``) for projects, and
``data/shows/legacy_lexicon.json`` + ``data/shows/legacy_format.json`` for
the pre-v5 show. ``AudioPipeline`` selects the active show per render.
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

_DIGIT_WORDS = {'0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
                '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'}

Lexicon = List[Tuple['re.Pattern[str]', str]]
_state = threading.local()
_legacy_cache: Dict[str, object] = {}


def _data_dir() -> Path:
    try:
        from config.paths import DATA_DIR
        return Path(DATA_DIR)
    except Exception:
        return Path('data')


def _spell_digits(digits: str) -> str:
    return ' '.join(_DIGIT_WORDS[c] for c in digits if c in _DIGIT_WORDS)


def _expand_number(raw: str) -> str:
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
        return f'{spoken} point {_spell_digits(frac_d)}' if frac_d else spoken
    whole_d = ''.join(c for c in t if c.isdigit())
    return _spell_digits(whole_d) if whole_d else raw


def compile_lexicon(entries: Iterable) -> Lexicon:
    """Entries: ``{pattern, ignore_case, replacement}`` or a {word: respelling} dict."""
    out: Lexicon = []
    if isinstance(entries, dict):
        for word in sorted(entries, key=len, reverse=True):
            out.append((re.compile(rf'\b{re.escape(word)}\b', re.IGNORECASE), entries[word]))
        return out
    for e in entries:
        flags = re.IGNORECASE if e.get('ignore_case') else 0
        out.append((re.compile(e['pattern'], flags), e['replacement']))
    return out


def _label_regex(labels: List[str]) -> Optional['re.Pattern[str]']:
    if not labels:
        return None
    alt = '|'.join(re.escape(l) for l in labels)
    return re.compile(rf'\b(?P<label>{alt})\s*:?\s*(?P<num>[\d][\d\s,]*\.?[\d\s,]*)',
                      re.IGNORECASE)


def legacy_rules() -> Tuple[Lexicon, Optional['re.Pattern[str]']]:
    if 'rules' not in _legacy_cache:
        lex: Lexicon = []
        labels: List[str] = []
        lp = _data_dir() / 'shows' / 'legacy_lexicon.json'
        fp = _data_dir() / 'shows' / 'legacy_format.json'
        if lp.exists():
            lex = compile_lexicon(json.loads(lp.read_text(encoding='utf-8'))['entries'])
        if fp.exists():
            labels = json.loads(fp.read_text(encoding='utf-8')).get('number_labels', [])
        _legacy_cache['rules'] = (lex, _label_regex(labels))
    return _legacy_cache['rules']


def set_active_show(lexicon=None, number_labels: Optional[List[str]] = None) -> None:
    """Use a project's rules on this thread; ``None`` restores the legacy rules."""
    if lexicon is None and number_labels is None:
        _state.rules = None
    else:
        _state.rules = (compile_lexicon(lexicon or {}), _label_regex(number_labels or []))


def _active() -> Tuple[Lexicon, Optional['re.Pattern[str]']]:
    rules = getattr(_state, 'rules', None)
    return rules if rules is not None else legacy_rules()


def expand_number_labels(text: str, regex=None) -> str:
    regex = regex if regex is not None else _active()[1]
    if regex is None:
        return text
    return regex.sub(lambda m: f"{m.group('label')} {_expand_number(m.group('num'))}", text)


def apply_lexicon(text: str, lexicon: Optional[Lexicon] = None) -> str:
    out = text
    for pat, repl in (lexicon if lexicon is not None else _active()[0]):
        out = pat.sub(repl, out)
    return out


def normalize_tts_text(text: str) -> str:
    """Full pipeline for dialogue and narration sent to TTS (active show's rules)."""
    if not text:
        return text
    lex, labels = _active()
    return apply_lexicon(expand_number_labels(text, labels), lex)
