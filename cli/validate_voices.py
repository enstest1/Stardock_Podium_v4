#!/usr/bin/env python3
"""
Voice Configuration Validator for Stardock Podium.

This script validates voice configurations and samples for Kokoro TTS
with ElevenLabs fallback.
"""

import os
import sys
import json
import logging
import argparse
import soundfile as sf
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def validate_audio_file(file_path: str) -> bool:
    """Validate audio file format and requirements.
    
    Args:
        file_path: Path to audio file
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"Audio file not found: {file_path}")
            return False

        # Load audio file
        data, samplerate = sf.read(file_path)
        
        # Check channels (must be mono)
        if len(data.shape) > 1 and data.shape[1] > 1:
            logger.error(f"Audio file must be mono: {file_path}")
            return False
        
        # Check sample rate (must be 16kHz)
        if samplerate != 16000:
            logger.error(f"Audio file must be 16kHz: {file_path}")
            return False
        
        # Check duration (must be 5-10 seconds)
        duration = len(data) / samplerate
        if duration < 5 or duration > 10:
            logger.error(f"Audio file must be 5-10 seconds: {file_path} ({duration:.1f}s)")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Error validating audio file {file_path}: {str(e)}")
        return False

def validate_voice_config(config_path: str) -> bool:
    """Validate the voice configuration file.
    
    Args:
        config_path: Path to voice configuration file
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Check if file exists
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return False

        # Load and validate JSON
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Validate required sections
        required_sections = ['engine_order', 'characters']
        for section in required_sections:
            if section not in config:
                logger.error(f"Missing required section: {section}")
                return False

        # Validate engine order
        if not isinstance(config['engine_order'], list) or len(config['engine_order']) < 1:
            logger.error("engine_order must be a non-empty list")
            return False

        # Validate characters
        if not isinstance(config['characters'], dict) or len(config['characters']) < 1:
            logger.error("characters must be a non-empty dictionary")
            return False

        # Validate each character configuration
        for char_name, char_config in config['characters'].items():
            # Check required fields
            required_fields = ['speaker_wav', 'language']
            for field in required_fields:
                if field not in char_config:
                    logger.error(f"Missing {field} for character: {char_name}")
                    return False

            # Validate speaker WAV
            if not validate_audio_file(char_config['speaker_wav']):
                return False

            # Validate language
            if not isinstance(char_config['language'], str):
                logger.error(f"Language must be a string for character: {char_name}")
                return False

            # Check ElevenLabs ID if eleven is in engine_order
            if 'eleven' in config['engine_order']:
                if 'eleven_id' not in char_config:
                    logger.error(f"Missing eleven_id for character: {char_name}")
                    return False

        return True
    except Exception as e:
        logger.error(f"Error validating config: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Validate voice configuration and samples')
    parser.add_argument('--config', default='voices/voice_config.json', help='Path to voice configuration file')
    args = parser.parse_args()

    if validate_voice_config(args.config):
        logger.info("Voice configuration is valid")
        return 0
    else:
        logger.error("Voice configuration validation failed")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 