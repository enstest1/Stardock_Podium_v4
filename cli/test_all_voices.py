#!/usr/bin/env python3
"""
Test Voice Generator for Stardock Podium.

This script generates test audio samples for all configured voices
so you can review quality before generating the full podcast.
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.generate_voices import TTSGenerator

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test text samples for each character type
TEST_SAMPLES = {
    "narrator": "Welcome to Stardock Podium, a Star Trek storytelling podcast. Today we continue our journey through the stars.",
    "aria": "This is Aria T'Vel, science officer of the U.S.S. Stardock. I've completed my analysis of the anomaly.",
    "naren": "Commander Naren here. All systems are operational. We're ready to proceed with the mission.",
    "jalen": "Lieutenant Jalen reporting. I've detected an unusual energy signature on long-range sensors.",
    "elara": "This is Elara, chief medical officer. The crew's vital signs are all within normal parameters.",
    "sarik": "Sarik here, security chief. All defensive systems are online and ready. We're prepared for anything."
}

def generate_all_voice_tests(config_path: str = "voices/voice_config.json", 
                              output_dir: str = "voices/test_samples"):
    """Generate test audio samples for all configured voices.
    
    Args:
        config_path: Path to voice configuration file
        output_dir: Directory to save test audio files
    """
    # Load configuration
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        return False
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize generator
    generator = TTSGenerator(config_path)
    
    # Get all characters from config
    characters = config.get('characters', {})
    
    logger.info(f"Generating test samples for {len(characters)} voices...")
    logger.info(f"Output directory: {output_path.absolute()}")
    
    success_count = 0
    failed_voices = []
    
    for voice_name in characters.keys():
        # Get test text (use generic if not in samples)
        test_text = TEST_SAMPLES.get(voice_name.lower(), 
                                     f"This is a test of the {voice_name} voice for the Star Trek podcast.")
        
        output_file = output_path / f"test_{voice_name}.wav"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Generating test for: {voice_name}")
        logger.info(f"Text: {test_text}")
        logger.info(f"Output: {output_file}")
        
        try:
            success = generator.generate_audio(
                text=test_text,
                voice_name=voice_name,
                output_path=str(output_file)
            )
            
            if success:
                # Check if file was created
                if output_file.exists():
                    file_size = output_file.stat().st_size / 1024  # KB
                    logger.info(f"✓ Success! File size: {file_size:.1f} KB")
                    success_count += 1
                else:
                    logger.error(f"✗ Failed: File was not created")
                    failed_voices.append(voice_name)
            else:
                logger.error(f"✗ Failed: Generation returned False")
                failed_voices.append(voice_name)
                
        except Exception as e:
            logger.error(f"✗ Failed: {str(e)}")
            failed_voices.append(voice_name)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("GENERATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total voices: {len(characters)}")
    logger.info(f"Successfully generated: {success_count}")
    logger.info(f"Failed: {len(failed_voices)}")
    
    if failed_voices:
        logger.warning(f"Failed voices: {', '.join(failed_voices)}")
    
    if success_count > 0:
        logger.info(f"\n✓ Test audio files saved to: {output_path.absolute()}")
        logger.info(f"\nTo listen to the test files:")
        logger.info(f"  1. Open the folder: {output_path.absolute()}")
        logger.info(f"  2. Double-click any .wav file to play it in your default audio player")
        logger.info(f"  3. Review each voice for quality and character appropriateness")
    
    return len(failed_voices) == 0

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate test audio samples for all configured voices'
    )
    parser.add_argument(
        '--config', 
        default='voices/voice_config.json',
        help='Path to voice configuration file'
    )
    parser.add_argument(
        '--output-dir',
        default='voices/test_samples',
        help='Directory to save test audio files'
    )
    
    args = parser.parse_args()
    
    success = generate_all_voice_tests(args.config, args.output_dir)
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())

