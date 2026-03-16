#!/usr/bin/env python
"""
TTS Engine Module for Stardock Podium.

This module provides a unified interface for text-to-speech engines,
currently supporting Kokoro TTS as primary and ElevenLabs as fallback.
"""

import os
import logging
import abc
import typing as t

# Try to import ElevenLabs
try:
    from elevenlabs import ElevenLabs, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
except ImportError:
    ElevenLabs = None
    VoiceSettings = None
    ElevenLabsClient = None

# Try to import Kokoro (optional - not needed for ElevenLabs-only)
try:
    import soundfile as sf
    import numpy as np
    from kokoro.inference import KokoroSynth
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False
    KokoroSynth = None
    sf = None
    np = None

logger = logging.getLogger(__name__)

class SynthError(Exception):
    """Exception raised for TTS synthesis errors."""
    pass

class TTSEngine(abc.ABC):
    """Abstract base class for TTS engines."""
    
    @abc.abstractmethod
    def synth(self, text: str, speaker_wav: str, language: str, output_path: str) -> None:
        """Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            speaker_wav: Path to speaker reference audio (if supported)
            language: Language code
            output_path: Optional path to save the audio file
        
        Returns:
            None
        
        Raises:
            SynthError: If synthesis fails
        """
        pass

class KokoroEngine(TTSEngine):
    """Kokoro TTS engine implementation."""
    
    def __init__(self):
        """Initialize the Kokoro TTS engine."""
        if not KOKORO_AVAILABLE:
            raise ImportError("Kokoro TTS is not available. Install with: pip install kokoro-tts")
        self.kok = KokoroSynth("kokoro-tts-base-ft.pt", device="cpu")
        logger.info("Kokoro TTS engine loaded.")
    
    def synth(self, text: str, speaker_wav: str, language: str, output_path: str) -> None:
        """Synthesize speech using Kokoro TTS.
        
        Args:
            text: Text to synthesize
            speaker_wav: Path to speaker reference audio
            language: Language code
            output_path: Optional path to save the audio file
        
        Returns:
            None
        
        Raises:
            SynthError: If synthesis fails
        """
        try:
            if not KOKORO_AVAILABLE or sf is None:
                raise ImportError("Kokoro TTS dependencies not available")
            wav = self.kok.tts(
                text,
                speaker_wav=speaker_wav,
                language=language
            )
            sf.write(output_path, wav, 16000)
            logger.info(f"Kokoro TTS synthesis complete: {output_path}")
        except Exception as e:
            logger.error(f"Kokoro TTS synthesis failed: {e}")
            raise SynthError(str(e))

class ElevenLabsEngine(TTSEngine):
    """ElevenLabs TTS engine implementation."""
    
    def __init__(self):
        """Initialize the ElevenLabs TTS engine."""
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
            self.elevenlabs = None
        else:
            try:
                self.elevenlabs = ElevenLabs(api_key=self.api_key)
                logger.info("ElevenLabs engine loaded.")
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs: {e}")
                self.elevenlabs = None
    
    def synth(self, text: str, speaker_wav: str, language: str, output_path: str) -> None:
        """Synthesize speech using ElevenLabs.
        
        Args:
            text: Text to synthesize
            speaker_wav: Voice ID for ElevenLabs
            language: Not used by ElevenLabs
            output_path: Path to save the audio file
        
        Returns:
            None
        
        Raises:
            SynthError: If synthesis fails
        """
        if not self.elevenlabs:
            raise SynthError("ElevenLabs client not initialized (no API key)")
        
        try:
            # speaker_wav should be the voice_id for ElevenLabs
            audio_data = self.elevenlabs.text_to_speech.convert(
                voice_id=speaker_wav,  # voice_id
                text=text,
                model_id="eleven_multilingual_v2"
            )
            
            # Convert generator to bytes if needed
            if hasattr(audio_data, '__iter__') and not isinstance(audio_data, bytes):
                audio_data = b''.join(chunk for chunk in audio_data)
            
            with open(output_path, "wb") as f:
                if isinstance(audio_data, bytes):
                    f.write(audio_data)
                else:
                    f.write(audio_data.read() if hasattr(audio_data, 'read') else bytes(audio_data))
            logger.info(f"ElevenLabs synthesis complete: {output_path}")
        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}")
            raise SynthError(str(e))

# Singleton instances
_kokoro_engine = None
_elevenlabs_engine = None

def get_kokoro_engine() -> KokoroEngine:
    """Get the KokoroEngine singleton instance."""
    global _kokoro_engine
    if _kokoro_engine is None:
        if not KOKORO_AVAILABLE:
            raise ImportError("Kokoro TTS is not available. Install with: pip install kokoro-tts")
        _kokoro_engine = KokoroEngine()
    return _kokoro_engine

def get_elevenlabs_engine() -> ElevenLabsEngine:
    """Get the ElevenLabsEngine singleton instance."""
    global _elevenlabs_engine
    if _elevenlabs_engine is None:
        _elevenlabs_engine = ElevenLabsEngine()
    return _elevenlabs_engine 