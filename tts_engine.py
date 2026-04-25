#!/usr/bin/env python
"""
TTS Engine Module for Stardock Podium.

Kokoro v0.9+ (``KPipeline``) is the primary engine; weights are downloaded
automatically from HuggingFace on first use.  ElevenLabs is kept importable
as a deprecated legacy path.
"""

import os
import inspect
import logging
import abc
import threading
import tempfile
import typing as t
import warnings
from pathlib import Path

from tts_pronunciation import normalize_trek_tts_text

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
    from TTS.api import TTS as CoquiTTS  # type: ignore
    XTTS_AVAILABLE = True
except ImportError:
    CoquiTTS = None
    XTTS_AVAILABLE = False

try:
    from elevenlabs import ElevenLabs, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
except ImportError:
    ElevenLabs = None
    VoiceSettings = None
    ElevenLabsClient = None

logger = logging.getLogger(__name__)

_KOKORO_SAMPLE_RATE = 24000

# ---------------------------------------------------------------------------
# Kokoro tail-chirp cleanup
# ---------------------------------------------------------------------------
# KPipeline frequently emits a short end-of-sequence artifact (a high-freq
# "chirp" / click) when the model transitions to silence. misaki — the
# phonemizer — also mis-handles trailing em-dashes and ellipses, producing
# stray phonemes right before that transition. The two combined make every
# utterance end in an audible artifact.
#
# The cheapest reliable fix is to trim the tail by energy and apply short
# head/tail fades. All numbers below are conservative so we don't chew into
# real speech.
#
# Override via env on noisy material (e.g. RunPod): KOKORO_TAIL_FADE_MS=55
# KOKORO_EXTRA_TAIL_TRIM_MS=12 nibbles a few ms after energy trim.
def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning('Invalid %s=%r — using default %s', name, raw, default)
        return default


_TAIL_FADE_MS = _env_float('KOKORO_TAIL_FADE_MS', 45.0)  # linear fade-out (was 25; longer kills HF chirp)
_HEAD_FADE_MS = _env_float('KOKORO_HEAD_FADE_MS', 5.0)
_TAIL_KEEP_MS = _env_float('KOKORO_TAIL_KEEP_MS', 32.0)   # release after last speech (was 40)
_SILENCE_WIN_MS = _env_float('KOKORO_SILENCE_WIN_MS', 10.0)
_SILENCE_DBFS = _env_float('KOKORO_SILENCE_DBFS', -45.0)
_EXTRA_TAIL_TRIM_MS = _env_float('KOKORO_EXTRA_TAIL_TRIM_MS', 0.0)  # optional hard nibble from tail


def _clean_kokoro_text(text: str) -> str:
    """Normalize text so misaki doesn't phonemize trailing junk into clicks.

    Strips trailing em/en dashes and ellipses, then ensures the line ends
    with a terminal punctuation mark so Kokoro's release phase is clean.
    Intentionally conservative — we only touch trailing characters.
    """
    if not text:
        return text
    cleaned = text.strip()
    # Drop trailing dashes / ellipses which misaki tends to turn into chirps.
    trailing = {'-', '\u2013', '\u2014', '\u2026'}  # - – — …
    while cleaned and (cleaned[-1] in trailing or cleaned.endswith('...')):
        if cleaned.endswith('...'):
            cleaned = cleaned[:-3].rstrip()
        else:
            cleaned = cleaned[:-1].rstrip()
    if cleaned and cleaned[-1] not in '.!?;:"\')]':
        cleaned += '.'
    return cleaned or text


def _clean_kokoro_audio(audio: np.ndarray, sr: int) -> np.ndarray:
    """Trim Kokoro end-chirp artifact and apply short head/tail fades."""
    if audio is None or audio.size == 0:
        return audio

    x = np.asarray(audio, dtype=np.float32).reshape(-1).copy()
    # Remove DC offset so concat / MP3 encode boundaries don't click or buzz.
    x -= float(np.mean(x))
    n = x.shape[0]

    win = max(1, int(sr * _SILENCE_WIN_MS / 1000))
    threshold = 10.0 ** (_SILENCE_DBFS / 20.0)

    last_speech = 0
    i = n
    while i > 0:
        j = max(0, i - win)
        window = x[j:i]
        rms = float(np.sqrt(np.mean(window * window))) if window.size else 0.0
        if rms > threshold:
            last_speech = i
            break
        i = j

    if last_speech > 0:
        keep = int(sr * _TAIL_KEEP_MS / 1000)
        trim_end = min(n, last_speech + keep)
        x = x[:trim_end]

    extra = int(sr * _EXTRA_TAIL_TRIM_MS / 1000)
    if extra > 0 and x.shape[0] > extra + int(0.01 * sr):
        x = x[:-extra]

    fade_out = min(int(sr * _TAIL_FADE_MS / 1000), x.shape[0])
    if fade_out > 0:
        ramp = np.linspace(1.0, 0.0, fade_out, dtype=np.float32)
        x[-fade_out:] *= ramp

    fade_in = min(int(sr * _HEAD_FADE_MS / 1000), x.shape[0])
    if fade_in > 0:
        ramp = np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
        x[:fade_in] *= ramp

    return x


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
            clean_text = _clean_kokoro_text(normalize_trek_tts_text(text))
            with self._synth_lock:
                chunks = list(self._pipeline(clean_text, voice=voice, speed=1.0))
                if not chunks:
                    raise SynthError(f'Kokoro returned no audio for: {text[:80]}')
                # Clean each chunk *before* concatenation so Kokoro's
                # per-chunk end-of-sequence chirps get trimmed at each seam,
                # not just at the very end of the full utterance.
                parts: list[np.ndarray] = []
                for c in chunks:
                    if c.audio is None:
                        continue
                    arr = c.audio
                    if hasattr(arr, 'cpu'):
                        arr = arr.cpu().numpy()
                    arr = np.asarray(arr, dtype=np.float32).reshape(-1)
                    arr = _clean_kokoro_audio(arr, _KOKORO_SAMPLE_RATE)
                    if arr.size:
                        parts.append(arr)
                if not parts:
                    raise SynthError(f'Kokoro returned no audio for: {text[:80]}')
                audio = np.concatenate(parts)
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
                except Exception as e:
                    logger.error(
                        'Kokoro rejected WAV reference %s (%s) — falling '
                        "back to 'af_heart'. Kokoro v0.9+ needs a built-in "
                        'voice name (e.g. am_michael, bm_george) or a .pt '
                        'voice tensor, NOT a raw .wav. Set kokoro_voice in '
                        'voice_config.json to avoid this.',
                        speaker_wav, e,
                    )
            else:
                logger.error(
                    'speaker_wav %s not found on disk — falling back to '
                    "'af_heart'.", speaker_wav,
                )
            return 'af_heart'
        return speaker_wav or 'af_heart'


_XTTS_MODEL = os.environ.get(
    'STARDOCK_XTTS_MODEL',
    'tts_models/multilingual/multi-dataset/xtts_v2',
)

# PyTorch 2.6+ defaults ``torch.load(..., weights_only=True)``; Coqui XTTS
# checkpoints need full unpickling. Patch once for the Coqui TTS import path.
_torch_load_patched = False


def _patch_torch_load_for_coqui() -> None:
    global _torch_load_patched
    if _torch_load_patched:
        return
    _torch_load_patched = True
    _orig = torch.load

    def _load(*args: t.Any, **kwargs: t.Any) -> t.Any:
        try:
            if (
                "weights_only" in inspect.signature(_orig).parameters
                and "weights_only" not in kwargs
            ):
                kwargs["weights_only"] = False
        except (TypeError, ValueError):
            pass
        return _orig(*args, **kwargs)

    torch.load = _load  # type: ignore[assignment]


class XTTSEngine(TTSEngine):
    """Coqui XTTS v2 — clones timbre from a reference ``speaker_wav`` file.

    Install optional deps: ``pip install -r requirements-voice-clone.txt``.
    First run downloads model weights (large). Use a GPU on RunPod when
    possible — CPU is very slow.
    """

    def __init__(self) -> None:
        if not XTTS_AVAILABLE or CoquiTTS is None:
            raise ImportError(
                'Coqui TTS (XTTS) is not installed. '
                'Use: pip install -r requirements-voice-clone.txt'
            )
        # Coqui reads CPML terms from stdin; nohup/SSH get EOF and XTTS never loads.
        if not (os.environ.get('COQUI_TOS_AGREED') or '').strip():
            os.environ['COQUI_TOS_AGREED'] = '1'

        _patch_torch_load_for_coqui()

        use_gpu = torch.cuda.is_available()
        self._device = 'cuda' if use_gpu else 'cpu'
        if not use_gpu:
            logger.warning(
                'CUDA not available — XTTS on CPU is extremely slow.',
            )
        try:
            self._tts = CoquiTTS(
                model_name=_XTTS_MODEL,
                progress_bar=False,
                gpu=use_gpu,
            )
        except TypeError:
            # Older Coqui API
            self._tts = CoquiTTS(_XTTS_MODEL, gpu=use_gpu)

        self._synth_lock = threading.Lock()
        logger.info(
            'XTTS engine loaded (model=%s, device=%s).',
            _XTTS_MODEL,
            self._device,
        )

    def synth(
        self,
        text: str,
        speaker_wav: str,
        language: str,
        output_path: str,
    ) -> None:
        """Synthesize with a reference WAV path (not a Kokoro voice id)."""
        ref = Path(speaker_wav)
        if not ref.is_file():
            raise SynthError(f'XTTS reference WAV not found: {speaker_wav}')

        lang = (language or 'en').strip().lower()
        if len(lang) > 2:
            lang = lang[:2]
        clean_text = _clean_kokoro_text(normalize_trek_tts_text(text))
        if not clean_text:
            raise SynthError('Empty text after normalization')

        ref_path = str(ref.resolve())
        tmp_spk: t.Optional[str] = None
        if ref.suffix.lower() == '.mp3':
            try:
                import librosa
            except ImportError as e:
                raise SynthError(
                    'MP3 speaker reference requires librosa '
                    '(pip install librosa).'
                ) from e
            if sf is None:
                raise SynthError('soundfile required to stage MP3 for XTTS.')
            y, _sr = librosa.load(str(ref), sr=24000, mono=True)
            fd, tmp_spk = tempfile.mkstemp(suffix='.wav', prefix='xtts_spk_')
            os.close(fd)
            sf.write(tmp_spk, y, 24000)
            ref_path = tmp_spk

        try:
            with self._synth_lock:
                self._tts.tts_to_file(  # type: ignore[union-attr]
                    text=clean_text,
                    file_path=output_path,
                    speaker_wav=ref_path,
                    language=lang,
                )
            logger.info('XTTS synthesis complete: %s', output_path)
        except SynthError:
            raise
        except Exception as e:
            logger.error('XTTS synthesis failed: %s', e)
            raise SynthError(str(e)) from e
        finally:
            if tmp_spk and os.path.isfile(tmp_spk):
                try:
                    os.unlink(tmp_spk)
                except OSError:
                    pass


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
_xtts_engine: t.Optional[XTTSEngine] = None
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


def get_xtts_engine() -> XTTSEngine:
    """Get the XTTSEngine singleton (lazy; loads weights on first use)."""
    global _xtts_engine
    if _xtts_engine is None:
        _xtts_engine = XTTSEngine()
    return _xtts_engine


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
