#!/usr/bin/env python3
"""
Test Original Voice Generator for Stardock Podium.

This script generates test audio samples using the ORIGINAL voice IDs
so you can compare them with the new improved voices.
"""

import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts_engine import get_elevenlabs_engine

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Original voice IDs (before the new improved ones)
ORIGINAL_VOICE_IDS = {
    "naren": "b9MWoRWjKTSI9ipAOsJV",
    "aria": "NTYYhif3Ref3SlagDJyF",
    "jalen": "mPRt73eGyddBVa9A9CNm",
    "elara": "wl2c369YHrfTBCRcQh5X",
    "sarik": "RK5lOhdEvnIrQW4427LT",
    "narrator": "JidnYYb3vc6McUQCcLcz"
}

# Test text samples (same as used for improved voices)
TEST_SAMPLES = {
    "narrator": "Welcome to Stardock Podium, a Star Trek storytelling podcast. Today we continue our journey through the stars.",
    "aria": "This is Aria T'Vel, science officer of the U.S.S. Stardock. I've completed my analysis of the anomaly.",
    "naren": "Commander Naren here. All systems are operational. We're ready to proceed with the mission.",
    "jalen": "Lieutenant Jalen reporting. I've detected an unusual energy signature on long-range sensors.",
    "elara": "This is Elara, chief medical officer. The crew's vital signs are all within normal parameters.",
    "sarik": "Sarik here, security chief. All defensive systems are online and ready. We're prepared for anything."
}

def generate_original_voice_tests(output_dir: str = "voices/test_samples"):
    """Generate test audio samples using original voice IDs.
    
    Args:
        output_dir: Directory to save test audio files
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize engine
    engine = get_elevenlabs_engine()
    
    logger.info(f"Generating test samples using ORIGINAL voice IDs...")
    logger.info(f"Output directory: {output_path.absolute()}")
    
    success_count = 0
    failed_voices = []
    
    for voice_name, voice_id in ORIGINAL_VOICE_IDS.items():
        # Get test text (use generic if not in samples)
        test_text = TEST_SAMPLES.get(voice_name.lower(), 
                                     f"This is a test of the {voice_name} voice for the Star Trek podcast.")
        
        output_file = output_path / f"test_{voice_name}_original.wav"
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Generating test for ORIGINAL: {voice_name}")
        logger.info(f"Voice ID: {voice_id}")
        logger.info(f"Text: {test_text}")
        logger.info(f"Output: {output_file}")
        
        try:
            engine.synth(
                text=test_text,
                speaker_wav=voice_id,  # Use voice_id directly
                language="en",
                output_path=str(output_file)
            )
            
            # Check if file was created
            if output_file.exists():
                file_size = output_file.stat().st_size / 1024  # KB
                logger.info(f"✓ Success! File size: {file_size:.1f} KB")
                success_count += 1
            else:
                logger.error(f"✗ Failed: File was not created")
                failed_voices.append(voice_name)
                
        except Exception as e:
            logger.error(f"✗ Failed: {str(e)}")
            failed_voices.append(voice_name)
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("GENERATION SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Total voices: {len(ORIGINAL_VOICE_IDS)}")
    logger.info(f"Successfully generated: {success_count}")
    logger.info(f"Failed: {len(failed_voices)}")
    
    if failed_voices:
        logger.warning(f"Failed voices: {', '.join(failed_voices)}")
    
    if success_count > 0:
        logger.info(f"\n✓ Original voice test files saved to: {output_path.absolute()}")
        logger.info(f"\nTo compare voices:")
        logger.info(f"  1. Open the folder: {output_path.absolute()}")
        logger.info(f"  2. Compare: test_{'{voice_name}'}_original.wav vs test_{'{voice_name}'}.wav")
        logger.info(f"  3. Review quality differences between original and improved voices")
    
    return len(failed_voices) == 0

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate test audio samples using original voice IDs for comparison'
    )
    parser.add_argument(
        '--output-dir',
        default='voices/test_samples',
        help='Directory to save test audio files'
    )
    
    args = parser.parse_args()
    
    success = generate_original_voice_tests(args.output_dir)
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())

