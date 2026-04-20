"""
Unified dialogue synthesis for Stardock Podium.

Routes speech generation through Kokoro (local) using voices/voice_config.json.
ElevenLabs is not used by this module.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

from tts_engine import get_kokoro_engine, SynthError, KOKORO_AVAILABLE

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path('voices/voice_config.json')

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


class KokoroDialogueSynthesizer:
    """Local dialogue synthesis via Kokoro."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config_path = config_path or _DEFAULT_CONFIG
        self._voice_config: Dict[str, Any] = {}

    def _load(self) -> Dict[str, Any]:
        self._voice_config = load_voice_config(self.config_path)
        return self._voice_config

    def synth(
        self,
        text: str,
        character_voice_key: str,
        output_path: str,
    ) -> None:
        """Synthesize dialogue for a configured character key.

        Args:
            text: Line text to speak.
            character_voice_key: Key in voice_config['characters'].
            output_path: WAV path to write (16 kHz mono from Kokoro).

        Raises:
            SynthError: If Kokoro is unavailable or synthesis fails.
            ValueError: If the character has no speaker_wav.
        """
        if not KOKORO_AVAILABLE:
            raise SynthError(
                'Kokoro TTS is not installed. Install dependencies from '
                'requirements.txt (kokoro-tts, torch, soundfile).'
            )
        cfg = self._load()
        entry = (cfg.get('characters') or {}).get(character_voice_key)
        if not entry:
            raise ValueError(
                f'No voice_config entry for character key: {character_voice_key}'
            )
        speaker_wav = entry.get('speaker_wav')
        if not speaker_wav:
            raise ValueError(
                f'Character {character_voice_key!r} has no speaker_wav in '
                'voice_config.json'
            )
        lang = entry.get('language', 'en')
        engine = get_kokoro_engine()
        engine.synth(
            text=text,
            speaker_wav=speaker_wav,
            language=lang,
            output_path=output_path,
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
        # Find canonical key for logging only
        chars = cfg.get('characters') or {}
        key = None
        for k, v in chars.items():
            if v is entry:
                key = k
                break
        if key is None:
            key = character_display
        speaker_wav = entry.get('speaker_wav')
        if not speaker_wav:
            raise ValueError(f'No speaker_wav for speaker {character_display!r}')
        lang = entry.get('language', 'en')
        engine = get_kokoro_engine()
        engine.synth(
            text=text,
            speaker_wav=speaker_wav,
            language=lang,
            output_path=output_path,
        )


_synth: Optional[KokoroDialogueSynthesizer] = None


def get_dialogue_synthesizer() -> KokoroDialogueSynthesizer:
    """Singleton Kokoro dialogue synthesizer."""
    global _synth
    if _synth is None:
        _synth = KokoroDialogueSynthesizer()
    return _synth
