"""
Unified dialogue synthesis for Stardock Podium.

Routes speech through ``engine_order`` in ``voices/voice_config.json``:

- ``xtts`` — Coqui XTTS v2 voice cloning from each character's ``speaker_wav``
  (optional; ``pip install -r requirements-voice-clone.txt``).
- ``kokoro`` — built-in Kokoro voices via ``kokoro_voice`` (always available
  as fallback).

Set ``STARDOCK_DISABLE_XTTS=1`` to force Kokoro only without editing JSON.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tts_engine import (
    get_kokoro_engine,
    get_xtts_engine,
    SynthError,
    KOKORO_AVAILABLE,
    XTTS_AVAILABLE,
)

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path('voices/voice_config.json')
_REPO_ROOT = Path(__file__).resolve().parent

_SPEAKER_SUFFIX_RE = re.compile(
    r"""\s*\(\s*(?:v\.?\s*o\.?|o\.?\s*s\.?|cont(?:inued|'d|d)?|
        off|off-?screen|over|voice[\s-]?over|pre-?lap|
        whisper(?:ed|ing)?|narr|narrating|narration|
        beat|pause|to\s+self)\s*\)""",
    re.IGNORECASE | re.VERBOSE,
)


def _canonicalize_name(character: str) -> str:
    """Reduce a raw speaker label to a stable lookup key.

    Strips screenplay suffixes like ``(V.O.)`` / ``(CONT'D)`` that chain
    onto the end of a name (possibly multiple times), drops a trailing
    ``:`` left over from colon-style dialogue, then lowercases and
    removes whitespace/punctuation so ``"LT. COMMANDER KIRA JARO"`` and
    ``"lieutenant_commander_kira_jaro"`` hash to the same key.
    """
    name = character.strip()
    name = name.rstrip(':').rstrip()
    for _ in range(4):
        stripped = _SPEAKER_SUFFIX_RE.sub('', name).rstrip()
        if stripped == name:
            break
        name = stripped
    name = name.lower()
    name = name.replace("'", '').replace('.', '')
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'_+', '_', name).strip('_')
    return name


def load_voice_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load voice JSON configuration."""
    cfg_path = path or _DEFAULT_CONFIG
    if not cfg_path.exists():
        return {}
    with open(cfg_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_character_voice_config(
    character: str,
    voice_config: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Match a script character name to a voice_config characters entry.

    Resolution order:

    1. Exact match against ``characters`` keys (case-sensitive).
    2. Canonical key derived from ``character`` (see :func:`_canonicalize_name`).
    3. Top-level ``aliases`` map lookup against the canonical key,
       whose value is a canonical character key in ``characters``.
    4. Bare ``character.lower()`` fallback for backward compatibility.
    """
    chars = voice_config.get('characters') or {}
    if character in chars:
        return chars[character]

    canon = _canonicalize_name(character)
    if canon in chars:
        return chars[canon]

    aliases = voice_config.get('aliases') or {}
    aliased = aliases.get(canon)
    if aliased and aliased in chars:
        return chars[aliased]

    simple = character.lower()
    if simple in chars:
        return chars[simple]
    return None


def resolve_speaker_wav_path(
    speaker_wav: str,
    cwd: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve ``speaker_wav`` from voice_config to an existing file."""
    if not speaker_wav or not str(speaker_wav).strip():
        return None
    p = Path(speaker_wav)
    if p.is_file():
        return p.resolve()
    base = cwd or Path.cwd()
    for parent in (base, _REPO_ROOT):
        cand = (parent / speaker_wav).resolve()
        if cand.is_file():
            return cand
    return None


def _effective_engine_order(
    cfg: Dict[str, Any],
    entry: Dict[str, Any],
) -> List[str]:
    raw = cfg.get('engine_order') or ['kokoro']
    base: List[str] = []
    for e in raw:
        if isinstance(e, str) and e.strip():
            base.append(e.strip().lower())

    override = entry.get('tts_engine')
    if isinstance(override, str):
        o = override.strip().lower()
        if o == 'kokoro':
            base = ['kokoro']
        elif o == 'xtts':
            base = ['xtts', 'kokoro']

    if os.environ.get('STARDOCK_DISABLE_XTTS', '').strip().lower() in (
        '1', 'true', 'yes',
    ):
        base = [e for e in base if e != 'xtts']

    seen: set[str] = set()
    out: List[str] = []
    for e in base:
        if e not in ('kokoro', 'xtts'):
            logger.warning(
                'Unknown engine %r in engine_order — skipping '
                '(supported: kokoro, xtts).',
                e,
            )
            continue
        if e not in seen:
            seen.add(e)
            out.append(e)
    if 'kokoro' not in out:
        out.append('kokoro')
    return out


def _pick_voice_id(entry: Dict[str, Any], character_key: str) -> str:
    """Pick Kokoro voice id (built-in name)."""
    voice = entry.get('kokoro_voice')
    if voice:
        return str(voice)
    speaker_wav = entry.get('speaker_wav')
    if speaker_wav:
        logger.warning(
            'Character %r has no kokoro_voice; passing speaker_wav %r '
            '— Kokoro will fall back to the default voice.',
            character_key, speaker_wav,
        )
        return str(speaker_wav)
    raise ValueError(
        f'Character {character_key!r} has neither kokoro_voice nor '
        'speaker_wav in voice_config.json'
    )


class KokoroDialogueSynthesizer:
    """Dialogue synthesis via engine_order (XTTS + Kokoro)."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or _DEFAULT_CONFIG
        self._voice_config: Dict[str, Any] = {}

    def _load(self) -> Dict[str, Any]:
        self._voice_config = load_voice_config(self.config_path)
        return self._voice_config

    def _synth_one(
        self,
        text: str,
        entry: Dict[str, Any],
        character_key: str,
        output_path: str,
    ) -> str:
        """Synthesize one line; returns engine name used (``xtts`` or ``kokoro``)."""
        cfg = self._load()
        order = _effective_engine_order(cfg, entry)
        last_err: Optional[BaseException] = None
        lang = str(entry.get('language', 'en'))

        for eng in order:
            if eng == 'xtts':
                if not XTTS_AVAILABLE:
                    logger.debug(
                        'XTTS not installed — skipping for %s', character_key)
                    continue
                sw = entry.get('speaker_wav')
                path = resolve_speaker_wav_path(str(sw)) if sw else None
                if not path:
                    logger.debug(
                        'XTTS skipped for %s — speaker_wav not found (%r)',
                        character_key, sw,
                    )
                    continue
                try:
                    get_xtts_engine().synth(
                        text=text,
                        speaker_wav=str(path),
                        language=lang,
                        output_path=output_path,
                    )
                    return 'xtts'
                except Exception as e:
                    last_err = e
                    logger.warning(
                        'XTTS failed for %s, trying next engine: %s',
                        character_key, e,
                    )
                continue

            if eng == 'kokoro':
                if not KOKORO_AVAILABLE:
                    raise SynthError(
                        'Kokoro TTS is not installed. Install dependencies '
                        'from requirements.txt (kokoro, torch, soundfile).'
                    )
                voice_id = _pick_voice_id(entry, character_key)
                try:
                    get_kokoro_engine().synth(
                        text=text,
                        speaker_wav=voice_id,
                        language=lang,
                        output_path=output_path,
                    )
                    return 'kokoro'
                except Exception as e:
                    last_err = e
                    logger.error('Kokoro failed for %s: %s', character_key, e)
                    raise SynthError(str(e)) from e

        msg = f'All configured TTS engines failed for {character_key}'
        if last_err:
            raise SynthError(f'{msg}: {last_err}') from last_err
        raise SynthError(msg)

    def synth(
        self,
        text: str,
        character_voice_key: str,
        output_path: str,
    ) -> None:
        """Synthesize dialogue for a configured character key."""
        cfg = self._load()
        entry = (cfg.get('characters') or {}).get(character_voice_key)
        if not entry:
            raise ValueError(
                f'No voice_config entry for character key: {character_voice_key}'
            )
        used = self._synth_one(text, entry, character_voice_key, output_path)
        logger.info(
            'Synthesized dialogue (%s): %s → %s',
            used, character_voice_key, output_path,
        )

    def synth_for_display_name(
        self,
        text: str,
        character_display: str,
        output_path: str,
    ) -> None:
        """Resolve display name (e.g. script speaker) then synthesize."""
        cfg = self._load()
        entry = resolve_character_voice_config(character_display, cfg)
        if not entry:
            raise ValueError(
                f'No voice_config match for speaker: {character_display!r}'
            )
        chars = cfg.get('characters') or {}
        key = None
        for k, v in chars.items():
            if v is entry:
                key = k
                break
        if key is None:
            key = character_display
        used = self._synth_one(text, entry, key, output_path)
        logger.info(
            'Synthesized dialogue (%s): %r → %s',
            used, character_display, output_path,
        )


_synth: Optional[KokoroDialogueSynthesizer] = None


def get_dialogue_synthesizer() -> KokoroDialogueSynthesizer:
    """Singleton dialogue synthesizer."""
    global _synth
    if _synth is None:
        _synth = KokoroDialogueSynthesizer()
    return _synth
