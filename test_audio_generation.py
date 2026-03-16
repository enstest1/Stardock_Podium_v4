#!/usr/bin/env python3
"""
Test script to generate audio for intro and first 5 scenes only.
This helps verify everything works before running the full episode.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from audio_pipeline import get_audio_pipeline
from script_editor import load_episode_script

# Load environment variables
load_dotenv()

def test_audio_generation(episode_id: str, max_scenes: int = 5):
    """Generate audio for intro and first N scenes only.
    
    Args:
        episode_id: Episode ID to generate
        max_scenes: Maximum number of scenes to generate (default: 5)
    """
    print("=" * 70)
    print(f"Testing Audio Generation for Episode: {episode_id}")
    print(f"Generating: Intro + First {max_scenes} scenes only")
    print("=" * 70)
    print()
    
    # Load script
    script = load_episode_script(episode_id)
    scenes = script.get('scenes', [])
    
    print(f"Found {len(scenes)} scenes in script")
    print(f"Will generate: Intro + Scenes 0-{min(max_scenes-1, len(scenes)-1)}")
    print()
    
    # Get audio pipeline
    pipeline = get_audio_pipeline()
    
    # Get episode directory
    audio_dir = Path(f"episodes/{episode_id}/audio")
    audio_dir.mkdir(exist_ok=True, parents=True)
    
    # Limit scenes to first max_scenes
    test_scenes = scenes[:max_scenes]
    
    try:
        # Generate intro narration
        print("Step 1: Generating intro narration...")
        intro_narration = pipeline._generate_intro_narration(episode_id)
        if intro_narration:
            print(f"[OK] Intro narration generated: {intro_narration}")
        else:
            print("[FAIL] Failed to generate intro narration")
        print()
        
        # Create intro segment (with music)
        print("Step 2: Creating intro segment (with theme music)...")
        intro_segment = pipeline._create_intro_segment(episode_id)
        if intro_segment:
            print(f"[OK] Intro segment created: {intro_segment}")
        else:
            print("[FAIL] Failed to create intro segment")
        print()
        
        # Get character voices mapping (empty dict for now, will be handled in generate_scene_audio)
        character_voices = {}
        
        # Generate audio for each test scene
        scene_results = []
        for i, scene in enumerate(test_scenes):
            print(f"Step {3+i}: Generating audio for Scene {i+1}/{len(test_scenes)}...")
            try:
                result = pipeline.generate_scene_audio(
                    scene, i, character_voices, episode_id, audio_dir
                )
                if result.get('success'):
                    print(f"  [OK] Scene {i} audio generated: {result.get('duration', 0):.1f}s")
                    scene_results.append({
                        "scene_index": i,
                        "success": True,
                        "audio_file": result.get('audio_file'),
                        "duration": result.get('duration', 0)
                    })
                else:
                    print(f"  [FAIL] Scene {i} failed: {result.get('error', 'Unknown error')}")
                    scene_results.append({
                        "scene_index": i,
                        "success": False,
                        "error": result.get('error', 'Unknown error')
                    })
            except Exception as e:
                print(f"  [ERROR] Scene {i} error: {e}")
                scene_results.append({
                    "scene_index": i,
                    "success": False,
                    "error": str(e)
                })
            print()
        
        # Create partial episode (intro + test scenes only, no outro for test)
        print("Step 8: Assembling partial episode (intro + test scenes)...")
        try:
            from audio_pipeline import get_episode
            episode = get_episode(episode_id)
            
            # Create concat file
            concat_file = audio_dir / "test_episode_concat.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                # Add intro if available
                if intro_segment and intro_segment.exists():
                    abs_path = intro_segment.resolve()
                    f.write(f"file '{abs_path.as_posix()}'\n")
                
                # Add each scene in order
                valid_scenes = [s for s in scene_results if s.get("success", False) and s.get("audio_file")]
                for scene in sorted(valid_scenes, key=lambda s: s.get("scene_index", 0)):
                    scene_file = scene['audio_file']
                    scene_path = Path(scene_file).resolve()
                    if scene_path.exists():
                        f.write(f"file '{scene_path.as_posix()}'\n")
            
            # Concatenate files (re-encode to ensure compatibility)
            output_file = audio_dir / "test_episode.mp3"
            import ffmpeg
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(str(output_file), acodec='libmp3lame', ar=44100, b='192k')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            print(f"[OK] Test episode assembled: {output_file}")
            
            # Get file size
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            print(f"  File size: {file_size_mb:.2f} MB")
            
            print()
            print("=" * 70)
            print("TEST GENERATION COMPLETE!")
            print("=" * 70)
            print(f"Test episode saved to: {output_file}")
            print(f"Scenes generated: {len(valid_scenes)}/{len(test_scenes)}")
            print()
            print("Listen to the test episode to verify:")
            print("  - Intro narration and music work correctly")
            print("  - All character voices are correct")
            print("  - Audio quality is good")
            print()
            print("If everything looks good, run the full generation with:")
            print(f"  python main.py generate-audio {episode_id} --quality high")
            
            return True
            
        except Exception as e:
            print(f"[FAIL] Error assembling test episode: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"Error during test generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    episode_id = "ep_988afb7c"
    max_scenes = 5
    
    if len(sys.argv) > 1:
        episode_id = sys.argv[1]
    if len(sys.argv) > 2:
        max_scenes = int(sys.argv[2])
    
    success = test_audio_generation(episode_id, max_scenes)
    sys.exit(0 if success else 1)

