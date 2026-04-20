#!/usr/bin/env python
"""
TTS Engine Module for Stardock Podium.

Kokoro v0.9+ (``KPipeline``) is the primary engine; weights are downloaded
automatically from HuggingFace on first use.  ElevenLabs is kept importable
as a deprecated legacy path.
"""

import os
import logging
import abc
import threading
import typing as t
import warnings
from pathlib import Path

import torch
import numpy as np

try:
    import soundfile as sf
except ImportError:
    sf = None

try:
    from kokoro import KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    KPipeline = None
    KOKORO_AVAILABLE = False

try:
    from elevenlabs import ElevenLabs, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
except ImportError:
    ElevenLabs = None
    VoiceSettings = None
    ElevenLabsClient = None

logger = logging.getLogger(__name__)

_KOKORO_SAMPLE_RATE = 24000


class SynthError(Exception):
    """Exception raised for TTS synthesis errors."""
    pass


class TTSEngine(abc.ABC):
    """Abstract base class for TTS engines."""

    @abc.abstractmethod
    def synth(
        self,
        text: str,
        speaker_wav: str,
        language: str,
        output_path: str,
    ) -> None:
        """Synthesize speech from text.

        Args:
            text: Text to synthesize.
            speaker_wav: Path to speaker reference audio (or voice name).
            language: Language code (e.g. ``'a'`` for American English).
            output_path: Path to write the output WAV.

        Raises:
            SynthError: If synthesis fails.
        """
        pass


class KokoroEngine(TTSEngine):
    """Kokoro v0.9+ TTS engine (auto-downloads weights via KPipeline)."""

    def __init__(self) -> None:
        if not KOKORO_AVAILABLE:
            raise ImportError(
                'Kokoro TTS is not available. '
                'Install with: pip install kokoro>=0.9.2'
            )
        if sf is None:
            raise ImportError(
                'soundfile is required for WAV output. '
                'Install with: pip install soundfile'
            )
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        if device == 'cpu':
            logger.warning(
                'CUDA not available — Kokoro running on CPU. '
                'Generation will be slow.'
            )
        else:
            logger.info(
                'Kokoro using GPU: %s',
                torch.cuda.get_device_name(0),
            )

        # Cloud-friendly: honor KOKORO_MODEL_PATH for legacy/symlink setups
        # (the RunPod setup script symlinks weights from /workspace/models/
        # into the repo root so they survive pod shutdowns). KPipeline v0.9+
        # auto-downloads from HuggingFace, but if a user has pointed
        # KOKORO_MODEL_PATH at a persistent file we log it for visibility
        # and, when HF_HOME is unset, redirect the HuggingFace cache to the
        # weight file's parent directory so the download persists on the
        # same volume.
        model_path_env = os.environ.get('KOKORO_MODEL_PATH')
        if model_path_env:
            model_path = Path(model_path_env)
            if model_path.exists():
                logger.info(
                    'KOKORO_MODEL_PATH set and present: %s', model_path,
                )
                if not os.environ.get('HF_HOME'):
                    cache_root = model_path.parent / 'hf_cache'
                    cache_root.mkdir(parents=True, exist_ok=True)
                    os.environ['HF_HOME'] = str(cache_root)
                    logger.info(
                        'HF_HOME unset — persisting Kokoro HF cache to %s',
                        cache_root,
                    )
            else:
                logger.warning(
                    'KOKORO_MODEL_PATH=%s does not exist; Kokoro will '
                    'auto-download weights from HuggingFace on first use.',
                    model_path,
                )

        self._pipeline = KPipeline(lang_code='a', device=device)
        self._device = device
        # KPipeline is not thread-safe — serialize calls when the audio
        # pipeline fans out across a ThreadPoolExecutor so GPU state and
        # the output numpy buffers don't get clobbered between threads.
        self._synth_lock = threading.Lock()
        logger.info('Kokoro TTS engine loaded (KPipeline, device=%s).', device)

    def synth(
        self,
        text: str,
        speaker_wav: str,
        language: str,
        output_path: str,
    ) -> None:
        """Synthesize speech using Kokoro KPipeline.

        ``speaker_wav`` is treated as a **Kokoro voice name** (e.g.
        ``'af_heart'``). If it looks like a file path (ends in ``.wav``) and
        Kokoro's ``load_single_voice`` accepts it, we try that first; otherwise
        fall back to the default voice ``'af_heart'``.
        """
        try:
            voice = self._resolve_voice(speaker_wav)
            with self._synth_lock:
                chunks = list(self._pipeline(text, voice=voice, speed=1.0))
                if not chunks:
                    raise SynthError(f'Kokoro returned no audio for: {text[:80]}')
                audio = np.concatenate(
                    [c.audio for c in chunks if c.audio is not None]
                )
                sf.write(output_path, audio, _KOKORO_SAMPLE_RATE)
            logger.info('Kokoro TTS synthesis complete: %s', output_path)
        except SynthError:
            raise
        except Exception as e:
            logger.error('Kokoro TTS synthesis failed: %s', e)
            raise SynthError(str(e))

    def _resolve_voice(self, speaker_wav: str) -> str:
        """Map a speaker_wav string to a Kokoro voice identifier.

        If the value is a .wav path, try to load it as a custom voice.
        Otherwise treat it as a built-in voice name.
        """
        if speaker_wav and speaker_wav.lower().endswith('.wav'):
            p = Path(speaker_wav)
            if p.exists():
                try:
                    self._pipeline.load_single_voice(str(p))
                    return str(p)
                except Exception:
                    logger.warning(
                        'Could not load custom voice %s, using default.',
                        speaker_wav,
                    )
            return 'af_heart'
        return speaker_wav or 'af_heart'


class ElevenLabsEngine(TTSEngine):
    """ElevenLabs TTS engine implementation (deprecated)."""

    def __init__(self) -> None:
        warnings.warn(
            'ElevenLabsEngine is deprecated; Kokoro is the default engine. '
            'This path is retained only for legacy scripts.',
            DeprecationWarning,
            stacklevel=2,
        )
        self.api_key = os.getenv('ELEVENLABS_API_KEY')
        if not self.api_key:
            logger.warning('ELEVENLABS_API_KEY not found in environment variables')
            self.elevenlabs = None
        else:
            try:
                self.elevenlabs = ElevenLabs(api_key=self.api_key)
                logger.info('ElevenLabs engine loaded.')
            except Exception as e:
                logger.error('Failed to initialize ElevenLabs: %s', e)
                self.elevenlabs = None

    def synth(
        self,
        text: str,
        speaker_wav: str,
        language: str,
        output_path: str,
    ) -> None:
        if not self.elevenlabs:
            raise SynthError('ElevenLabs client not initialized (no API key)')
        try:
            audio_data = self.elevenlabs.text_to_speech.convert(
                voice_id=speaker_wav,
                text=text,
                model_id='eleven_multilingual_v2',
            )
            if hasattr(audio_data, '__iter__') and not isinstance(audio_data, bytes):
                audio_data = b''.join(chunk for chunk in audio_data)
            with open(output_path, 'wb') as f:
                if isinstance(audio_data, bytes):
                    f.write(audio_data)
                else:
                    f.write(
                        audio_data.read()
                        if hasattr(audio_data, 'read')
                        else bytes(audio_data)
                    )
            logger.info('ElevenLabs synthesis complete: %s', output_path)
        except Exception as e:
            logger.error('ElevenLabs synthesis failed: %s', e)
            raise SynthError(str(e))


# Singleton instances
_kokoro_engine: t.Optional[KokoroEngine] = None
_elevenlabs_engine: t.Optional[ElevenLabsEngine] = None


def get_kokoro_engine() -> KokoroEngine:
    """Get the KokoroEngine singleton instance."""
    global _kokoro_engine
    if _kokoro_engine is None:
        if not KOKORO_AVAILABLE:
            raise ImportError(
                'Kokoro TTS is not available. '
                'Install with: pip install kokoro>=0.9.2'
            )
        _kokoro_engine = KokoroEngine()
    return _kokoro_engine


def get_elevenlabs_engine() -> ElevenLabsEngine:
    """Get the ElevenLabsEngine singleton instance."""
    global _elevenlabs_engine
    if ElevenLabs is None or ElevenLabsClient is None:
        raise ImportError(
            'elevenlabs package is not installed. pip install elevenlabs'
        )
    if _elevenlabs_engine is None:
        _elevenlabs_engine = ElevenLabsEngine()
    return _elevenlabs_engine
