#!/usr/bin/env python3
"""
Voice Configuration Validator for Stardock Podium.

Validates ``voice_config.json`` and the referenced speaker WAVs for
Kokoro TTS. The ElevenLabs ``eleven_id`` requirement has been removed —
Kokoro is the sole supported engine.

WAV requirements (Kokoro):
    * Mono (1 channel)
    * 16 kHz sample rate
    * Duration between 4 and 20 seconds
      (6–15 s recommended — outside that range we warn but don't fail)
"""

import os
import sys
import json
import logging
import argparse
import soundfile as sf

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MIN_DURATION_S = 4.0
MAX_DURATION_S = 20.0
RECOMMENDED_MIN_S = 6.0
RECOMMENDED_MAX_S = 15.0


def validate_audio_file(file_path: str) -> bool:
    """Validate one speaker reference WAV.

    Args:
        file_path: Path to audio file.

    Returns:
        True if hard requirements pass (existence, mono, 16 kHz, 4–20 s).
        Emits a warning — but returns True — for durations outside the
        recommended 6–15 s window.
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False

        data, samplerate = sf.read(file_path)

        if len(data.shape) > 1 and data.shape[1] > 1:
            logger.error(f"Audio file must be mono: {file_path}")
            return False

        if samplerate != 16000:
            logger.error(
                f"Audio file must be 16 kHz (got {samplerate}): {file_path}")
            return False

        duration = len(data) / samplerate
        if duration < MIN_DURATION_S or duration > MAX_DURATION_S:
            logger.error(
                f"Audio file must be {MIN_DURATION_S:.0f}-"
                f"{MAX_DURATION_S:.0f} seconds (got {duration:.1f}s): "
                f"{file_path}"
            )
            return False

        if (duration < RECOMMENDED_MIN_S
                or duration > RECOMMENDED_MAX_S):
            logger.warning(
                f"Duration {duration:.1f}s is outside the recommended "
                f"{RECOMMENDED_MIN_S:.0f}-{RECOMMENDED_MAX_S:.0f}s "
                f"window (Kokoro quality may vary): {file_path}"
            )

        return True
    except Exception as e:
        logger.error(f"Error validating audio file {file_path}: {e}")
        return False


def validate_voice_config(config_path: str) -> bool:
    """Validate ``voice_config.json`` structure and its referenced WAVs."""
    try:
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return False

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        required_sections = ['engine_order', 'characters']
        for section in required_sections:
            if section not in config:
                logger.error(f"Missing required section: {section}")
                return False

        engine_order = config['engine_order']
        if not isinstance(engine_order, list) or len(engine_order) < 1:
            logger.error("engine_order must be a non-empty list")
            return False

        if 'kokoro' not in engine_order:
            logger.error(
                "engine_order must contain 'kokoro' (the only supported "
                "engine). Got: %s", engine_order)
            return False

        deprecated = [e for e in engine_order if e != 'kokoro']
        if deprecated:
            logger.warning(
                "engine_order contains deprecated engines %s — these will "
                "be ignored at runtime.", deprecated)

        if (not isinstance(config['characters'], dict)
                or len(config['characters']) < 1):
            logger.error("characters must be a non-empty dictionary")
            return False

        for char_name, char_config in config['characters'].items():
            required_fields = ['speaker_wav', 'language']
            for field in required_fields:
                if field not in char_config:
                    logger.error(
                        f"Missing {field} for character: {char_name}")
                    return False

            if not validate_audio_file(char_config['speaker_wav']):
                return False

            if not isinstance(char_config['language'], str):
                logger.error(
                    f"Language must be a string for character: {char_name}")
                return False

        return True
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Validate voice configuration and samples')
    parser.add_argument(
        '--config', default='voices/voice_config.json',
        help='Path to voice configuration file')
    args = parser.parse_args()

    if validate_voice_config(args.config):
        logger.info("Voice configuration is valid")
        return 0
    logger.error("Voice configuration validation failed")
    return 1


if __name__ == '__main__':
    sys.exit(main())
