#!/usr/bin/env python3
"""
Generate theme music for podcast intro/outro using ElevenLabs Music API.
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def generate_music_via_api(api_key: str, prompt: str, output_file: Path, duration_ms: int = 30000):
    """Generate music using ElevenLabs Music API via REST."""
    url = "https://api.elevenlabs.io/v1/music-generation"
    
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": prompt,
        "duration": duration_ms,
        "instrumental": True
    }
    
    try:
        print(f"  Sending request to ElevenLabs Music API...")
        response = requests.post(url, headers=headers, json=payload, stream=True)
        response.raise_for_status()
        
        # Save the audio stream
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"✓ Music saved to: {output_file}")
        return output_file
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"  Error: Music API endpoint not found (404)")
            print(f"  This may mean Music API is not available on your plan")
            return None
        elif e.response.status_code == 401:
            print(f"  Error: Authentication failed. Check your API key.")
            return None
        else:
            error_detail = e.response.json() if e.response.content else {}
            print(f"  Error: {e.response.status_code} - {error_detail.get('detail', str(e))}")
            return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def generate_intro_music(api_key: str, output_dir: Path):
    """Generate intro theme music."""
    print("Generating intro theme music...")
    
    prompt = "Epic space sci-fi theme music, orchestral, mysterious and adventurous, Star Trek style opening, instrumental"
    intro_file = output_dir / "theme_intro.mp3"
    
    return generate_music_via_api(api_key, prompt, intro_file, duration_ms=30000)

def generate_outro_music(api_key: str, output_dir: Path):
    """Generate outro theme music."""
    print("Generating outro theme music...")
    
    prompt = "Epic space sci-fi closing theme, orchestral, triumphant and hopeful, Star Trek style ending, fade out, instrumental"
    outro_file = output_dir / "theme_outro.mp3"
    
    return generate_music_via_api(api_key, prompt, outro_file, duration_ms=20000)

def main():
    """Main function."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment variables")
        print("Please set it in your .env file")
        sys.exit(1)
    
    # Create output directory
    output_dir = Path("assets/music")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    print("=" * 60)
    print("Generating Theme Music for Stardock Podium")
    print("=" * 60)
    print()
    
    # Generate intro music
    intro_file = generate_intro_music(api_key, output_dir)
    print()
    
    # Generate outro music
    outro_file = generate_outro_music(api_key, output_dir)
    print()
    
    if intro_file and outro_file:
        print("=" * 60)
        print("Music generation complete!")
        print("=" * 60)
        print(f"Intro: {intro_file}")
        print(f"Outro: {outro_file}")
        print()
        print("These files will be automatically used in your episodes.")
    elif intro_file or outro_file:
        print("=" * 60)
        print("Partial completion - some music files generated.")
        print("=" * 60)
        if intro_file:
            print(f"Intro: {intro_file}")
        if outro_file:
            print(f"Outro: {outro_file}")
    else:
        print("=" * 60)
        print("NOTE: Music generation via API failed.")
        print("This may require:")
        print("  1. A paid ElevenLabs plan with Music API access")
        print("  2. The Music API may not be available yet")
        print()
        print("Alternative: Add theme music files manually to:")
        print(f"  {output_dir}")
        print()
        print("Suggested filenames:")
        print("  - theme_intro.mp3 (for intro)")
        print("  - theme_outro.mp3 (for outro)")
        print("  - intro*.mp3 or opening*.mp3 (will also work for intro)")
        print("  - outro*.mp3 or closing*.mp3 (will also work for outro)")

if __name__ == "__main__":
    main()

