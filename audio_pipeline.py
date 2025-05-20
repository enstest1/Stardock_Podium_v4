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
        
        # Role to character mapping
        self.role_to_character = {
            "COMMANDING OFFICER": "Aria T'Vel",
            "SCIENCE OFFICER": "Jalen",
            "SECURITY OFFICER": "Naren",
            "CHIEF MEDICAL OFFICER": "Elara",
            "COMMUNICATIONS SPECIALIST": "Sarik"
        }
    
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
            
            # Add intro and outro music
            intro_file = self._add_intro_music(episode_id, audio_dir)
            outro_file = self._add_outro_music(episode_id, audio_dir)
            
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
                character = line.get('character', '')
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
        # Map role to character name if needed
        if character in self.role_to_character:
            character = self.role_to_character[character]
        
        # Get voice config
        voice_config = self.voice_registry.get_voice(character)
        if not voice_config:
            logger.error(f"No voice config found for character: {character}")
            return None
        
        try:
            # Clean text to avoid synthesis issues
            content = content.replace('"', '').replace('...', '…')
            
            # Generate audio file name
            safe_character = ''.join(c for c in character.lower().replace(' ', '_') if c.isalnum() or c == '_')
            audio_file = temp_dir / f"line_{line_index:03d}_{safe_character}.wav"
            
            # Try Coqui TTS first
            try:
                from tts_engine import get_coqui_engine
                coqui_engine = get_coqui_engine()
                coqui_engine.synth(
                    text=content,
                    speaker_wav=voice_config.get('speaker_wav'),
                    language=voice_config.get('language', 'en'),
                    output_path=str(audio_file)
                )
                logger.info(f"Generated with Coqui: {audio_file}")
            except Exception as e:
                logger.warning(f"Coqui TTS failed: {e}")
                
                # Try ElevenLabs as fallback
                if not self.elevenlabs:
                    logger.error("ElevenLabs client not initialized (no API key)")
                    return None
                
                eleven_id = voice_config.get('eleven_id')
                if not eleven_id:
                    logger.error(f"No ElevenLabs ID for character: {character}")
                    return None
                
                # Generate speech
                audio_data = self.voice_registry.generate_speech(
                    text=content,
                    voice_identifier=eleven_id,
                    output_path=str(audio_file)
                )
                logger.info(f"Generated with ElevenLabs: {audio_file}")
            
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
        
        Args:
            description: Sound effect description
            line_index: Index of the line
            scene_dir: Directory for scene audio
        
        Returns:
            AudioClip or None if not found
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
                    
                    return AudioClip(
                        path=str(dest_file),
                        type='sound_effect',
                        duration=duration,
                        line_index=line_index,
                        volume=1.2  # Slightly louder than dialogue
                    )
                
                except Exception as e:
                    logger.error(f"Error processing sound effect: {e}")
            
        # If no matching sound effect found
        logger.warning(f"No sound effect found for: {description}")
        
        # TODO: Implement synthesized sound effect option when no match found
        
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
                    
                    return AudioClip(
                        path=str(dest_file),
                        type='ambience',
                        duration=duration,
                        volume=0.3  # Lower volume for background
                    )
                
                except Exception as e:
                    logger.error(f"Error processing ambience: {e}")
        
        # If no matching ambience found
        logger.warning(f"No ambience found for setting: {setting}")
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
            
            # Build concatenation file list
            concat_file = output_file.parent / "concat.txt"
            with open(concat_file, 'w') as f:
                # Add each clip followed by silence
                for clip in line_clips:
                    f.write(f"file '{os.path.abspath(clip.path)}'\n")
                    f.write(f"file '{os.path.abspath(silence_file)}'\n")
            
            # Concatenate clips with silence between
            dialogue_file = output_file.parent / "dialogue.mp3"
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(str(dialogue_file), c='copy')
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            
            # If we have ambience, mix it with the dialogue
            if ambience_clip:
                # If ambience is shorter than total duration, loop it
                if ambience_clip.duration < total_duration:
                    looped_ambience = output_file.parent / "looped_ambience.mp3"
                    loop_count = int(total_duration / ambience_clip.duration) + 1
                    
                    # Create concat file for looping
                    loop_concat = output_file.parent / "loop_concat.txt"
                    with open(loop_concat, 'w') as f:
                        for _ in range(loop_count):
                            f.write(f"file '{ambience_clip.path}'\n")
                    
                    # Generate looped ambience
                    (
                        ffmpeg
                        .input(str(loop_concat), format='concat', safe=0)
                        .output(str(looped_ambience), c='copy', t=str(total_duration))
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
                    
                    # Mix dialogue and looped ambience
                    (
                        ffmpeg
                        .input(str(dialogue_file))
                        .input(str(looped_ambience))
                        .filter_complex(f'[0:a][1:a]amix=inputs=2:duration=first:weights={1}\\\ {ambience_clip.volume}')
                        .output(str(output_file), ar=44100)
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
                else:
                    # Mix dialogue and ambience directly
                    (
                        ffmpeg
                        .input(str(dialogue_file))
                        .input(str(ambience_clip.path))
                        .filter_complex(f'[0:a][1:a]amix=inputs=2:duration=first:weights={1}\\\ {ambience_clip.volume}')
                        .output(str(output_file), ar=44100)
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
            with open(concat_file, 'w') as f:
                # Add intro if available
                if intro_file and intro_file.exists():
                    f.write(f"file '{intro_file}'\n")
                
                # Add each scene in order
                for scene in sorted(valid_scenes, key=lambda s: s.get("scene_index", 0)):
                    f.write(f"file '{scene['audio_file']}'\n")
                
                # Add outro if available
                if outro_file and outro_file.exists():
                    f.write(f"file '{outro_file}'\n")
            
            # Concatenate all files
            output_file = audio_dir / "full_episode.mp3"
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(str(output_file), c='copy')
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