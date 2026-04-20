#!/usr/bin/env python
"""
Script to list available ElevenLabs voices (optional legacy tool).

Requires: pip install elevenlabs and ELEVENLABS_API_KEY.
Default dialogue uses Kokoro; see README.md.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    """List all available ElevenLabs voices."""
    try:
        from elevenlabs import ElevenLabs
    except ImportError:
        print(
            'elevenlabs is not installed. This script is optional.\n'
            'Install with: pip install elevenlabs'
        )
        sys.exit(1)

    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print('Error: ELEVENLABS_API_KEY not found in environment variables')
        sys.exit(1)

    elevenlabs = ElevenLabs(api_key=api_key)

    try:
        voices = elevenlabs.voices.get_all()
        print('\nAvailable ElevenLabs Voices:')
        print('-' * 50)
        for voice in voices.voices:
            print(f'Name: {voice.name}')
            print(f'Voice ID: {voice.voice_id}')
            print(f'Category: {voice.category}')
            print(
                'Description:',
                voice.labels.get('description', 'No description'),
            )
            print('-' * 50)
    except Exception as e:
        print(f'Error listing voices: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
