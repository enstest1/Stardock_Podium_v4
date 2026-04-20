#!/usr/bin/env python
"""
Voice Registry Module for Stardock Podium.

Kokoro-only — no ElevenLabs. Each voice is a ``speaker_wav`` path (mono 16
kHz WAV). Registration updates ``voices/registry.json`` and the matching entry
in ``voices/voice_config.json`` so ``dialogue_engine`` / ``audio_pipeline``
can resolve speakers.
"""

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from mem0_client import get_mem0_client

logger = logging.getLogger(__name__)

from config.paths import VOICES_DIR, VOICE_SAMPLES_DIR

SAMPLES_DIR = VOICE_SAMPLES_DIR
REGISTRY_FILE = VOICES_DIR / 'registry.json'
VOICE_CONFIG_PATH = VOICES_DIR / 'voice_config.json'


def slug_character(name: str) -> str:
    """Match ``dialogue_engine.resolve_character_voice_config`` key rules."""
    return name.strip().lower().replace(' ', '_').replace("'", '')


class VoiceRegistry:
    """Manages Kokoro voice registration and retrieval for characters."""

    def __init__(self, voices_dir: Optional[str] = None) -> None:
        self.voices_dir = Path(voices_dir) if voices_dir else VOICES_DIR
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

        self.mem0_client = get_mem0_client()
        self.registry = self._load_registry()
        logger.info(
            'VoiceRegistry loaded — %s voices registered',
            len(self.registry),
        )

    # ── Registry I/O ──────────────────────────────────────────────────────

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        if REGISTRY_FILE.exists():
            try:
                with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
                logger.error('Voice registry must be a JSON object; resetting.')
            except Exception as e:
                logger.error('Error loading voice registry: %s', e)
        return {}

    def _save_registry(self) -> None:
        try:
            REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.registry, f, indent=2)
        except Exception as e:
            logger.error('Error saving voice registry: %s', e)

    def _load_voice_config(self) -> Dict[str, Any]:
        if not VOICE_CONFIG_PATH.exists():
            return {
                'engine_order': ['kokoro'],
                'characters': {},
                'audio_settings': {
                    'sample_rate': 16000,
                    'channels': 1,
                    'format': 'wav',
                    'quality': 'high',
                },
                'fallback_settings': {
                    'max_retries': 3,
                    'retry_delay': 1.0,
                    'quality_threshold': 0.7,
                },
            }
        try:
            with open(VOICE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error('Error loading voice_config.json: %s', e)
            return {'engine_order': ['kokoro'], 'characters': {}}

    def _save_voice_config(self, cfg: Dict[str, Any]) -> None:
        VOICE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(VOICE_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        logger.info('Updated %s', VOICE_CONFIG_PATH)

    def _sync_voice_config_entry(
        self,
        display_name: str,
        speaker_wav: str,
        language: str,
    ) -> None:
        """Ensure ``voice_config.json`` has a character key for Kokoro."""
        cfg = self._load_voice_config()
        chars = cfg.setdefault('characters', {})
        key = slug_character(display_name)
        rel = str(Path(speaker_wav))
        try:
            rel = str(Path(speaker_wav).resolve().relative_to(Path.cwd()))
        except ValueError:
            pass
        entry: Dict[str, Any] = {
            'speaker_wav': rel.replace('\\', '/'),
            'language': language,
        }
        if key in chars and isinstance(chars[key], dict):
            old = chars[key]
            for k, v in old.items():
                if k not in ('speaker_wav', 'language'):
                    entry[k] = v
        chars[key] = entry
        cfg.setdefault('engine_order', ['kokoro'])
        self._save_voice_config(cfg)

    def _remove_voice_config_for_entry(self, entry: Dict[str, Any]) -> None:
        if not VOICE_CONFIG_PATH.exists():
            return
        cfg = self._load_voice_config()
        chars = cfg.get('characters') or {}
        key = slug_character(entry.get('name', ''))
        if key in chars:
            del chars[key]
            cfg['characters'] = chars
            self._save_voice_config(cfg)

    # ── Core CRUD ─────────────────────────────────────────────────────────

    def register_voice(self, voice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a character voice.

        Required: ``name``, ``speaker_wav`` (path to mono 16 kHz WAV).

        Optional: ``language`` (default ``en``), ``description``,
        ``character_bio``.
        """
        name = voice_data.get('name', '').strip()
        speaker_wav = (
            voice_data.get('speaker_wav') or voice_data.get('voice_id') or ''
        ).strip()

        if not name:
            return {'error': 'Missing required field: name'}
        if not speaker_wav:
            return {
                'error': 'Missing required field: speaker_wav '
                '(WAV path; legacy voice_id is not supported).',
            }

        wav_path = Path(speaker_wav)
        if not wav_path.exists():
            return {
                'error': (
                    f'speaker_wav not found: {speaker_wav}\n'
                    f'Place a mono 16 kHz WAV at that path and retry.'
                ),
            }
        if wav_path.suffix.lower() != '.wav':
            return {
                'error': f'speaker_wav must be a .wav file, got: {wav_path.suffix}',
            }

        voice_registry_id = voice_data.get(
            'voice_registry_id',
            f'voice_{uuid.uuid4().hex[:8]}',
        )
        language = voice_data.get('language') or 'en'

        entry: Dict[str, Any] = {
            'voice_registry_id': voice_registry_id,
            'name': name,
            'speaker_wav': str(wav_path.resolve()),
            'language': language,
            'description': voice_data.get('description') or '',
            'character_bio': voice_data.get('character_bio') or '',
            'created_at': time.time(),
            'updated_at': time.time(),
        }

        self.registry[voice_registry_id] = entry
        self._save_registry()
        self._sync_voice_config_entry(name, entry['speaker_wav'], language)
        self._add_voice_to_memory(entry)

        logger.info('Registered voice: %s → %s', name, speaker_wav)
        return entry

    def get_voice(self, identifier: str) -> Optional[Dict[str, Any]]:
        if identifier in self.registry:
            return self.registry[identifier]
        for entry in self.registry.values():
            if entry.get('name', '').lower() == identifier.lower():
                return entry
        return None

    def update_voice(
        self,
        voice_registry_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        if voice_registry_id not in self.registry:
            return {'error': f'Voice not found: {voice_registry_id}'}

        entry = self.registry[voice_registry_id].copy()
        for key, value in updates.items():
            if key != 'voice_registry_id':
                entry[key] = value
        entry['updated_at'] = time.time()

        if 'speaker_wav' in updates:
            wav_path = Path(updates['speaker_wav'])
            if not wav_path.exists():
                return {
                    'error': f"Updated speaker_wav not found: {updates['speaker_wav']}",
                }

        self.registry[voice_registry_id] = entry
        self._save_registry()
        if 'speaker_wav' in updates or 'language' in updates or 'name' in updates:
            self._sync_voice_config_entry(
                entry.get('name', ''),
                entry.get('speaker_wav', ''),
                entry.get('language', 'en'),
            )
        self._add_voice_to_memory(entry)
        return entry

    def delete_voice(self, voice_registry_id: str) -> Dict[str, Any]:
        if voice_registry_id not in self.registry:
            return {'error': f'Voice not found: {voice_registry_id}', 'success': False}
        deleted = self.registry.pop(voice_registry_id)
        self._save_registry()
        self._remove_voice_config_for_entry(deleted)
        return {'success': True, 'deleted': deleted}

    def list_voices(self) -> List[Dict[str, Any]]:
        return list(self.registry.values())

    def create_voice_from_description(
        self,
        name: str,
        description: str,
    ) -> Dict[str, Any]:
        """Not supported without cloud voice cloning — use ``register_voice``."""
        return {
            'error': (
                'Kokoro-only registry: record a reference WAV and run '
                'register_voice with speaker_wav=path. '
                f'(Requested: {name!r})'
            ),
        }

    # ── Speech generation (Kokoro) ────────────────────────────────────────

    def generate_speech(
        self,
        text: str,
        voice_identifier: str,
        output_path: str,
        language: Optional[str] = None,
    ) -> None:
        from tts_engine import get_kokoro_engine, SynthError

        voice_data = self.get_voice(voice_identifier)
        if not voice_data:
            raise ValueError(
                f'Voice not found: {voice_identifier}\n'
                f'Register with: python main.py register-voice',
            )

        speaker_wav = voice_data['speaker_wav']
        lang = language or voice_data.get('language', 'en')

        if not Path(speaker_wav).exists():
            raise RuntimeError(
                f"speaker_wav missing for '{voice_data['name']}': {speaker_wav}",
            )

        try:
            engine = get_kokoro_engine()
            engine.synth(
                text=text,
                speaker_wav=speaker_wav,
                language=lang,
                output_path=output_path,
            )
        except SynthError as e:
            raise RuntimeError(
                f"Kokoro synthesis failed for '{voice_data['name']}': {e}",
            ) from e

    # ── Voice health / validation ─────────────────────────────────────────

    def check_voice_health(self, voice_registry_id: str) -> Dict[str, Any]:
        voice_data = self.get_voice(voice_registry_id)
        if not voice_data:
            return {
                'status': 'error',
                'message': f'Not found in registry: {voice_registry_id}',
            }

        wav_path = Path(voice_data.get('speaker_wav', ''))
        if not wav_path.exists():
            return {
                'status': 'missing',
                'message': f'speaker_wav not found: {wav_path}',
                'fix': f'Place WAV at {wav_path} or re-register.',
            }

        size_kb = wav_path.stat().st_size // 1024
        return {
            'status': 'healthy',
            'message': f'WAV exists ({size_kb} KB): {wav_path}',
            'name': voice_data['name'],
        }

    def check_all_voices_health(self) -> Dict[str, Dict[str, Any]]:
        return {vid: self.check_voice_health(vid) for vid in self.registry}

    def smoke_test_voice(self, voice_identifier: str) -> Dict[str, Any]:
        voice_data = self.get_voice(voice_identifier)
        if not voice_data:
            return {'success': False, 'error': f'Voice not found: {voice_identifier}'}

        slug = slug_character(voice_data['name'])[:40]
        out = str(self.voices_dir / f'smoke_test_{slug}.wav')
        test_text = 'This is a voice test for Stardock Podium.'

        try:
            self.generate_speech(test_text, voice_identifier, out)
            size_kb = Path(out).stat().st_size // 1024
            return {
                'success': True,
                'output': out,
                'size_kb': size_kb,
                'message': f'Smoke test passed — {size_kb} KB written to {out}',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ── Character → voice mapping ─────────────────────────────────────────

    def map_characters_to_voices(
        self,
        characters: List[Dict[str, Any]],
    ) -> Dict[str, str]:
        """
        Map character names to voice registry IDs.

        Only includes characters that have a registered voice so
        ``audio_pipeline`` can treat an empty dict as “no mappings” and apply
        its name-based fallback.
        """
        mapping: Dict[str, str] = {}

        for char in characters:
            name = char.get('name', '').strip()
            if not name:
                continue
            voice = self.get_voice(name)
            if voice:
                mapping[name] = voice['voice_registry_id']
            else:
                logger.warning(
                    "No voice registered for character '%s'. "
                    'python main.py register-voice \"%s\" voices/samples/%s.wav',
                    name,
                    name,
                    slug_character(name),
                )
        return mapping

    def get_missing_voices(self, characters: List[Dict[str, Any]]) -> List[str]:
        """Character names with no registry entry (by display name)."""
        missing: List[str] = []
        for char in characters:
            name = char.get('name', '').strip()
            if not name:
                continue
            if not self.get_voice(name):
                missing.append(name)
        return missing

    # ── Mem0 ──────────────────────────────────────────────────────────────

    def _add_voice_to_memory(self, entry: Dict[str, Any]) -> None:
        try:
            content = (
                f"Voice Registry — Character: {entry.get('name', '')}\n"
                f"WAV: {entry.get('speaker_wav', '')}\n"
                f"Description: {entry.get('description', '')}\n"
                f"Bio: {entry.get('character_bio', '')}"
            )
            self.mem0_client.add_memory(
                content=content,
                user_id='voice_registry',
                memory_type=self.mem0_client.VOICE_METADATA,
                metadata={
                    'voice_registry_id': entry.get('voice_registry_id'),
                    'name': entry.get('name'),
                    'speaker_wav': entry.get('speaker_wav'),
                },
            )
        except Exception as e:
            logger.warning('Could not add voice to Mem0 (non-critical): %s', e)

    def find_voices_by_description(
        self,
        description: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        try:
            results = self.mem0_client.search_memory(
                query=description,
                user_id='voice_registry',
                memory_type=self.mem0_client.VOICE_METADATA,
                limit=limit,
            )
        except Exception as e:
            logger.warning('Voice memory search failed: %s', e)
            return []
        voices: List[Dict[str, Any]] = []
        for r in results:
            vid = r.get('metadata', {}).get('voice_registry_id')
            if vid and vid in self.registry:
                voices.append(self.registry[vid])
        return voices


_voice_registry: Optional[VoiceRegistry] = None


def get_voice_registry() -> VoiceRegistry:
    global _voice_registry
    if _voice_registry is None:
        _voice_registry = VoiceRegistry()
    return _voice_registry


def register_voice(voice_data: Dict[str, Any]) -> Dict[str, Any]:
    return get_voice_registry().register_voice(voice_data)


def get_voice(identifier: str) -> Optional[Dict[str, Any]]:
    return get_voice_registry().get_voice(identifier)


def list_voices() -> List[Dict[str, Any]]:
    return get_voice_registry().list_voices()


def generate_speech(
    text: str,
    voice_identifier: str,
    output_path: str,
    language: Optional[str] = None,
) -> None:
    get_voice_registry().generate_speech(
        text, voice_identifier, output_path, language,
    )


def create_voice_from_description(name: str, description: str) -> Dict[str, Any]:
    return get_voice_registry().create_voice_from_description(name, description)


def map_characters_to_voices(characters: List[Dict[str, Any]]) -> Dict[str, str]:
    return get_voice_registry().map_characters_to_voices(characters)
