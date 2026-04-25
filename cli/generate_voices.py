#!/usr/bin/env python3
"""
Voice Generation CLI for Stardock Podium.

This script generates voice audio for episode scripts using Kokoro TTS.

Note: The ElevenLabs fallback that used to live here has been removed —
Kokoro is the sole supported engine for the default pipeline. If
``engine_order`` in voice_config.json still contains ``eleven`` it will be
skipped with a deprecation warning.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

import torch  # noqa: F401 — imported so failure surfaces early on bad env
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_engine import get_kokoro_engine, SynthError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TTSGenerator:
    """Kokoro‑only TTS generator driven by ``voice_config.json``."""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.kokoro_engine = None

        engine_order = self.config.get('engine_order', ['kokoro'])
        extra = [e for e in engine_order if e not in ('kokoro',)]
        if extra:
            logger.warning(
                "This CLI uses Kokoro only; engine_order also lists %s — "
                "use main.py generate-audio for full xtts+kokoro routing.",
                extra,
            )

    def _load_config(self, config_path: str) -> dict:
        """Load and validate voice configuration."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading config: {str(e)}")
            raise

    def _initialize_engines(self, engine_type: str = None):
        """Lazy‑init Kokoro. ``engine_type`` is accepted for back‑compat.

        Any value other than ``'kokoro'`` / ``None`` is ignored with a warn.
        """
        if engine_type and engine_type != 'kokoro':
            logger.warning(
                "Engine '%s' is no longer supported; only 'kokoro' runs here.",
                engine_type,
            )
            return

        if self.kokoro_engine is None:
            try:
                self.kokoro_engine = get_kokoro_engine()
                logger.info("Kokoro TTS initialized successfully")
            except Exception as e:
                logger.warning(
                    f"Kokoro TTS not available (will skip): {str(e)}"
                )

    def generate_audio(
            self, text: str, voice_name: str, output_path: str) -> bool:
        """Generate audio for one line using Kokoro."""
        if voice_name not in self.config['characters']:
            logger.error(f"Voice not found in configuration: {voice_name}")
            return False

        voice_config = self.config['characters'][voice_name]

        self._initialize_engines('kokoro')
        if self.kokoro_engine is None:
            logger.error(
                f"Kokoro engine unavailable; cannot synthesise {voice_name}")
            return False

        try:
            self.kokoro_engine.synth(
                text=text,
                speaker_wav=voice_config['speaker_wav'],
                language=voice_config.get('language', 'en'),
                output_path=output_path,
            )
            logger.info(
                f"Generated audio via Kokoro for {voice_name} → {output_path}"
            )
            return True
        except SynthError as e:
            logger.error(f"Kokoro TTS generation failed for {voice_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during Kokoro synth: {e}")
            return False


def generate_from_script(script_path, config_path, output_dir):
    """Generate audio for all dialogue lines in a script."""
    with open(script_path, 'r', encoding='utf-8') as f:
        script = json.load(f)

    generator = TTSGenerator(config_path)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for scene in script.get('scenes', []):
        scene_num = scene.get('scene_number', 'unknown')
        for idx, line in enumerate(scene.get('lines', [])):
            if line.get('type') != 'dialogue':
                continue

            char_name = line.get('speaker', '').strip()
            text = line.get('content', '').strip()

            if char_name in generator.config['characters'] and text:
                out_path = (
                    f"{output_dir}/scene{scene_num}_line{idx}_"
                    f"{char_name}.wav"
                )
                logger.info(
                    f"Generating: {char_name}: {text} -> {out_path}")
                generator.generate_audio(text, char_name, out_path)

    logger.info(f"Batch generation complete. Output in {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Generate audio using Kokoro TTS')
    parser.add_argument(
        '--config', default='voices/voice_config.json',
        help='Path to voice configuration file')
    parser.add_argument('--text', help='Text to convert to speech')
    parser.add_argument('--voice', help='Voice name to use')
    parser.add_argument('--output', help='Output audio file path')
    parser.add_argument(
        '--script', help='Path to episode script JSON for batch generation')
    parser.add_argument(
        '--output_dir', '--outdir', dest='output_dir',
        help='Output directory for batch generation')
    args = parser.parse_args()

    if args.script and args.output_dir:
        generate_from_script(args.script, args.config, args.output_dir)
        return 0
    elif args.text and args.voice and args.output:
        try:
            generator = TTSGenerator(args.config)
            success = generator.generate_audio(
                args.text, args.voice, args.output)
            return 0 if success else 1
        except Exception as e:
            logger.error(f"Error in main: {str(e)}")
            return 1
    else:
        parser.print_help()
        return 2


if __name__ == '__main__':
    sys.exit(main())
