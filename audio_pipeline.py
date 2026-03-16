#!/usr/bin/env python
"""
Audio Pipeline Module for Stardock Podium.

This module handles the audio generation, processing, and assembly for podcast
episodes, including voice synthesis, sound effects, and mixing.
"""

import os
import json
import logging
import time
import uuid
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple
import concurrent.futures
import asyncio
from dataclasses import dataclass

# Try to import required libraries
try:
    from elevenlabs import ElevenLabs, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
except ImportError:
    logging.error("ElevenLabs not found. Please install it with: pip install elevenlabs")
    raise

try:
    import ffmpeg
except ImportError:
    logging.error("ffmpeg-python not found. Please install it with: pip install ffmpeg-python")
    raise

# Local imports
from script_editor import load_episode_script
from voice_registry import get_voice_registry, get_voice, map_characters_to_voices
from story_structure import get_episode

# Setup logging
logger = logging.getLogger(__name__)

@dataclass
class AudioClip:
    """Represents an audio clip with metadata."""
    path: str
    type: str
    duration: float
    start_time: float = 0.0
    character: Optional[str] = None
    line_index: Optional[int] = None
    scene_index: Optional[int] = None
    volume: float = 1.0

class AudioPipeline:
    """Audio generation and processing pipeline for podcast episodes."""
    
    def __init__(self, episodes_dir: str = "episodes", assets_dir: str = "assets"):
        """Initialize the audio pipeline.
        
        Args:
            episodes_dir: Directory for episode data
            assets_dir: Directory for audio assets
        """
        self.episodes_dir = Path(episodes_dir)
        self.assets_dir = Path(assets_dir)
        
        # Create asset directories if they don't exist
        self.sound_effects_dir = self.assets_dir / "sound_effects"
        self.music_dir = self.assets_dir / "music"
        self.ambience_dir = self.assets_dir / "ambience"
        
        for directory in [self.sound_effects_dir, self.music_dir, self.ambience_dir]:
            directory.mkdir(exist_ok=True, parents=True)
        
        # Initialize voice registry
        self.voice_registry = get_voice_registry()
        
        # Initialize ElevenLabs API
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if self.api_key:
            self.elevenlabs = ElevenLabs(api_key=self.api_key)
            self.client = ElevenLabsClient(api_key=self.api_key)
        else:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
            self.elevenlabs = None
            self.client = None
        
        # Role to character mapping (using lowercase keys to match voice_config.json)
        self.role_to_character = {
            "COMMANDING OFFICER": "aria",
            "SCIENCE OFFICER": "jalen",
            "SECURITY OFFICER": "naren",
            "CHIEF MEDICAL OFFICER": "elara",
            "COMMUNICATIONS SPECIALIST": "sarik"
        }
        
        # Load voice_config.json for voice IDs
        self.voice_config_path = Path("voices/voice_config.json")
        self.voice_config = self._load_voice_config()
    
    def _load_voice_config(self) -> Dict[str, Any]:
        """Load voice configuration from voice_config.json.
        
        Returns:
            Voice configuration dictionary
        """
        if self.voice_config_path.exists():
            try:
                with open(self.voice_config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading voice config: {e}")
        return {}
    
    def generate_episode_audio(self, episode_id: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Generate audio for a complete episode.
        
        Args:
            episode_id: ID of the episode
            options: Audio generation options
        
        Returns:
            Dictionary with generation results
        """
        # Get episode data
        episode = get_episode(episode_id)
        if not episode:
            return {"error": f"Episode not found: {episode_id}"}
        
        # Get script data
        script = load_episode_script(episode_id)
        if not script:
            return {"error": f"Script not found for episode: {episode_id}"}
        
        # Create audio directory
        episode_dir = self.episodes_dir / episode_id
        audio_dir = episode_dir / "audio"
        audio_dir.mkdir(exist_ok=True)
        
        # Get character voices
        characters = episode.get('characters', [])
        character_voices = self.voice_registry.map_characters_to_voices(characters)
        
        if not character_voices:
            return {"error": "No character voices mapped"}
        
        try:
            # Process each scene
            scene_results = []
            
            scenes = script.get('scenes', [])
            
            # Use concurrent processing to generate audio for all scenes
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_to_scene = {
                    executor.submit(self.generate_scene_audio, 
                                  scene, i, character_voices, episode_id, audio_dir): i 
                    for i, scene in enumerate(scenes)
                }
                
                for future in concurrent.futures.as_completed(future_to_scene):
                    scene_idx = future_to_scene[future]
                    try:
                        result = future.result()
                        scene_results.append({
                            "scene_index": scene_idx,
                            "scene_number": scenes[scene_idx].get('scene_number', scene_idx + 1),
                            "success": result.get("success", False),
                            "audio_file": result.get("audio_file"),
                            "duration": result.get("duration", 0)
                        })
                    except Exception as e:
                        logger.error(f"Error generating audio for scene {scene_idx}: {e}")
                        scene_results.append({
                            "scene_index": scene_idx,
                            "scene_number": scenes[scene_idx].get('scene_number', scene_idx + 1),
                            "success": False,
                            "error": str(e)
                        })
            
            # Sort scene results by scene index
            scene_results.sort(key=lambda r: r.get("scene_index", 0))
            
            # Create intro and outro segments (with narration and music)
            intro_file = self._create_intro_segment(episode_id)
            outro_file = self._create_outro_segment()
            
            # Assemble full episode
            episode_file = self._assemble_episode(
                episode_id, 
                scene_results, 
                intro_file, 
                outro_file, 
                audio_dir
            )
            
            # Generate file with generation metadata
            generation_meta = {
                "generated_at": time.time(),
                "episode_id": episode_id,
                "title": episode.get('title', 'Unknown'),
                "scenes_generated": len(scene_results),
                "scenes_successful": sum(1 for r in scene_results if r.get("success", False)),
                "total_duration": sum(r.get("duration", 0) for r in scene_results),
                "full_episode_file": str(episode_file) if episode_file else None
            }
            
            meta_file = audio_dir / "generation_metadata.json"
            with open(meta_file, 'w') as f:
                json.dump(generation_meta, f, indent=2)
            
            # Update episode with audio info
            episode['audio'] = {
                "generated_at": generation_meta["generated_at"],
                "duration": generation_meta["total_duration"],
                "file_path": str(episode_file) if episode_file else None
            }
            
            with open(episode_dir / "structure.json", 'w') as f:
                json.dump(episode, f, indent=2)
            
            return generation_meta
        
        except Exception as e:
            logger.exception(f"Error generating episode audio: {e}")
            return {"error": f"Error generating episode audio: {str(e)}"}
    
    def generate_scene_audio(self, scene: Dict[str, Any], scene_index: int,
                           character_voices: Dict[str, str], episode_id: str,
                           audio_dir: Path) -> Dict[str, Any]:
        """Generate audio for a single scene.
        
        Args:
            scene: Scene data
            scene_index: Index of the scene
            character_voices: Mapping of character names to voice IDs
            episode_id: ID of the episode
            audio_dir: Directory for audio output
        
        Returns:
            Dictionary with scene audio results
        """
        # Create scene directory
        scene_dir = audio_dir / f"scene_{scene_index:02d}"
        scene_dir.mkdir(exist_ok=True)
        
        # Create temp directory for line audio
        temp_dir = scene_dir / "temp"
        temp_dir.mkdir(exist_ok=True)
        
        # Process each line in the scene
        line_clips = []
        
        try:
            for i, line in enumerate(scene.get('lines', [])):
                clip = self._process_line(line, i, scene_dir, temp_dir, character_voices)
                if clip:
                    line_clips.append(clip)
            
            # Add scene ambience
            ambience_clip = self._add_scene_ambience(scene, scene_dir)
            
            # Mix all clips together
            output_file = scene_dir / "scene_audio.mp3"
            mixed_duration = self._mix_scene_audio(line_clips, ambience_clip, output_file)
            
            return {
                "success": True,
                "audio_file": str(output_file),
                "duration": mixed_duration
            }
        
        except Exception as e:
            logger.error(f"Error generating scene audio: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _process_line(self, line: Dict[str, Any], line_index: int, 
                     scene_dir: Path, temp_dir: Path,
                     character_voices: Dict[str, str]) -> Optional[AudioClip]:
        """Process a single line to generate audio.
        
        Args:
            line: Line data
            line_index: Index of the line
            scene_dir: Directory for scene audio
            temp_dir: Directory for temporary audio files
            character_voices: Mapping of character names to voice IDs
        
        Returns:
            AudioClip or None if processing failed
        """
        line_type = line.get('type', 'unknown')
        content = line.get('content', '')
        
        if not content:
            return None
        
        try:
            if line_type == 'dialogue':
                # Script uses 'speaker' field, but fall back to 'character' for compatibility
                character = line.get('speaker', line.get('character', ''))
                if not character:
                    logger.warning(f"Empty speaker field in dialogue line {line_index}")
                    return None
                return self._generate_character_audio(
                    character, content, line_index, temp_dir, character_voices
                )
            
            elif line_type == 'narration':
                return self._generate_narrator_audio(content, line_index, temp_dir)
            
            elif line_type == 'sound_effect':
                return self._get_sound_effect(content, line_index, scene_dir)
            
            elif line_type == 'description':
                # No audio for descriptions unless explicitly requested
                return None
            
            else:
                logger.warning(f"Unknown line type: {line_type}")
                return None
        
        except Exception as e:
            logger.error(f"Error processing line {line_index}: {e}")
            return None
    
    def _generate_character_audio(self, character: str, content: str, 
                                line_index: int, temp_dir: Path,
                                character_voices: Dict[str, str]) -> Optional[AudioClip]:
        """Generate audio for character dialogue.
        
        Args:
            character: Character name or role
            content: Dialogue content
            line_index: Index of the line
            temp_dir: Directory for temporary audio files
            character_voices: Mapping of character names to voice IDs
        
        Returns:
            AudioClip or None if generation failed
        """
        # Extract role from character name if it contains extra info (e.g., "CAPTAIN T'LARA" -> "COMMANDING OFFICER")
        # Also handle special cases like "KAI (V.O.)" -> narrator
        original_character = character
        if "(V.O.)" in character or "(VO)" in character:
            # Voice-over characters, use narrator voice
            character = "narrator"
        elif "CAPTAIN" in character.upper() or "COMMANDING OFFICER" in character.upper():
            character = "COMMANDING OFFICER"
        elif "SCIENCE OFFICER" in character.upper():
            character = "SCIENCE OFFICER"
        elif "SECURITY OFFICER" in character.upper():
            character = "SECURITY OFFICER"
        elif "COMMUNICATIONS SPECIALIST" in character.upper():
            character = "COMMUNICATIONS SPECIALIST"
        elif "CHIEF MEDICAL OFFICER" in character.upper() or "MEDICAL OFFICER" in character.upper():
            character = "CHIEF MEDICAL OFFICER"
        elif "KAI" in character.upper():
            # Kai is a Bajoran religious leader, use narrator voice
            character = "narrator"
        
        # Map role to character name if needed
        if character in self.role_to_character:
            character = self.role_to_character[character]
        elif character == "narrator":
            # Narrator is already the character name, keep it
            pass
        else:
            # Try the original character name
            character = original_character
        
        # Normalize character name to lowercase for voice_config.json lookup
        character_key = character.lower().replace(' ', '_').replace("'", "")
        # Also try with just lowercase
        character_key_simple = character.lower()
        
        # Get voice config from voice_config.json
        voice_config = None
        if self.voice_config and 'characters' in self.voice_config:
            # Try full key first (e.g., "aria_t_vel")
            if character_key in self.voice_config['characters']:
                voice_config = self.voice_config['characters'][character_key]
            # Try simple lowercase (e.g., "aria")
            elif character_key_simple in self.voice_config['characters']:
                voice_config = self.voice_config['characters'][character_key_simple]
            # Try original character name
            elif character in self.voice_config['characters']:
                voice_config = self.voice_config['characters'][character]
        
        if not voice_config:
            logger.error(f"No voice config found for character: {character} (tried keys: {character_key}, {character_key_simple}, {character})")
            return None
        
        try:
            # Clean text to avoid synthesis issues
            content = content.replace('"', '').replace('...', '…')
            
            # Generate audio file name
            safe_character = ''.join(c for c in character.lower().replace(' ', '_') if c.isalnum() or c == '_')
            audio_file = temp_dir / f"line_{line_index:03d}_{safe_character}.wav"
            
            # Use ElevenLabs directly (since we're configured for ElevenLabs only)
            if not self.client:
                logger.error("ElevenLabs client not initialized (no API key)")
                return None
            
            eleven_id = voice_config.get('eleven_id')
            if not eleven_id:
                logger.error(f"No ElevenLabs ID for character: {character}")
                return None
            
            # Generate speech directly using ElevenLabs API
            try:
                from elevenlabs import VoiceSettings
                
                # Generate audio using ElevenLabs text_to_speech API
                audio_chunks = self.client.text_to_speech.convert(
                    voice_id=eleven_id,
                    text=content,
                    model_id="eleven_multilingual_v2",
                    voice_settings=VoiceSettings(
                        stability=0.5,
                        similarity_boost=0.75,
                        style=0.0,
                        use_speaker_boost=True
                    )
                )
                
                # Write audio chunks to file
                with open(audio_file, 'wb') as f:
                    for chunk in audio_chunks:
                        f.write(chunk)
                
                logger.info(f"Generated with ElevenLabs: {audio_file}")
                
            except Exception as e:
                logger.error(f"ElevenLabs TTS generation failed: {e}")
                return None
            
            # Get audio duration using ffmpeg
            probe = ffmpeg.probe(str(audio_file))
            duration = float(probe['format']['duration'])
            
            return AudioClip(
                path=str(audio_file),
                type='dialogue',
                duration=duration,
                character=character,
                line_index=line_index
            )
        
        except Exception as e:
            logger.error(f"Error generating character audio for {character}: {e}")
            return None
    
    def _generate_narrator_audio(self, content: str, line_index: int, 
                               temp_dir: Path) -> Optional[AudioClip]:
        """Generate audio for narrator lines.
        
        Args:
            content: Narration content
            line_index: Index of the line
            temp_dir: Directory for temporary audio files
        
        Returns:
            AudioClip or None if generation failed
        """
        if not self.elevenlabs:
            logger.error("ElevenLabs client not initialized (no API key)")
            return None
        
        try:
            # Generate audio file name
            audio_file = temp_dir / f"line_{line_index:03d}_narrator.mp3"
            
            # Try to get narrator voice
            voice_id = None
            narrator_voices = self.voice_registry.find_voices_by_description("narrator deep authoritative", limit=1)
            
            if narrator_voices:
                voice_id = narrator_voices[0].get('voice_registry_id')
            else:
                # Fallback to any available voice
                voices = self.voice_registry.list_voices()
                if voices:
                    voice_id = voices[0].get('voice_registry_id')
            
            if not voice_id:
                logger.error("No voice available for narrator")
                return None
            
            # Generate speech
            audio_data = self.voice_registry.generate_speech(
                text=content,
                voice_identifier=voice_id,
                output_path=str(audio_file)
            )
            
            # Get audio duration using ffmpeg
            probe = ffmpeg.probe(str(audio_file))
            duration = float(probe['format']['duration'])
            
            return AudioClip(
                path=str(audio_file),
                type='narration',
                duration=duration,
                line_index=line_index
            )
        
        except Exception as e:
            logger.error(f"Error generating narrator audio: {e}")
            return None
    
    def _get_sound_effect(self, description: str, line_index: int, 
                        scene_dir: Path) -> Optional[AudioClip]:
        """Find or generate a sound effect based on description.
        
        First checks for existing files in assets, then generates using ElevenLabs
        if not found. Generated effects are cached for future use.
        
        Args:
            description: Sound effect description
            line_index: Index of the line
            scene_dir: Directory for scene audio
        
        Returns:
            AudioClip or None if generation fails
        """
        # Clean description to create a search key
        search_key = description.lower().replace(' ', '_').replace('.', '').replace(',', '')
        
        # Look for matching sound effect in assets
        for ext in ['mp3', 'wav']:
            matches = list(self.sound_effects_dir.glob(f"*{search_key}*.{ext}"))
            if matches:
                # Use first match
                effect_file = matches[0]
                
                try:
                    # Get audio duration using ffmpeg
                    probe = ffmpeg.probe(str(effect_file))
                    duration = float(probe['format']['duration'])
                    
                    # Copy to scene directory
                    dest_file = scene_dir / f"sfx_{line_index:03d}.{ext}"
                    with open(effect_file, 'rb') as src:
                        with open(dest_file, 'wb') as dst:
                            dst.write(src.read())
                    
                    logger.info(f"Using existing sound effect: {effect_file.name}")
                    return AudioClip(
                        path=str(dest_file),
                        type='sound_effect',
                        duration=duration,
                        line_index=line_index,
                        volume=1.2  # Slightly louder than dialogue
                    )
                
                except Exception as e:
                    logger.error(f"Error processing sound effect: {e}")
        
        # No existing file found - generate using ElevenLabs
        if not self.client:
            logger.warning("ElevenLabs client not available for sound effect generation")
            return None
        
        try:
            logger.info(f"Generating sound effect with ElevenLabs: {description}")
            
            # Generate sound effect using ElevenLabs API
            audio_chunks = self.client.text_to_sound_effects.convert(
                text=description,
                output_format="mp3_44100_128",
                duration_seconds=2.0,  # Default 2 seconds for most effects
                prompt_influence=0.5  # Balance between prompt adherence and variety
            )
            
            # Save to assets directory for reuse (cache)
            cached_file = self.sound_effects_dir / f"{search_key}.mp3"
            with open(cached_file, 'wb') as f:
                for chunk in audio_chunks:
                    f.write(chunk)
            
            logger.info(f"Generated and cached sound effect: {cached_file.name}")
            
            # Get audio duration using ffmpeg
            probe = ffmpeg.probe(str(cached_file))
            duration = float(probe['format']['duration'])
            
            # Copy to scene directory
            dest_file = scene_dir / f"sfx_{line_index:03d}.mp3"
            with open(cached_file, 'rb') as src:
                with open(dest_file, 'wb') as dst:
                    dst.write(src.read())
            
            return AudioClip(
                path=str(dest_file),
                type='sound_effect',
                duration=duration,
                line_index=line_index,
                volume=1.2  # Slightly louder than dialogue
            )
        
        except Exception as e:
            logger.error(f"Error generating sound effect with ElevenLabs: {e}")
            return None
    
    def _add_scene_ambience(self, scene: Dict[str, Any], scene_dir: Path) -> Optional[AudioClip]:
        """Add ambient sound for the scene.
        
        Args:
            scene: Scene data
            scene_dir: Directory for scene audio
        
        Returns:
            AudioClip or None if no ambience added
        """
        setting = scene.get('setting', '').lower()
        atmosphere = scene.get('atmosphere', '').lower()
        
        # Setting-based ambience keywords
        ambience_mapping = {
            'bridge': ['bridge', 'starship_bridge', 'command_center'],
            'space': ['space', 'vacuum', 'stars'],
            'planet': ['planet', 'alien_world', 'nature'],
            'engine room': ['engine_room', 'machinery', 'warp_core'],
            'medical': ['sickbay', 'medical', 'hospital'],
            'corridor': ['corridor', 'hallway', 'footsteps'],
            'quarters': ['quarters', 'room', 'living_space'],
            'shuttlecraft': ['shuttle', 'small_ship', 'cockpit'],
            'transporter': ['transporter', 'teleport', 'energy'],
            'battle': ['battle', 'combat', 'weapons'],
            'forest': ['forest', 'woods', 'nature'],
            'city': ['city', 'urban', 'crowd'],
            'underwater': ['underwater', 'ocean', 'bubbles']
        }
        
        # Choose keywords based on setting
        keywords = []
        for key, values in ambience_mapping.items():
            if any(term in setting for term in key.split()):
                keywords.extend(values)
                break
        
        # Add atmosphere-based keywords
        if 'tense' in atmosphere or 'danger' in atmosphere:
            keywords.append('tension')
        elif 'quiet' in atmosphere or 'calm' in atmosphere:
            keywords.append('quiet')
        elif 'busy' in atmosphere or 'active' in atmosphere:
            keywords.append('activity')
        
        # No keywords found
        if not keywords:
            keywords = ['background', 'ambience']
        
        # Look for matching ambience in assets
        for keyword in keywords:
            matches = list(self.ambience_dir.glob(f"*{keyword}*.mp3")) + list(self.ambience_dir.glob(f"*{keyword}*.wav"))
            if matches:
                # Use first match
                ambience_file = matches[0]
                
                try:
                    # Get audio duration using ffmpeg
                    probe = ffmpeg.probe(str(ambience_file))
                    duration = float(probe['format']['duration'])
                    
                    # Copy to scene directory
                    dest_file = scene_dir / f"ambience.{ambience_file.suffix}"
                    with open(ambience_file, 'rb') as src:
                        with open(dest_file, 'wb') as dst:
                            dst.write(src.read())
                    
                    logger.info(f"Using existing ambience: {ambience_file.name}")
                    return AudioClip(
                        path=str(dest_file),
                        type='ambience',
                        duration=duration,
                        volume=0.3  # Lower volume for background
                    )
                
                except Exception as e:
                    logger.error(f"Error processing ambience: {e}")
        
        # No existing file found - generate using ElevenLabs
        if not self.client:
            logger.warning("ElevenLabs client not available for ambience generation")
            return None
        
        try:
            # Create description from keywords for generation
            ambience_description = f"{', '.join(keywords[:3])}, ambient background"
            logger.info(f"Generating ambience with ElevenLabs: {ambience_description}")
            
            # Generate ambience using ElevenLabs API (longer duration for more natural looping)
            audio_chunks = self.client.text_to_sound_effects.convert(
                text=ambience_description,
                output_format="mp3_44100_128",
                duration_seconds=20.0,  # 20 seconds for more natural loops (max is 22)
                prompt_influence=0.4  # Lower influence for more variety in loops
            )
            
            # Save to assets directory for reuse (cache)
            cache_key = '_'.join(keywords[:2]) if keywords else 'background'
            cached_file = self.ambience_dir / f"{cache_key}.mp3"
            with open(cached_file, 'wb') as f:
                for chunk in audio_chunks:
                    f.write(chunk)
            
            logger.info(f"Generated and cached ambience: {cached_file.name}")
            
            # Get audio duration using ffmpeg
            probe = ffmpeg.probe(str(cached_file))
            duration = float(probe['format']['duration'])
            
            # Copy to scene directory
            dest_file = scene_dir / f"ambience.mp3"
            with open(cached_file, 'rb') as src:
                with open(dest_file, 'wb') as dst:
                    dst.write(src.read())
            
            return AudioClip(
                path=str(dest_file),
                type='ambience',
                duration=duration,
                volume=0.3  # Lower volume for background
            )
        
        except Exception as e:
            logger.error(f"Error generating ambience with ElevenLabs: {e}")
            return None
    
    def _mix_scene_audio(self, line_clips: List[AudioClip], 
                        ambience_clip: Optional[AudioClip],
                        output_file: Path) -> float:
        """Mix scene audio clips together.
        
        Args:
            line_clips: List of line audio clips
            ambience_clip: Optional ambience audio clip
            output_file: Output file path
        
        Returns:
            Duration of the mixed audio
        """
        if not line_clips:
            logger.warning("No audio clips to mix")
            return 0.0
        
        # Sort clips by line index
        line_clips.sort(key=lambda c: c.line_index if c.line_index is not None else 999)
        
        # Initialize ffmpeg input streams
        inputs = []
        
        # Calculate total duration based on line clips
        total_duration = sum(clip.duration for clip in line_clips) + 1.0  # Add 1 second padding
        
        # Add silence between clips
        silence_duration = 0.5  # Half-second silence between lines
        
        try:
            # Create a silence file for padding
            silence_file = output_file.parent / "silence.mp3"
            (
                ffmpeg
                .input('anullsrc=r=44100:cl=stereo', f='lavfi', t=silence_duration)
                .output(str(silence_file), ar=44100, ac=2, c='mp3', b='128k')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            # Process clips with fade effects (especially for sound effects)
            processed_clips = []
            temp_dir = output_file.parent / "processed"
            temp_dir.mkdir(exist_ok=True)
            
            for i, clip in enumerate(line_clips):
                clip_path = Path(clip.path)
                processed_path = temp_dir / f"processed_{i:03d}.mp3"
                
                # Add fade in/out for sound effects to prevent abrupt cuts
                if clip.type == 'sound_effect':
                    fade_in = 0.05  # 50ms fade in
                    fade_out = 0.2  # 200ms fade out for smooth stop
                    clip_duration = clip.duration
                    
                    # Ensure fade out doesn't exceed clip duration
                    if clip_duration <= fade_out:
                        fade_out = clip_duration * 0.3  # Use 30% of duration if too short
                    
                    # Apply fade in/out to sound effects
                    (
                        ffmpeg
                        .input(str(clip_path))
                        .filter('afade', t='in', st=0, d=fade_in)
                        .filter('afade', t='out', st=max(0, clip_duration - fade_out), d=fade_out)
                        .output(str(processed_path), acodec='libmp3lame', ar=44100, b='192k')
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
                    processed_clips.append(processed_path)
                else:
                    # For dialogue/narration, use original path (no fade needed)
                    processed_clips.append(clip_path)
            
            # Build concatenation file list with processed clips
            concat_file = output_file.parent / "concat.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                # Add each processed clip followed by silence
                for clip_path in processed_clips:
                    abs_path = Path(clip_path).resolve()
                    f.write(f"file '{abs_path.as_posix()}'\n")
                    f.write(f"file '{os.path.abspath(silence_file)}'\n")
            
            # Concatenate clips with silence between (re-encode for compatibility)
            dialogue_file = output_file.parent / "dialogue.mp3"
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(str(dialogue_file), acodec='libmp3lame', ar=44100, b='192k')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            # If we have ambience, mix it with the dialogue
            if ambience_clip:
                # If ambience is shorter than total duration, loop it seamlessly
                if ambience_clip.duration < total_duration:
                    ambience_path = Path(ambience_clip.path).resolve()
                    looped_ambience = output_file.parent / "looped_ambience.mp3"
                    
                    # Use seamless looping with aloop filter for natural sound
                    (
                        ffmpeg
                        .input(str(ambience_path))
                        .filter('aloop', loop=-1, size=2e+09)  # Loop infinitely until cut by duration
                        .output(str(looped_ambience), t=str(total_duration), acodec='libmp3lame', ar=44100, b='128k')
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
                    
                    # Mix dialogue and looped ambience
                    dialogue_stream = ffmpeg.input(str(dialogue_file))
                    ambience_stream = ffmpeg.input(str(looped_ambience))
                    (
                        ffmpeg.output(
                            dialogue_stream,
                            ambience_stream,
                            str(output_file),
                            filter_complex=f'[0:a]volume=1.0[a0];[1:a]volume={ambience_clip.volume}[a1];[a0][a1]amix=inputs=2:duration=first',
                            ar=44100
                        )
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
                else:
                    # Mix dialogue and ambience directly
                    ambience_path = Path(ambience_clip.path).resolve()
                    dialogue_stream = ffmpeg.input(str(dialogue_file))
                    ambience_stream = ffmpeg.input(str(ambience_path))
                    (
                        ffmpeg.output(
                            dialogue_stream,
                            ambience_stream,
                            str(output_file),
                            filter_complex=f'[0:a]volume=1.0[a0];[1:a]volume={ambience_clip.volume}[a1];[a0][a1]amix=inputs=2:duration=first',
                            ar=44100
                        )
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
            else:
                # Just use the dialogue file as output
                (
                    ffmpeg
                    .input(str(dialogue_file))
                    .output(str(output_file), ar=44100)
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
            
            # Get final output duration
            probe = ffmpeg.probe(str(output_file))
            final_duration = float(probe['format']['duration'])
            
            return final_duration
        
        except Exception as e:
            logger.error(f"Error mixing scene audio: {e}")
            return 0.0
    
    def _generate_intro_narration(self, episode_id: str) -> Optional[Path]:
        """Generate intro narration with episode information.
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            Path to the intro narration audio file or None if failed
        """
        try:
            # Get episode data
            episode = get_episode(episode_id)
            if not episode:
                logger.error(f"Episode not found: {episode_id}")
                return None
            
            # Extract episode information
            episode_number = episode.get('episode_number', 1)
            created_at = episode.get('created_at', time.time())
            
            # Format date from timestamp
            from datetime import datetime
            date_str = datetime.fromtimestamp(created_at).strftime("%B %d, %Y")
            
            # Create narration text (TNG style)
            narration_text = (
                f"This is the logs of the Celestial Temple. "
                f"Journeys through the Gamma Quadrant. "
                f"Star date: {date_str}. "
                f"Episode number {episode_number}."
            )
            
            # Get narrator voice ID from voice config
            narrator_config = self.voice_config.get('characters', {}).get('narrator', {})
            narrator_voice_id = narrator_config.get('eleven_id')
            
            if not narrator_voice_id:
                logger.error("No narrator voice ID found in voice config")
                return None
            
            # Generate narration audio
            intro_narration_file = self.assets_dir / "music" / "intro_narration.mp3"
            intro_narration_file.parent.mkdir(exist_ok=True, parents=True)
            
            # Generate speech using ElevenLabs
            if not self.client:
                logger.error("ElevenLabs client not initialized")
                return None
            
            try:
                audio_data = self.client.text_to_speech.convert(
                    voice_id=narrator_voice_id,
                    text=narration_text,
                    model_id="eleven_multilingual_v2"
                )
                
                # Save audio file
                with open(intro_narration_file, 'wb') as f:
                    if hasattr(audio_data, '__iter__'):
                        for chunk in audio_data:
                            f.write(chunk)
                    else:
                        f.write(audio_data)
                
                logger.info(f"Generated intro narration: {intro_narration_file}")
                return intro_narration_file
                
            except Exception as e:
                logger.error(f"Error generating intro narration: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating intro narration: {e}")
            return None
    
    def _generate_outro_narration(self) -> Optional[Path]:
        """Generate outro narration.
        
        Returns:
            Path to the outro narration audio file or None if failed
        """
        try:
            # Create outro narration text
            narration_text = (
                "End of transmission. "
                "The Celestial Temple awaits our next journey through the stars."
            )
            
            # Get narrator voice ID from voice config
            narrator_config = self.voice_config.get('characters', {}).get('narrator', {})
            narrator_voice_id = narrator_config.get('eleven_id')
            
            if not narrator_voice_id:
                logger.error("No narrator voice ID found in voice config")
                return None
            
            # Generate narration audio (only generate once, reuse if exists)
            outro_narration_file = self.assets_dir / "music" / "outro_narration.mp3"
            if outro_narration_file.exists():
                logger.info(f"Reusing existing outro narration: {outro_narration_file}")
                return outro_narration_file
            
            outro_narration_file.parent.mkdir(exist_ok=True, parents=True)
            
            # Generate speech using ElevenLabs
            if not self.client:
                logger.error("ElevenLabs client not initialized")
                return None
            
            try:
                audio_data = self.client.text_to_speech.convert(
                    voice_id=narrator_voice_id,
                    text=narration_text,
                    model_id="eleven_multilingual_v2"
                )
                
                # Save audio file
                with open(outro_narration_file, 'wb') as f:
                    if hasattr(audio_data, '__iter__'):
                        for chunk in audio_data:
                            f.write(chunk)
                    else:
                        f.write(audio_data)
                
                logger.info(f"Generated outro narration: {outro_narration_file}")
                return outro_narration_file
                
            except Exception as e:
                logger.error(f"Error generating outro narration: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating outro narration: {e}")
            return None
    
    def _create_intro_segment(self, episode_id: str) -> Optional[Path]:
        """Create complete intro segment with music and narration.
        
        Note: Intro is regenerated per episode since it includes episode-specific info.
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            Path to the complete intro segment or None if failed
        """
        # Store intro in episode-specific location since it includes episode info
        episode_dir = self.episodes_dir / episode_id / "audio"
        episode_dir.mkdir(exist_ok=True, parents=True)
        intro_file = episode_dir / "intro_complete.mp3"
        
        try:
            # Generate narration
            narration_file = self._generate_intro_narration(episode_id)
            if not narration_file:
                logger.warning("Could not generate intro narration")
                narration_file = None
            
            # Look for theme music
            theme_music = None
            music_matches = list(self.music_dir.glob("*theme*.mp3")) + \
                          list(self.music_dir.glob("*intro*.mp3")) + \
                          list(self.music_dir.glob("*opening*.mp3"))
            
            if music_matches:
                theme_music = music_matches[0]
                logger.info(f"Using theme music: {theme_music}")
            
            # If we have both music and narration, use TNG style: narration first, then music
            if theme_music and narration_file:
                intro_file.parent.mkdir(exist_ok=True, parents=True)
                
                # Get narration duration
                narration_probe = ffmpeg.probe(str(narration_file))
                narration_duration = float(narration_probe['format']['duration'])
                
                # Create music segment (15-20 seconds with fade in/out)
                music_duration = 18.0  # 18 seconds of music
                music_stream = (
                    ffmpeg
                    .input(str(theme_music))
                    .filter('afade', t='in', st=0, d=2)  # 2 second fade in
                    .filter('afade', t='out', st=music_duration - 2, d=2)  # 2 second fade out
                )
                
                # Concatenate: narration first, then music (TNG style)
                concat_file = intro_file.parent / "intro_concat.txt"
                with open(concat_file, 'w', encoding='utf-8') as f:
                    f.write(f"file '{Path(narration_file).resolve().as_posix()}'\n")
                
                # Create temporary music file for concatenation
                temp_dir = self.assets_dir / "music" / "temp"
                temp_dir.mkdir(exist_ok=True, parents=True)
                music_trimmed = temp_dir / "intro_music.mp3"
                (
                    music_stream
                    .output(str(music_trimmed), t=str(music_duration), acodec='libmp3lame', ar=44100, b='192k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
                
                # Add music to concat file
                with open(concat_file, 'a', encoding='utf-8') as f:
                    f.write(f"file '{music_trimmed.resolve().as_posix()}'\n")
                
                # Concatenate narration + music
                (
                    ffmpeg
                    .input(str(concat_file), format='concat', safe=0)
                    .output(str(intro_file), acodec='libmp3lame', ar=44100, b='192k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
                
                # Cleanup
                if music_trimmed.exists():
                    music_trimmed.unlink()
                if concat_file.exists():
                    concat_file.unlink()
                
            elif narration_file:
                # Just use narration if no music
                intro_file.parent.mkdir(exist_ok=True, parents=True)
                (
                    ffmpeg
                    .input(str(narration_file))
                    .output(str(intro_file), acodec='libmp3lame', b='192k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
            elif theme_music:
                # Just use music if no narration
                intro_file.parent.mkdir(exist_ok=True, parents=True)
                # Trim to 15 seconds
                (
                    ffmpeg
                    .input(str(theme_music))
                    .filter('afade', t='in', st=0, d=1)
                    .filter('afade', t='out', st=14, d=1)
                    .output(str(intro_file), t='15', acodec='libmp3lame', b='192k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
            else:
                logger.warning("No music or narration available for intro")
                return None
            
            logger.info(f"Created complete intro segment: {intro_file}")
            return intro_file
            
        except Exception as e:
            logger.error(f"Error creating intro segment: {e}")
            return None
    
    def _create_outro_segment(self) -> Optional[Path]:
        """Create complete outro segment with music and narration.
        
        Returns:
            Path to the complete outro segment or None if failed
        """
        outro_file = self.assets_dir / "music" / "outro_complete.mp3"
        
        # Check if outro already exists (reuse it)
        if outro_file.exists():
            logger.info(f"Reusing existing outro: {outro_file}")
            return outro_file
        
        try:
            # Generate narration
            narration_file = self._generate_outro_narration()
            if not narration_file:
                logger.warning("Could not generate outro narration")
                narration_file = None
            
            # Look for theme music
            theme_music = None
            music_matches = list(self.music_dir.glob("*theme*.mp3")) + \
                          list(self.music_dir.glob("*outro*.mp3")) + \
                          list(self.music_dir.glob("*closing*.mp3"))
            
            if music_matches:
                theme_music = music_matches[0]
                logger.info(f"Using theme music: {theme_music}")
            
            # If we have both music and narration, mix them
            if theme_music and narration_file:
                # Create temp directory
                temp_dir = self.assets_dir / "music" / "temp"
                temp_dir.mkdir(exist_ok=True, parents=True)
                
                # Get durations
                narration_probe = ffmpeg.probe(str(narration_file))
                narration_duration = float(narration_probe['format']['duration'])
                
                # Trim music to match narration + fade in/out
                music_trimmed = temp_dir / "music_trimmed.mp3"
                target_duration = narration_duration + 2.0  # Add 2 seconds for fade
                (
                    ffmpeg
                    .input(str(theme_music))
                    .filter('afade', t='in', st=0, d=1)
                    .filter('afade', t='out', st=target_duration - 1, d=1)
                    .output(str(music_trimmed), t=str(target_duration), acodec='libmp3lame', b='128k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
                
                # Mix narration and music (narration louder)
                outro_file.parent.mkdir(exist_ok=True, parents=True)
                narration_stream = ffmpeg.input(str(narration_file))
                music_stream = ffmpeg.input(str(music_trimmed))
                (
                    ffmpeg.output(
                        narration_stream,
                        music_stream,
                        str(outro_file),
                        filter_complex='[0:a]volume=1.0[a0];[1:a]volume=0.3[a1];[a0][a1]amix=inputs=2:duration=first',
                        acodec='libmp3lame',
                        ar=44100,
                        b='192k'
                    )
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
                
                # Cleanup
                if music_trimmed.exists():
                    music_trimmed.unlink()
                
            elif narration_file:
                # Just use narration if no music
                outro_file.parent.mkdir(exist_ok=True, parents=True)
                (
                    ffmpeg
                    .input(str(narration_file))
                    .output(str(outro_file), acodec='libmp3lame', b='192k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
            elif theme_music:
                # Just use music if no narration
                outro_file.parent.mkdir(exist_ok=True, parents=True)
                # Trim to 10 seconds
                (
                    ffmpeg
                    .input(str(theme_music))
                    .filter('afade', t='in', st=0, d=1)
                    .filter('afade', t='out', st=9, d=1)
                    .output(str(outro_file), t='10', acodec='libmp3lame', b='192k')
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
            else:
                logger.warning("No music or narration available for outro")
                return None
            
            logger.info(f"Created complete outro segment: {outro_file}")
            return outro_file
            
        except Exception as e:
            logger.error(f"Error creating outro segment: {e}")
            return None
    
    def _add_intro_music(self, episode_id: str, audio_dir: Path) -> Optional[Path]:
        """Add intro music for the episode.
        
        Args:
            episode_id: ID of the episode
            audio_dir: Directory for audio output
        
        Returns:
            Path to the intro music file or None if failed
        """
        # Look for sci-fi intro music
        intro_matches = list(self.music_dir.glob("*intro*.mp3")) + list(self.music_dir.glob("*opening*.mp3"))
        
        if not intro_matches:
            logger.warning("No intro music found")
            return None
        
        # Use first match
        intro_file = intro_matches[0]
        
        try:
            # Copy to audio directory
            dest_file = audio_dir / "intro.mp3"
            with open(intro_file, 'rb') as src:
                with open(dest_file, 'wb') as dst:
                    dst.write(src.read())
            
            # Trim to reasonable length (15 seconds)
            trimmed_file = audio_dir / "intro_trimmed.mp3"
            (
                ffmpeg
                .input(str(dest_file))
                .output(str(trimmed_file), t='15')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            # Add fade-out
            final_intro = audio_dir / "intro_final.mp3"
            (
                ffmpeg
                .input(str(trimmed_file))
                .filter_('afade', t='out', st='12', d='3')
                .output(str(final_intro))
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            return final_intro
        
        except Exception as e:
            logger.error(f"Error processing intro music: {e}")
            return None
    
    def _add_outro_music(self, episode_id: str, audio_dir: Path) -> Optional[Path]:
        """Add outro music for the episode.
        
        Args:
            episode_id: ID of the episode
            audio_dir: Directory for audio output
        
        Returns:
            Path to the outro music file or None if failed
        """
        # Look for sci-fi outro music
        outro_matches = list(self.music_dir.glob("*outro*.mp3")) + list(self.music_dir.glob("*closing*.mp3"))
        
        if not outro_matches:
            logger.warning("No outro music found")
            return None
        
        # Use first match
        outro_file = outro_matches[0]
        
        try:
            # Copy to audio directory
            dest_file = audio_dir / "outro.mp3"
            with open(outro_file, 'rb') as src:
                with open(dest_file, 'wb') as dst:
                    dst.write(src.read())
            
            # Trim to reasonable length (10 seconds)
            trimmed_file = audio_dir / "outro_trimmed.mp3"
            (
                ffmpeg
                .input(str(dest_file))
                .output(str(trimmed_file), t='10')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            # Add fade-in
            final_outro = audio_dir / "outro_final.mp3"
            (
                ffmpeg
                .input(str(trimmed_file))
                .filter_('afade', t='in', st='0', d='2')
                .output(str(final_outro))
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            return final_outro
        
        except Exception as e:
            logger.error(f"Error processing outro music: {e}")
            return None
    
    def _assemble_episode(self, episode_id: str, scene_results: List[Dict[str, Any]],
                         intro_file: Optional[Path], outro_file: Optional[Path],
                         audio_dir: Path) -> Optional[Path]:
        """Assemble the full episode audio from scene audio files.
        
        Args:
            episode_id: ID of the episode
            scene_results: List of scene audio generation results
            intro_file: Optional intro music file
            outro_file: Optional outro music file
            audio_dir: Directory for audio output
        
        Returns:
            Path to the full episode audio file or None if failed
        """
        # Get all scene audio files
        valid_scenes = [s for s in scene_results if s.get("success", False) and s.get("audio_file")]
        
        if not valid_scenes:
            logger.error("No valid scene audio files to assemble")
            return None
        
        try:
            # Create concatenation file
            concat_file = audio_dir / "episode_concat.txt"
            with open(concat_file, 'w', encoding='utf-8') as f:
                # Add intro if available
                if intro_file and intro_file.exists():
                    abs_path = Path(intro_file).resolve()
                    f.write(f"file '{abs_path.as_posix()}'\n")
                
                # Add each scene in order (use absolute paths for ffmpeg compatibility)
                for scene in sorted(valid_scenes, key=lambda s: s.get("scene_index", 0)):
                    scene_file = scene['audio_file']
                    # Convert to Path and resolve to absolute path
                    scene_path = Path(scene_file).resolve()
                    # Verify file exists
                    if not scene_path.exists():
                        logger.warning(f"Scene audio file not found: {scene_path}")
                        continue
                    # Use forward slashes for ffmpeg compatibility (works on Windows too)
                    f.write(f"file '{scene_path.as_posix()}'\n")
                
                # Add outro if available
                if outro_file and outro_file.exists():
                    abs_path = Path(outro_file).resolve()
                    f.write(f"file '{abs_path.as_posix()}'\n")
            
            # Concatenate all files (re-encode to ensure compatibility)
            output_file = audio_dir / "full_episode.mp3"
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(str(output_file), acodec='libmp3lame', ar=44100, b='192k')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            # Add metadata to the file
            try:
                episode = get_episode(episode_id)
                if episode:
                    title = episode.get('title', f"Episode {episode.get('episode_number', 'Unknown')}")
                    series = episode.get('series', 'Main Series')
                    
                    (
                        ffmpeg
                        .input(str(output_file))
                        .output(
                            str(output_file) + ".temp.mp3",
                            **{
                                'metadata:g:0': f"title={title}",
                                'metadata:g:1': f"album={series}",
                                'metadata:g:2': f"artist=Stardock Podium AI",
                                'metadata:g:3': f"comment=Generated by Stardock Podium"
                            }
                        )
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
                    
                    # Replace original file
                    os.replace(str(output_file) + ".temp.mp3", str(output_file))
            except Exception as e:
                logger.error(f"Error adding metadata to episode: {e}")
            
            return output_file
        
        except Exception as e:
            logger.error(f"Error assembling episode audio: {e}")
            return None
    
    def generate_single_audio(self, text: str, voice_identifier: str, 
                            output_file: Optional[str] = None) -> Tuple[bytes, float]:
        """Generate audio for a single text passage.
        
        Args:
            text: Text to convert to speech
            voice_identifier: Voice registry ID or character name
            output_file: Optional path to save the audio file
        
        Returns:
            Tuple of (audio data, duration)
        """
        if not self.elevenlabs:
            raise RuntimeError("ElevenLabs client not initialized (no API key)")
        
        # Generate speech
        audio_data = self.voice_registry.generate_speech(
            text=text,
            voice_identifier=voice_identifier,
            output_path=output_file
        )
        
        # Get duration
        if output_file:
            probe = ffmpeg.probe(output_file)
            duration = float(probe['format']['duration'])
        else:
            # Write to a temporary file to get duration
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(audio_data)
            
            probe = ffmpeg.probe(tmp_path)
            duration = float(probe['format']['duration'])
            
            # Clean up temporary file
            os.unlink(tmp_path)
        
        return audio_data, duration

# Singleton instance
_audio_pipeline = None

def get_audio_pipeline() -> AudioPipeline:
    """Get the AudioPipeline singleton instance."""
    global _audio_pipeline
    
    if _audio_pipeline is None:
        _audio_pipeline = AudioPipeline()
    
    return _audio_pipeline

def generate_episode_audio(episode_id: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Generate audio for a complete episode.
    
    Args:
        episode_id: ID of the episode
        options: Audio generation options
    
    Returns:
        Dictionary with generation results
    """
    if options is None:
        options = {}
    
    pipeline = get_audio_pipeline()
    return pipeline.generate_episode_audio(episode_id, options)

def generate_audio(text: str, voice_identifier: str, 
                  output_file: Optional[str] = None) -> Tuple[bytes, float]:
    """Generate audio for a text passage.
    
    Args:
        text: Text to convert to speech
        voice_identifier: Voice registry ID or character name
        output_file: Optional path to save the audio file
    
    Returns:
        Tuple of (audio data, duration)
    """
    pipeline = get_audio_pipeline()
    return pipeline.generate_single_audio(text, voice_identifier, output_file)