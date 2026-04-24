#!/usr/bin/env python
"""
Audio Pipeline Module for Stardock Podium.

This module handles the audio generation, processing, and assembly for podcast
episodes, including voice synthesis, sound effects, and mixing.
"""

import os
import re
import json
import logging
import subprocess
import time
import uuid
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple
import concurrent.futures
import asyncio
import threading
from dataclasses import dataclass

# ElevenLabs is optional; dialogue uses Kokoro via dialogue_engine.
try:
    from elevenlabs import ElevenLabs
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
    _ELEVEN_IMPORT_OK = True
except ImportError:
    ElevenLabs = None  # type: ignore
    ElevenLabsClient = None  # type: ignore
    _ELEVEN_IMPORT_OK = False

try:
    import ffmpeg
except ImportError:
    logging.error("ffmpeg-python not found. Please install it with: pip install ffmpeg-python")
    raise

# Local imports
from dialogue_engine import (
    get_dialogue_synthesizer,
    resolve_character_voice_config,
)
from needed_audio_report import NeededAudioTracker, default_report_path
from script_editor import load_episode_script
from voice_registry import get_voice_registry, get_voice, map_characters_to_voices
from story_structure import get_episode
from config.paths import EPISODES_DIR, VOICES_DIR

# Setup logging
logger = logging.getLogger(__name__)

# Kokoro line WAVs are 24 kHz mono float/PCM. Interleaving them in ffmpeg's
# concat demuxer with *different* format segments (e.g. 44.1 kHz stereo MP3
# silence) forces a resample+re-encode at every line boundary and produces
# zipper noise, high-frequency hash, and "buzzing" in the final MP3.
_LINE_SAMPLE_RATE = 24000

# Pause between dialogue lines (seconds). The old 0.5s gap sounded like a
# distinct "clip" of dead air after every line. Override with env, e.g.
# STARDOCK_LINE_GAP_SEC=0 for back-to-back lines.
_LINE_GAP_SEC = float(os.environ.get('STARDOCK_LINE_GAP_SEC', '0.09'))

# Glob patterns under assets/music/ — include .wav (themes are often WAV).
# Include *Theme* — Linux globs are case-sensitive, so *theme*.wav misses
# Cosmic_Odyssey_Main_Theme.wav. Never treat *narration* as theme music.
_INTRO_MUSIC_PATTERNS = (
    '*theme*.mp3', '*theme*.wav', '*Theme*.mp3', '*Theme*.wav',
    '*intro*.mp3', '*intro*.wav',
    '*opening*.mp3', '*opening*.wav',
)
_OUTRO_MUSIC_PATTERNS = (
    '*theme*.mp3', '*theme*.wav', '*Theme*.mp3', '*Theme*.wav',
    '*outro*.mp3', '*outro*.wav',
    '*closing*.mp3', '*closing*.wav',
)

# Preferred theme filenames (place under assets/music/). Env overrides below.
_INTRO_THEME_FILE = 'Cosmic_Odyssey_Main_Theme_2025-12-25T222447.wav'
_OUTRO_THEME_FILE = 'Cosmic_Odyssey_Main_Theme_2025-12-27T064552.wav'
_INTRO_MUSIC_DURATION_SEC = float(
    os.environ.get('STARDOCK_INTRO_MUSIC_SEC', '60'))
_INTRO_NARRATION_DELAY_SEC = float(
    os.environ.get('STARDOCK_INTRO_NARRATION_START_SEC', '45'))


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
    
    def __init__(self, episodes_dir: Optional[str] = None, assets_dir: str = "assets"):
        """Initialize the audio pipeline.

        Args:
            episodes_dir: Directory for episode data. When None (the default),
                resolves via ``config.paths.EPISODES_DIR`` which honors the
                ``STARDOCK_EPISODES_DIR`` env var for cloud deployments.
            assets_dir: Directory for audio assets (sound effects / music /
                ambience). Stays repo-local — these are part of the codebase.
        """
        self.episodes_dir = Path(episodes_dir) if episodes_dir else EPISODES_DIR
        self.assets_dir = Path(assets_dir)
        
        # Create asset directories if they don't exist
        self.sound_effects_dir = self.assets_dir / "sound_effects"
        self.music_dir = self.assets_dir / "music"
        self.ambience_dir = self.assets_dir / "ambience"
        
        for directory in [self.sound_effects_dir, self.music_dir, self.ambience_dir]:
            directory.mkdir(exist_ok=True, parents=True)
        
        # Initialize voice registry
        self.voice_registry = get_voice_registry()

        # Optional ElevenLabs (legacy / unused by default dialogue path)
        self.api_key = os.environ.get('ELEVENLABS_API_KEY')
        self.elevenlabs = None
        self.client = None
        if _ELEVEN_IMPORT_OK and self.api_key:
            try:
                self.elevenlabs = ElevenLabs(api_key=self.api_key)
                self.client = ElevenLabsClient(api_key=self.api_key)
            except Exception as e:
                logger.warning('ElevenLabs client init failed: %s', e)
        elif not _ELEVEN_IMPORT_OK:
            logger.debug('elevenlabs package not installed; using Kokoro only.')

        self._dialogue = get_dialogue_synthesizer()
        self._needed_tracker: Optional[NeededAudioTracker] = None
        self._needed_lock = threading.Lock()
        
        # Role to character mapping (using lowercase keys to match voice_config.json)
        self.role_to_character = {
            "COMMANDING OFFICER": "aria",
            "SCIENCE OFFICER": "jalen",
            "SECURITY OFFICER": "naren",
            "CHIEF MEDICAL OFFICER": "elara",
            "COMMUNICATIONS SPECIALIST": "sarik"
        }
        
        # Load voice_config.json for voice IDs (honors STARDOCK_VOICES_DIR).
        self.voice_config_path = VOICES_DIR / "voice_config.json"
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

    def _find_music_assets(self, patterns: tuple[str, ...]) -> List[Path]:
        """Collect unique theme files from ``assets/music`` (mp3 + wav)."""
        found: List[Path] = []
        seen: set[str] = set()
        for pat in patterns:
            for p in sorted(self.music_dir.glob(pat)):
                key = str(p.resolve())
                if key not in seen:
                    seen.add(key)
                    found.append(p)
        return found

    def _find_theme_music(self, patterns: tuple[str, ...]) -> List[Path]:
        """Like :meth:`_find_music_assets` but drop Kokoro narration exports."""
        out: List[Path] = []
        for p in self._find_music_assets(patterns):
            if 'narration' in p.name.lower():
                continue
            out.append(p)
        return out

    def _resolve_theme_path(self, role: str) -> Optional[Path]:
        """Pick intro/outro theme: env override, preferred filename, then glob."""
        env_key = (
            'STARDOCK_INTRO_MUSIC' if role == 'intro' else 'STARDOCK_OUTRO_MUSIC')
        override = os.environ.get(env_key, '').strip()
        if override:
            p = Path(override)
            if p.is_file():
                return p
            p2 = self.music_dir / override
            if p2.is_file():
                return p2
        preferred = (
            _INTRO_THEME_FILE if role == 'intro' else _OUTRO_THEME_FILE)
        cand = self.music_dir / preferred
        if cand.is_file():
            return cand
        patterns = (
            _INTRO_MUSIC_PATTERNS if role == 'intro' else _OUTRO_MUSIC_PATTERNS)
        found = self._find_theme_music(patterns)
        return found[0] if found else None

    def _extract_stardate_for_intro(
            self, episode_id: str, episode: Dict[str, Any]) -> str:
        """Return a numeric stardate string for intro TTS (expanded later)."""
        raw = episode.get('stardate')
        if isinstance(raw, str) and raw.strip():
            return raw.replace(',', '').replace(' ', '').strip()
        if isinstance(raw, (int, float)):
            return str(raw)
        script = load_episode_script(episode_id)
        if script:
            for scene in script.get('scenes') or []:
                for line in scene.get('lines') or []:
                    c = line.get('content')
                    if not isinstance(c, str):
                        continue
                    m = re.search(
                        r'\b[Ss]tardate\s*:?\s*([\d\s,.]+)', c)
                    if m:
                        return re.sub(
                            r'[\s,]', '', m.group(1)).strip()
        n = episode.get('episode_number', 1) or 1
        return f'52{n:03d}.1'

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
        
        # Get character voices (registry / ElevenLabs metadata — optional for
        # Kokoro, which resolves speakers from voices/voice_config.json).
        characters = episode.get('characters', [])
        character_voices = self.voice_registry.map_characters_to_voices(
            characters)
        if not character_voices and characters:
            character_voices = {
                c.get('name', '').strip(): c.get('name', '').strip()
                for c in characters
                if c.get('name')
            }

        if not character_voices:
            return {"error": "No character voices mapped"}

        self._needed_tracker = NeededAudioTracker(episode_id)
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

            try:
                from story_os.flags import feature_enabled
                if feature_enabled('USE_AUDIO_QA_BLOCK', default=False):
                    from audio_qa import run_episode_audio_qa
                    qa = run_episode_audio_qa(episode_id, audio_dir)
                    generation_meta['audio_qa'] = qa
                    with open(meta_file, 'w') as f:
                        json.dump(generation_meta, f, indent=2)
            except Exception as qa_e:
                logger.warning('Audio QA skipped: %s', qa_e)

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
        finally:
            if self._needed_tracker and self._needed_tracker.items:
                report_path = default_report_path(
                    self.episodes_dir, episode_id)
                self._needed_tracker.write(report_path)
            self._needed_tracker = None
    
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
            scene_no = scene.get('scene_number', scene_index + 1)
            for i, line in enumerate(scene.get('lines', [])):
                clip = self._process_line(
                    line, i, scene_dir, temp_dir, character_voices,
                    scene_number=scene_no,
                )
                if clip:
                    line_clips.append(clip)
            
            # Add scene ambience
            ambience_clip = self._add_scene_ambience(
                scene, scene_dir, scene_number=scene_no)
            
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
                     character_voices: Dict[str, str],
                     scene_number: Optional[int] = None) -> Optional[AudioClip]:
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
                return self._get_sound_effect(
                    content, line_index, scene_dir,
                    scene_number=scene_number,
                )
            
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
        # Delegate the full name-to-voice match (including aliases,
        # (V.O.)/(CONT'D) suffix stripping, and period/case normalization)
        # to dialogue_engine.resolve_character_voice_config so this module
        # and the Kokoro synthesizer never disagree on a speaker.
        voice_config = resolve_character_voice_config(
            character, self.voice_config or {})
        if not voice_config:
            logger.error(
                "No voice config found for character: %r (voice_config keys: %s)",
                character,
                sorted((self.voice_config or {}).get('characters', {}).keys()),
            )
            return None
        
        try:
            # Clean text to avoid synthesis issues
            content = content.replace('"', '').replace('...', '…')

            safe_character = ''.join(
                c for c in character.lower().replace(' ', '_')
                if c.isalnum() or c == '_'
            )
            audio_file = temp_dir / f"line_{line_index:03d}_{safe_character}.wav"

            self._dialogue.synth_for_display_name(
                text=content,
                character_display=character,
                output_path=str(audio_file),
            )
            logger.info('Generated dialogue with Kokoro: %s', audio_file)

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
        """Generate audio for narrator lines using Kokoro (narrator voice)."""
        try:
            content = content.replace('"', '').replace('...', '…')
            audio_file = temp_dir / f"line_{line_index:03d}_narrator.wav"
            self._dialogue.synth_for_display_name(
                text=content,
                character_display='narrator',
                output_path=str(audio_file),
            )
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
                        scene_dir: Path,
                        scene_number: Optional[int] = None) -> Optional[AudioClip]:
        """Resolve a sound effect from assets/sound_effects only.

        If no file matches, records the cue in needed_audio_assets.json
        (see NeededAudioTracker) and returns None.
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

        if self._needed_tracker:
            self._needed_tracker.record_sound_effect(
                description, line_index, search_key,
                scene_number=scene_number,
            )
        logger.warning('Missing sound_effect asset for: %s', description)
        return None

    def _add_scene_ambience(self, scene: Dict[str, Any], scene_dir: Path,
                           scene_number: Optional[int] = None) -> Optional[AudioClip]:
        """Add ambient sound for the scene.
        
        Args:
            scene: Scene data
            scene_dir: Directory for scene audio
        
        Returns:
            AudioClip or None if no ambience added
        """
        setting = (scene.get('setting') or '').lower()
        atmosphere = (scene.get('atmosphere') or '').lower()
        
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

        if self._needed_tracker:
            self._needed_tracker.record_ambience(
                keywords=list(keywords),
                scene_number=scene_number,
            )
        logger.warning(
            'Missing ambience assets for scene keywords: %s', keywords)
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
        
        # Short gap between lines (not sound effects). Half a second of silence
        # after every line sounded like a distinct "clip" / dead-air hit; use a
        # brief breath (~90 ms) by default, or STARDOCK_LINE_GAP_SEC=0 for none.
        silence_duration = max(0.0, _LINE_GAP_SEC)

        try:
            # Silence must match Kokoro line WAV format (24 kHz mono). The old
            # pipeline used 44.1 kHz stereo MP3 silence between 24 kHz mono WAV
            # lines — ffmpeg re-encoded every boundary and produced buzzing /
            # zipper noise in the final MP3.
            silence_file = output_file.parent / "silence_between_lines.wav"
            if silence_duration > 0:
                (
                    ffmpeg
                    .input(
                        f'anullsrc=r={_LINE_SAMPLE_RATE}:cl=mono',
                        f='lavfi',
                        t=silence_duration,
                    )
                    .filter('aformat', sample_fmts='s16', channel_layouts='mono')
                    .output(
                        str(silence_file),
                        acodec='pcm_s16le',
                        ar=_LINE_SAMPLE_RATE,
                        ac=1,
                    )
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
                # Sound effects must land in the same format as dialogue (24 kHz mono
                # PCM). The old path wrote 44.1 kHz stereo MP3 here, so every SFX line
                # reintroduced concat-boundary buzzing next to Kokoro WAVs.
                processed_path = temp_dir / f"processed_{i:03d}.wav"
                
                # Add fade in/out for sound effects to prevent abrupt cuts
                if clip.type == 'sound_effect':
                    fade_in = 0.05  # 50ms fade in
                    fade_out = 0.2  # 200ms fade out for smooth stop
                    clip_duration = clip.duration
                    
                    # Ensure fade out doesn't exceed clip duration
                    if clip_duration <= fade_out:
                        fade_out = clip_duration * 0.3  # Use 30% of duration if too short
                    
                    # Apply fade in/out, then match dialogue lines (24 kHz mono s16).
                    (
                        ffmpeg
                        .input(str(clip_path))
                        .filter('afade', t='in', st=0, d=fade_in)
                        .filter('afade', t='out', st=max(0, clip_duration - fade_out), d=fade_out)
                        .filter('aformat', sample_fmts='s16', channel_layouts='mono')
                        .output(
                            str(processed_path),
                            acodec='pcm_s16le',
                            ar=_LINE_SAMPLE_RATE,
                            ac=1,
                        )
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
                n = len(processed_clips)
                for i, clip_path in enumerate(processed_clips):
                    abs_path = Path(clip_path).resolve()
                    f.write(f"file '{abs_path.as_posix()}'\n")
                    # Gap between lines only — not after the last line (avoids a
                    # trailing "clip" of silence before scene mix / ambience).
                    if silence_duration > 0 and i < n - 1:
                        f.write(f"file '{os.path.abspath(silence_file)}'\n")
            
            # Decode all segments in one stream, normalize to 24 kHz mono s16 PCM,
            # then encode to MP3 once. (Do not force SoXR here — many FFmpeg builds
            # ship without libsoxr; the default resampler is fine.) This avoids
            # per-line MP3 generation at heterogeneous format boundaries.
            dialogue_pcm = output_file.parent / "dialogue_mono_24k.wav"
            dialogue_file = output_file.parent / "dialogue.mp3"
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .filter('aformat', sample_fmts='s16', channel_layouts='mono')
                .output(
                    str(dialogue_pcm),
                    acodec='pcm_s16le',
                    ar=_LINE_SAMPLE_RATE,
                    ac=1,
                )
                .overwrite_output()
                .global_args('-loglevel', 'error')
                .run()
            )
            (
                ffmpeg
                .input(str(dialogue_pcm))
                .output(
                    str(dialogue_file),
                    acodec='libmp3lame',
                    ar=44100,
                    ac=2,
                    audio_bitrate='256k',
                )
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
                        .output(
                            str(looped_ambience),
                            t=str(total_duration),
                            acodec='libmp3lame',
                            ar=44100,
                            audio_bitrate='192k',
                        )
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
                            filter_complex=(
                                f'[0:a]volume=1.0[a0];[1:a]volume={ambience_clip.volume}[a1];'
                                f'[a0][a1]amix=inputs=2:duration=first:normalize=1'
                            ),
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
                            filter_complex=(
                                f'[0:a]volume=1.0[a0];[1:a]volume={ambience_clip.volume}[a1];'
                                f'[a0][a1]amix=inputs=2:duration=first:normalize=1'
                            ),
                            ar=44100
                        )
                        .overwrite_output()
                        .global_args('-loglevel', 'error')
                        .run()
                    )
            else:
                # Dialogue-only scene: re-encode explicitly (avoid ambiguous pass-through).
                (
                    ffmpeg
                    .input(str(dialogue_file))
                    .output(
                        str(output_file),
                        acodec='libmp3lame',
                        ar=44100,
                        ac=2,
                        audio_bitrate='256k',
                    )
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
            stardate_raw = self._extract_stardate_for_intro(episode_id, episode)

            # Spoken form is applied in tts_engine via normalize_trek_tts_text
            # (digit-by-digit stardate, Trek lexicon).
            narration_text = (
                f"This is the logs of the Celestial Temple. "
                f"Journeys through the Gamma Quadrant. "
                f"Stardate {stardate_raw}. "
                f"Episode number {episode_number}."
            )

            narrator_cfg = self.voice_config.get('characters', {}).get(
                'narrator', {})
            if not (narrator_cfg.get('kokoro_voice')
                    or narrator_cfg.get('speaker_wav')):
                logger.error(
                    'No narrator kokoro_voice or speaker_wav in voice_config '
                    'for intro')
                return None

            intro_narration_file = (
                self.assets_dir / "music" / "intro_narration.wav")
            intro_narration_file.parent.mkdir(exist_ok=True, parents=True)

            try:
                self._dialogue.synth_for_display_name(
                    text=narration_text,
                    character_display='narrator',
                    output_path=str(intro_narration_file),
                )
                logger.info('Generated intro narration: %s', intro_narration_file)
                return intro_narration_file
            except Exception as e:
                logger.error('Error generating intro narration: %s', e)
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
            
            narrator_cfg = self.voice_config.get('characters', {}).get(
                'narrator', {})
            if not (narrator_cfg.get('kokoro_voice')
                    or narrator_cfg.get('speaker_wav')):
                logger.error(
                    'No narrator kokoro_voice or speaker_wav in voice_config '
                    'for outro')
                return None

            outro_narration_file = (
                self.assets_dir / "music" / "outro_narration.wav")
            if outro_narration_file.exists():
                logger.info(
                    'Reusing existing outro narration: %s',
                    outro_narration_file)
                return outro_narration_file

            outro_narration_file.parent.mkdir(exist_ok=True, parents=True)

            try:
                self._dialogue.synth_for_display_name(
                    text=narration_text,
                    character_display='narrator',
                    output_path=str(outro_narration_file),
                )
                logger.info(
                    'Generated outro narration: %s', outro_narration_file)
                return outro_narration_file
            except Exception as e:
                logger.error('Error generating outro narration: %s', e)
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
            
            theme_music = self._resolve_theme_path('intro')
            if theme_music:
                logger.info('Using theme music: %s', theme_music)
            else:
                logger.warning(
                    'No intro theme in %s — add %s or any *theme* / *intro* '
                    '.wav / .mp3.',
                    self.music_dir,
                    _INTRO_THEME_FILE,
                )

            # Classic-style intro: theme (~1 min) with narrator over the tail.
            if theme_music and narration_file:
                intro_file.parent.mkdir(exist_ok=True, parents=True)

                narration_probe = ffmpeg.probe(str(narration_file))
                narration_duration = float(
                    narration_probe['format']['duration'])
                music_sec = _INTRO_MUSIC_DURATION_SEC
                narr_delay = min(
                    _INTRO_NARRATION_DELAY_SEC,
                    max(0.0, music_sec - 5.0),
                )
                fade_tail = max(1.0, music_sec - narr_delay)
                mix_end = max(
                    music_sec,
                    narr_delay + narration_duration + 0.5,
                )
                delay_ms = int(round(narr_delay * 1000))

                temp_dir = self.assets_dir / "music" / "temp"
                temp_dir.mkdir(exist_ok=True, parents=True)
                mixed_wav = temp_dir / "intro_mix_24k.wav"

                m_in = ffmpeg.input(str(theme_music))
                n_in = ffmpeg.input(str(narration_file))
                m_chain = (
                    m_in.audio.filter('atrim', start=0, duration=music_sec)
                    .filter('asetpts', 'PTS-STARTPTS')
                    .filter('afade', t='in', st=0, d=2)
                    .filter('afade', t='out', st=narr_delay, d=fade_tail)
                    .filter(
                        'aformat',
                        sample_fmts='s16',
                        channel_layouts='mono',
                    )
                    .filter('aresample', _LINE_SAMPLE_RATE)
                    .filter('apad', whole_dur=mix_end)
                )
                n_chain = (
                    n_in.audio.filter('afade', t='in', st=0, d=0.4)
                    .filter(
                        'aformat',
                        sample_fmts='s16',
                        channel_layouts='mono',
                    )
                    .filter('aresample', _LINE_SAMPLE_RATE)
                    .filter('adelay', str(delay_ms))
                )
                mixed = ffmpeg.filter(
                    [m_chain, n_chain],
                    'amix',
                    inputs=2,
                    duration='longest',
                    normalize=0,
                )
                (
                    ffmpeg.output(
                        mixed,
                        str(mixed_wav),
                        acodec='pcm_s16le',
                        ac=1,
                        ar=_LINE_SAMPLE_RATE,
                    )
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
                (
                    ffmpeg.input(str(mixed_wav))
                    .output(
                        str(intro_file),
                        acodec='libmp3lame',
                        ar=44100,
                        ac=2,
                        audio_bitrate='256k',
                    )
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )
                if mixed_wav.exists():
                    mixed_wav.unlink()

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
            
            theme_music = self._resolve_theme_path('outro')
            if theme_music:
                logger.info('Using theme music: %s', theme_music)

            # If we have both music and narration, mix them
            if theme_music and narration_file:
                # Create temp directory
                temp_dir = self.assets_dir / "music" / "temp"
                temp_dir.mkdir(exist_ok=True, parents=True)
                
                narration_probe = ffmpeg.probe(str(narration_file))
                narration_duration = float(narration_probe['format']['duration'])

                # Trim theme to narration + pad; PCM intermediate (MP3 here broke amix→MP3).
                music_trimmed = temp_dir / "music_trimmed.wav"
                target_duration = max(0.5, narration_duration + 2.0)
                fade_in_d = min(1.0, target_duration / 4.0)
                fade_out_d = min(1.0, max(0.1, target_duration / 4.0))
                fade_out_start = max(0.0, target_duration - fade_out_d)
                (
                    ffmpeg
                    .input(str(theme_music))
                    .filter('afade', t='in', st=0, d=fade_in_d)
                    .filter('afade', t='out', st=fade_out_start, d=fade_out_d)
                    .output(
                        str(music_trimmed),
                        t=str(target_duration),
                        acodec='pcm_s16le',
                        ar=44100,
                        ac=2,
                    )
                    .overwrite_output()
                    .global_args('-loglevel', 'error')
                    .run()
                )

                # Kokoro narration: 24 kHz mono; theme: 44.1 kHz stereo — align then amix.
                # Call ffmpeg directly: ffmpeg-python mangles ``pan=stereo|c0=c0`` escaping.
                outro_file.parent.mkdir(parents=True, exist_ok=True)
                fc = (
                    '[0:a]aresample=44100,pan=stereo|c0=c0|c1=c0[a0];'
                    '[1:a]aresample=44100[a1];'
                    '[a0]volume=1.0[a0v];[a1]volume=0.3[a1v];'
                    '[a0v][a1v]amix=inputs=2:duration=first:normalize=1[out]'
                )
                cmd = [
                    'ffmpeg', '-nostdin', '-y',
                    '-i', str(narration_file),
                    '-i', str(music_trimmed),
                    '-filter_complex', fc,
                    '-map', '[out]',
                    '-c:a', 'libmp3lame', '-b:a', '192k',
                    '-ar', '44100', '-ac', '2',
                    str(outro_file),
                ]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, check=False)
                if proc.returncode != 0:
                    err = (proc.stderr or proc.stdout or '').strip()
                    logger.error('Outro mix ffmpeg failed: %s', err)
                    raise RuntimeError('ffmpeg outro mix failed')

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
        # Look for sci-fi intro music (mp3 or wav)
        intro_matches = self._find_music_assets(
            ('*intro*.mp3', '*intro*.wav', '*opening*.mp3', '*opening*.wav')
        )

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
        # Look for sci-fi outro music (mp3 or wav)
        outro_matches = self._find_music_assets(
            ('*outro*.mp3', '*outro*.wav', '*closing*.mp3', '*closing*.wav')
        )

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
            
            # Re-encode once at a higher bitrate — cheap 192k passes added hash.
            output_file = audio_dir / "full_episode.mp3"
            (
                ffmpeg
                .input(str(concat_file), format='concat', safe=0)
                .output(
                    str(output_file),
                    acodec='libmp3lame',
                    ar=44100,
                    ac=2,
                    audio_bitrate='256k',
                )
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

    def reassemble_episode_audio(
            self,
            episode_id: str,
            *,
            refresh_intro: bool = False,
    ) -> Dict[str, Any]:
        """Rebuild outro and ``full_episode.mp3`` from existing scene MP3s only.

        Does not re-run Kokoro on dialogue lines. Use after a failed outro mux or
        when intro/scene audio already exists.

        Args:
            episode_id: Episode folder id.
            refresh_intro: If True, drop ``intro_complete.mp3`` and run
                :meth:`_create_intro_segment` so intro narration + theme match
                current code and ``assets/music`` (still Kokoro ``kokoro_voice``,
                not ``narrator.wav``).
        """
        script = load_episode_script(episode_id)
        if not script or not script.get('scenes'):
            return {'error': f'No script or scenes for {episode_id}'}

        episode_dir = self.episodes_dir / episode_id
        audio_dir = episode_dir / 'audio'
        if not audio_dir.is_dir():
            return {'error': f'No audio directory: {audio_dir}'}

        scenes = script['scenes']
        scene_results: List[Dict[str, Any]] = []
        for i, _scene in enumerate(scenes):
            mp3 = audio_dir / f'scene_{i:02d}' / 'scene_audio.mp3'
            if not mp3.exists():
                return {
                    'error': (
                        f'Missing {mp3} — run full generate-audio for this episode.'
                    ),
                }
            probe = ffmpeg.probe(str(mp3))
            scene_results.append({
                'success': True,
                'scene_index': i,
                'audio_file': str(mp3.resolve()),
                'duration': float(probe['format']['duration']),
            })

        intro_path: Optional[Path] = audio_dir / 'intro_complete.mp3'
        if refresh_intro and intro_path.exists():
            intro_path.unlink()
            logger.info('Removed intro_complete.mp3 (--refresh-intro)')
            intro_path = audio_dir / 'intro_complete.mp3'
        if refresh_intro or not intro_path.exists():
            built = self._create_intro_segment(episode_id)
            intro_path = built if built else None
            if not intro_path:
                logger.warning(
                    'Intro rebuild failed or skipped — assembling without intro')

        outro_cached = self.assets_dir / 'music' / 'outro_complete.mp3'
        if outro_cached.exists():
            outro_cached.unlink()
            logger.info('Removed cached outro_complete.mp3 for fresh outro mux')

        outro_file = self._create_outro_segment()
        if not outro_file:
            logger.warning('Outro segment missing — full episode will omit outro')

        episode_file = self._assemble_episode(
            episode_id, scene_results, intro_path, outro_file, audio_dir)

        if not episode_file:
            return {'error': 'Episode assembly failed (see logs)'}

        logger.info('Reassembled full episode: %s', episode_file)
        return {
            'success': True,
            'full_episode_file': str(episode_file),
            'outro_file': str(outro_file) if outro_file else None,
        }

    def generate_single_audio(self, text: str, voice_identifier: str,
                            output_file: Optional[str] = None) -> Tuple[bytes, float]:
        """Generate audio for a single text passage using Kokoro."""
        if not output_file:
            fd, output_path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            cleanup_tmp = True
        else:
            output_path = output_file
            cleanup_tmp = False
        self._dialogue.synth_for_display_name(
            text=text,
            character_display=voice_identifier,
            output_path=output_path,
        )
        with open(output_path, 'rb') as f:
            audio_data = f.read()
        probe = ffmpeg.probe(output_path)
        duration = float(probe['format']['duration'])
        if cleanup_tmp:
            os.unlink(output_path)
        return audio_data, duration

# Singleton instance
_audio_pipeline = None

def get_audio_pipeline() -> AudioPipeline:
    """Get the AudioPipeline singleton instance."""
    global _audio_pipeline
    
    if _audio_pipeline is None:
        _audio_pipeline = AudioPipeline()
    
    return _audio_pipeline

def reassemble_episode_audio(
        episode_id: str,
        *,
        refresh_intro: bool = False,
) -> Dict[str, Any]:
    """Module wrapper for :meth:`AudioPipeline.reassemble_episode_audio`."""
    pipeline = get_audio_pipeline()
    return pipeline.reassemble_episode_audio(
        episode_id, refresh_intro=refresh_intro)


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