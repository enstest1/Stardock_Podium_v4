#!/usr/bin/env python3
"""
Voice Registry Migration Tool for Stardock Podium.

This script converts the old voice registry to the new Kokoro TTS configuration format.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_registry(registry_path: str) -> dict:
    """Load the old voice registry.
    
    Args:
        registry_path: Path to old registry file
        
    Returns:
        dict: Registry data
    """
    try:
        with open(registry_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading registry: {str(e)}")
        raise

def create_new_config(registry: dict) -> dict:
    """Create new voice configuration from registry.
    
    Args:
        registry: Old registry data
        
    Returns:
        dict: New configuration data
    """
    config = {
        "engine_order": ["kokoro", "eleven"],
        "characters": {}
    }
    
    for char_name, char_data in registry.items():
        config["characters"][char_name] = {
            "speaker_wav": "",  # User must provide this
            "language": "en",
            "eleven_id": char_data.get("voice_id", "")  # Copy from old registry
        }
    
    return config

def save_config(config: dict, output_path: str) -> None:
    """Save new configuration to file.
    
    Args:
        config: New configuration data
        output_path: Path to save configuration
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Saved new configuration to {output_path}")
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        raise

def print_todo_list(config: dict) -> None:
    """Print TODO list for user.
    
    Args:
        config: New configuration data
    """
    print("\nTODO List:")
    print("==========")
    print("Please provide voice samples for the following characters:")
    for char_name in config["characters"]:
        print(f"- {char_name}:")
        print(f"  - Record 5-10 seconds of clear speech")
        print(f"  - Save as WAV file (16kHz, mono)")
        print(f"  - Place in voices/samples/{char_name.lower().replace(' ', '_')}.wav")
        print(f"  - Update speaker_wav in voice_config.json")
    print("\nAfter completing these tasks, run validate_voices.py to verify your setup.")

def main():
    parser = argparse.ArgumentParser(description='Migrate voice registry to new format')
    parser.add_argument('--registry', default='voices/registry.json', help='Path to old registry file')
    parser.add_argument('--output', default='voices/voice_config.json', help='Path to save new configuration')
    args = parser.parse_args()

    try:
        # Load old registry
        registry = load_registry(args.registry)
        
        # Create new configuration
        config = create_new_config(registry)
        
        # Save new configuration
        save_config(config, args.output)
        
        # Print TODO list
        print_todo_list(config)
        
        return 0
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 