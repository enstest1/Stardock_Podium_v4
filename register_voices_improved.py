#!/usr/bin/env python
"""
Improved Voice Registration Script for Stardock Podium characters.

This script contains enhanced voice descriptions optimized for ElevenLabs Voice Design,
providing more detailed and nuanced character voice definitions.
"""

import os
from dotenv import load_dotenv
from voice_registry import VoiceRegistry

# Load environment variables
load_dotenv()

# Enhanced Character Voice Descriptions
# These descriptions are optimized for ElevenLabs Voice Design API
# More detailed descriptions produce better, more consistent voices
CHARACTER_VOICES = [
    {
        "name": "Aria T'Vel",
        "description": """A Vulcan female voice that is smooth, calm, and precisely articulated. 
The voice has a logical, measured quality typical of Vulcans, with perfect enunciation and clear 
vowel pronunciation. There is an undercurrent of warmth and emotional depth that suggests she 
understands emotions even while maintaining Vulcan control. The voice should sound intelligent 
and authoritative, with a calm confidence. The tone is steady and controlled, never hurried or 
emotional, but capable of subtle shifts that reveal deeper feelings. The pitch is medium to 
slightly lower for a female voice, conveying wisdom and maturity. Articulation is crisp and 
precise, with careful pronunciation of consonants.""",
        "settings": {
            "stability": 0.65,  # Slightly higher for Vulcan consistency
            "similarity_boost": 0.80,
            "style": 0.15,  # Minimal style - logical Vulcan
            "use_speaker_boost": True
        }
    },
    {
        "name": "Jalen",
        "description": """A male Trill voice that is warm, enthusiastic, and carries the wisdom 
of multiple lifetimes through the symbiont. The voice has a natural eagerness and curiosity that 
can accelerate when excited about discoveries, while maintaining a foundation of ancient knowledge 
and experience. The tone is friendly and approachable, yet authoritative when needed. There's a 
slight musical quality to the voice, reflecting the Trill culture's appreciation for music and 
art. The voice should sound like it belongs to someone both youthful in energy and ancient in 
wisdom - enthusiastic but never naive. The pitch is medium, with warmth in the lower register. 
The voice can shift between quick, excited delivery for scientific discoveries and slower, more 
contemplative tones when sharing wisdom from past hosts.""",
        "settings": {
            "stability": 0.55,  # Allow for more expressive variation
            "similarity_boost": 0.75,
            "style": 0.25,  # More expressive style for enthusiasm
            "use_speaker_boost": True
        }
    },
    {
        "name": "Naren",
        "description": """A female Bajoran voice that is strong and confident, with the remarkable 
ability to shift between commanding authority and spiritual serenity. The voice carries the weight 
of experience and resilience, reflecting someone who has survived occupation and emerged stronger. 
There is a slight accent that reflects her Bajoran heritage - subtle but present, with a musical 
quality to the pronunciation. The voice should sound like it belongs to a leader - firm when giving 
orders, compassionate when comforting, and reverent when speaking of the Prophets. The tone is 
firm but never harsh, compassionate but never weak. The pitch is medium to slightly lower, conveying 
maturity and strength. When speaking of spiritual matters, the voice takes on a softer, more 
contemplative quality. When commanding, it becomes crisp and clear with authority.""",
        "settings": {
            "stability": 0.60,  # Balance between consistency and expressiveness
            "similarity_boost": 0.80,
            "style": 0.30,  # More style for emotional range
            "use_speaker_boost": True
        }
    },
    {
        "name": "Elara",
        "description": """A female Caitian voice that is softly musical with a subtle purring 
undertone. The voice should be soothing and gentle, with a playful lilt that can become serious 
and professional when needed. The tone reflects her species' feline nature - smooth, graceful, 
and fluid like a cat's movement. There's a warmth to the voice that makes patients feel at ease, 
combined with clear, professional articulation that establishes medical authority. The voice has 
a slight breathy quality that adds to its gentle nature. When serious or concerned, the playful 
elements fade but the warmth remains. The pitch is medium to slightly higher, with smooth 
transitions between tones. The voice should sound like someone who is both nurturing and 
competent - a healer's voice.""",
        "settings": {
            "stability": 0.50,  # More variation for expressiveness
            "similarity_boost": 0.75,
            "style": 0.20,  # Moderate style for warmth
            "use_speaker_boost": True
        }
    },
    {
        "name": "Sarik",
        "description": """A male El-Aurian voice that is gentle and reflective, carrying an aura 
of wisdom beyond his years. The voice is deliberate and thoughtful, with a comforting, almost 
lyrical quality that reflects his species' long lifespan and natural empathy. The tone should 
sound like someone who has seen centuries pass - patient, understanding, and deeply empathetic. 
There's a musical quality to the voice, with smooth, flowing speech patterns. The voice should 
sound calming and reassuring, like a wise counselor or mentor. The pitch is medium to slightly 
lower, with a richness that comes from experience. The voice moves at a measured pace, never 
rushed, with pauses that feel natural and contemplative. When speaking, it sounds like each word 
is carefully chosen and meaningful.""",
        "settings": {
            "stability": 0.70,  # Higher stability for consistent wisdom
            "similarity_boost": 0.80,
            "style": 0.15,  # Minimal style - measured and wise
            "use_speaker_boost": True
        }
    },
    {
        "name": "Narrator",
        "description": """A versatile narrator voice that is clear, authoritative, and engaging. 
The voice should sound like a professional documentary narrator or audiobook reader - confident 
and easy to listen to for extended periods. The tone is warm but neutral, allowing the story to 
take center stage. The voice should be articulate with excellent pronunciation, suitable for 
describing complex scenes and technical concepts. There should be a sense of gravitas appropriate 
for Star Trek storytelling - serious when needed, but never melodramatic. The voice should be 
smooth and flowing, with natural pacing that guides the listener through the narrative. The pitch 
is medium, with good projection and clarity. The voice should feel trustworthy and reliable, like 
a skilled storyteller.""",
        "settings": {
            "stability": 0.65,  # Consistent narrator voice
            "similarity_boost": 0.75,
            "style": 0.10,  # Minimal style - clear and neutral
            "use_speaker_boost": True
        }
    }
]

def main():
    """Create and register improved voices for all characters."""
    print("Creating and registering improved voices for characters...")
    print("Note: This will create NEW voices. Old voices will remain in your ElevenLabs account.")
    print("You may want to test these voices before updating voice_config.json\n")
    
    registry = VoiceRegistry()
    
    results = {}
    
    for voice_data in CHARACTER_VOICES:
        print(f"\n{'='*60}")
        print(f"Creating improved voice for: {voice_data['name']}")
        print(f"{'='*60}")
        print(f"Description: {voice_data['description'][:100]}...")
        
        result = registry.create_voice_from_description(
            name=voice_data['name'] + " (Improved)",  # Append "(Improved)" to distinguish
            description=voice_data['description']
        )
        
        if "error" in result:
            print(f"[ERROR] Error creating voice for {voice_data['name']}: {result['error']}")
            results[voice_data['name']] = {"success": False, "error": result['error']}
        else:
            print(f"[SUCCESS] Successfully created voice for {voice_data['name']}")
            print(f"   Voice ID: {result.get('voice_id', 'N/A')}")
            print(f"   Registry ID: {result.get('voice_registry_id', 'N/A')}")
            
            # Update voice settings
            if 'settings' in voice_data:
                updated = registry.update_voice(
                    result['voice_registry_id'],
                    {'settings': voice_data['settings']}
                )
                if "error" not in updated:
                    print(f"   [OK] Updated voice settings")
                else:
                    print(f"   [WARNING] Could not update settings: {updated.get('error')}")
            
            results[voice_data['name']] = {
                "success": True,
                "voice_id": result.get('voice_id'),
                "voice_registry_id": result.get('voice_registry_id')
            }
    
    print(f"\n{'='*60}")
    print("Voice creation complete!")
    print(f"{'='*60}\n")
    
    # Print summary
    print("Summary of created voices:")
    print("-" * 60)
    for name, result in results.items():
        if result.get("success"):
            print(f"[SUCCESS] {name}")
            print(f"   Voice ID: {result.get('voice_id')}")
            print(f"   Next step: Update voice_config.json with this voice_id")
        else:
            print(f"[FAILED] {name}: {result.get('error', 'Unknown error')}")
        print()
    
    print("\n[IMPORTANT] NEXT STEPS:")
    print("1. Test each new voice to ensure quality")
    print("2. Compare new voices with old ones")
    print("3. Update voice_config.json with new voice IDs if satisfied")
    print("4. Keep old voice IDs for existing episodes if needed")
    print("\nTo test a voice, use:")
    print('  python cli/generate_voices.py --text "Test dialogue" --voice "CHARACTER_NAME" --output test.wav')

if __name__ == "__main__":
    main()

