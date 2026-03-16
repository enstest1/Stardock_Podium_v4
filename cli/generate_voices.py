#!/usr/bin/env python3
"""
Voice Generation CLI for Stardock Podium.

This script generates voice audio for episode scripts using Kokoro TTS
with ElevenLabs as fallback.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
import torch
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_engine import get_kokoro_engine, get_elevenlabs_engine, SynthError

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TTSGenerator:
    def __init__(self, config_path: str):
        """Initialize TTS generator with configuration."""
        self.config = self._load_config(config_path)
        self.kokoro_engine = None
        self.elevenlabs_engine = None

    def _load_config(self, config_path: str) -> dict:
        """Load and validate voice configuration."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            raise

    def _initialize_engines(self, engine_type: str = None):
        """Initialize TTS engines if not already initialized.
        
        Args:
            engine_type: Specific engine to initialize ('kokoro' or 'eleven'), 
                        or None to initialize based on engine_order config
        """
        # Only initialize engines that are in engine_order
        engines_to_init = [engine_type] if engine_type else self.config.get('engine_order', [])
        
        if 'kokoro' in engines_to_init and self.kokoro_engine is None:
            try:
                self.kokoro_engine = get_kokoro_engine()
                logger.info("Kokoro TTS initialized successfully")
            except Exception as e:
                logger.warning(f"Kokoro TTS not available (will skip): {str(e)}")
                # Don't raise - allow fallback to other engines

        if 'eleven' in engines_to_init and self.elevenlabs_engine is None:
            try:
                self.elevenlabs_engine = get_elevenlabs_engine()
                logger.info("ElevenLabs engine initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing ElevenLabs: {str(e)}")
                raise

    def generate_audio(self, text: str, voice_name: str, output_path: str) -> bool:
        """Generate audio using configured TTS engines with fallback."""
        if voice_name not in self.config['characters']:
            logger.error(f"Voice not found in configuration: {voice_name}")
            return False

        voice_config = self.config['characters'][voice_name]
        success = False

        # Try each engine in order
        for engine in self.config['engine_order']:
            if engine == 'kokoro':
                try:
                    self._initialize_engines('kokoro')
                    if self.kokoro_engine is None:
                        continue  # Skip if Kokoro not available
                    self.kokoro_engine.synth(
                        text=text,
                        speaker_wav=voice_config['speaker_wav'],
                        language=voice_config.get('language', 'en'),
                        output_path=output_path
                    )
                    success = True
                    logger.info(f"Successfully generated audio using Kokoro TTS for {voice_name}")
                    break
                except Exception as e:
                    logger.error(f"Kokoro TTS generation failed: {str(e)}")

            elif engine == 'eleven':
                try:
                    self._initialize_engines('eleven')
                    if self.elevenlabs_engine is None:
                        continue  # Skip if ElevenLabs not available
                    self.elevenlabs_engine.synth(
                        text=text,
                        speaker_wav=voice_config['eleven_id'],
                        language=voice_config.get('language', 'en'),
                        output_path=output_path
                    )
                    success = True
                    logger.info(f"Successfully generated audio using ElevenLabs for {voice_name}")
                    break
                except Exception as e:
                    logger.error(f"ElevenLabs generation failed: {str(e)}")

        if not success:
            logger.error(f"All TTS engines failed for {voice_name}")
            return False

        return True

def generate_from_script(script_path, config_path, output_dir):
    """Generate audio for all dialogue lines in a script."""
    # Load script
    with open(script_path, 'r', encoding='utf-8') as f:
        script = json.load(f)
    
    generator = TTSGenerator(config_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    for scene in script.get('scenes', []):
        scene_num = scene.get('scene_number', 'unknown')
        for idx, line in enumerate(scene.get('lines', [])):
            # Only process dialogue lines
            if line.get('type') != 'dialogue':
                continue
            
            char_name = line.get('speaker', '').strip()
            text = line.get('content', '').strip()
            
            # Only process if character is in config
            if char_name in generator.config['characters'] and text:
                out_path = f"{output_dir}/scene{scene_num}_line{idx}_{char_name}.wav"
                logger.info(f"Generating: {char_name}: {text} -> {out_path}")
                generator.generate_audio(text, char_name, out_path)
    
    logger.info(f"Batch generation complete. Output in {output_dir}")

def main():
    parser = argparse.ArgumentParser(description='Generate audio using TTS system')
    parser.add_argument('--config', default='voices/voice_config.json', help='Path to voice configuration file')
    parser.add_argument('--text', help='Text to convert to speech')
    parser.add_argument('--voice', help='Voice name to use')
    parser.add_argument('--output', help='Output audio file path')
    parser.add_argument('--script', help='Path to episode script JSON for batch generation')
    parser.add_argument('--output_dir', '--outdir', dest='output_dir', help='Output directory for batch generation')
    args = parser.parse_args()

    if args.script and args.output_dir:
        generate_from_script(args.script, args.config, args.output_dir)
        return 0
    elif args.text and args.voice and args.output:
        try:
            generator = TTSGenerator(args.config)
            success = generator.generate_audio(args.text, args.voice, args.output)
            return 0 if success else 1
        except Exception as e:
            logger.error(f"Error in main: {str(e)}")
            return 1
    else:
        parser.print_help()
        return 2

if __name__ == '__main__':
    sys.exit(main()) 