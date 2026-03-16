#!/usr/bin/env python3
"""
Audio Combination CLI for Stardock Podium.

This script combines individual audio clips into a complete podcast episode,
following the scene structure from script.json.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
import ffmpeg

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_script(script_path: str) -> dict:
    """Load and validate script JSON."""
    try:
        with open(script_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading script: {str(e)}")
        raise

def get_audio_files(scene_dir: Path, scene_number: int) -> list:
    """Get audio files for a scene in order."""
    scene_files = []
    scene_pattern = f"scene{scene_number}_line*"
    
    # Get all line files for this scene
    line_files = sorted(scene_dir.glob(scene_pattern))
    
    for line_file in line_files:
        if line_file.suffix in ['.wav', '.mp3']:
            scene_files.append(str(line_file))
    
    return scene_files

def combine_scene_audio(scene_files: list, output_file: str) -> bool:
    """Combine audio files for a scene into a single file."""
    try:
        # Create input streams
        streams = []
        for file in scene_files:
            stream = ffmpeg.input(file)
            streams.append(stream)
        
        # Combine streams
        combined = ffmpeg.concat(*streams, v=0, a=1)
        
        # Write output
        combined.output(output_file).overwrite_output().run(capture_stdout=True, capture_stderr=True)
        return True
    except Exception as e:
        logger.error(f"Error combining scene audio: {str(e)}")
        return False

def combine_episode_audio(script_path: str, audio_dir: str, output_file: str) -> bool:
    """Combine all scene audio files into a complete episode."""
    try:
        # Load script
        script = load_script(script_path)
        audio_dir = Path(audio_dir)
        
        # Create temp directory for scene audio
        temp_dir = audio_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Process each scene
        scene_files = []
        for scene in script.get('scenes', []):
            scene_number = scene.get('scene_number', 0)
            
            # Get audio files for this scene
            scene_audio_files = get_audio_files(audio_dir, scene_number)
            if not scene_audio_files:
                logger.warning(f"No audio files found for scene {scene_number}")
                continue
            
            # Combine scene audio
            scene_output = temp_dir / f"scene_{scene_number:02d}.mp3"
            if combine_scene_audio(scene_audio_files, str(scene_output)):
                scene_files.append(str(scene_output))
            else:
                logger.error(f"Failed to combine audio for scene {scene_number}")
                return False
        
        # Combine all scenes
        if scene_files:
            if combine_scene_audio(scene_files, output_file):
                logger.info(f"Successfully combined episode audio: {output_file}")
                return True
            else:
                logger.error("Failed to combine episode audio")
                return False
        else:
            logger.error("No scene audio files found")
            return False
            
    except Exception as e:
        logger.error(f"Error combining episode audio: {str(e)}")
        return False
    finally:
        # Clean up temp directory
        if temp_dir.exists():
            for file in temp_dir.glob("*"):
                file.unlink()
            temp_dir.rmdir()

def main():
    parser = argparse.ArgumentParser(description='Combine audio clips into a podcast episode')
    parser.add_argument('--script', required=True, help='Path to episode script JSON')
    parser.add_argument('--audio-dir', required=True, help='Directory containing audio clips')
    parser.add_argument('--output', required=True, help='Output audio file path')
    
    args = parser.parse_args()
    
    success = combine_episode_audio(args.script, args.audio_dir, args.output)
    return 0 if success else 1

if __name__ == '__main__':
    exit(main()) 