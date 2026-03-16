#!/usr/bin/env python
"""
Helper script to display voice descriptions for manual creation in ElevenLabs web interface.

Since voice creation via API requires a paid plan, this script helps you:
1. View all improved voice descriptions in a format easy to copy
2. Format them for pasting into the ElevenLabs web interface
"""

from register_voices_improved import CHARACTER_VOICES

def print_voice_for_web(voice_data):
    """Print voice description formatted for web interface."""
    print(f"\n{'='*80}")
    print(f"VOICE NAME: {voice_data['name']} (Improved)")
    print(f"{'='*80}\n")
    
    print("DESCRIPTION (copy this entire block):")
    print("-" * 80)
    print(voice_data['description'])
    print("-" * 80)
    
    print("\nRECOMMENDED SETTINGS:")
    settings = voice_data.get('settings', {})
    print(f"  Stability: {settings.get('stability', 0.5)}")
    print(f"  Similarity Boost: {settings.get('similarity_boost', 0.75)}")
    print(f"  Style: {settings.get('style', 0.0)}")
    print(f"  Speaker Boost: {settings.get('use_speaker_boost', True)}")
    
    print("\n" + "="*80 + "\n")

def main():
    """Display all voice descriptions for manual creation."""
    print("="*80)
    print("ELEVENLABS VOICE CREATION HELPER")
    print("="*80)
    print("\nSince API voice creation requires a paid plan, use these descriptions")
    print("to create voices manually via: https://elevenlabs.io/app/voice-design\n")
    print("Copy each description below and paste into the ElevenLabs web interface.\n")
    
    for voice_data in CHARACTER_VOICES:
        print_voice_for_web(voice_data)
    
    print("\n" + "="*80)
    print("INSTRUCTIONS:")
    print("="*80)
    print("1. Go to: https://elevenlabs.io/app/voice-design")
    print("2. For each voice above:")
    print("   - Click 'Add Voice' or 'Create Voice'")
    print("   - Select 'Voice Design' method")
    print("   - Copy the DESCRIPTION above")
    print("   - Paste into description field")
    print("   - Name it: [Character Name] (Improved)")
    print("   - Generate the voice")
    print("   - Copy the Voice ID")
    print("3. Update voice_config.json with new Voice IDs")
    print("="*80)

if __name__ == "__main__":
    main()

