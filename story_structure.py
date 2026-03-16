#!/usr/bin/env python
"""
Story Structure Module for Stardock Podium.

This module implements Save the Cat story structure for podcast episode generation,
ensuring consistent narrative arcs across all generated content.
"""

import os
import json
import logging
import time
import uuid
import random
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import asyncio

# Try to import required libraries
try:
    from openai import OpenAI, AsyncOpenAI
except ImportError:
    logging.error("OpenAI not found. Please install it with: pip install openai")
    raise

# Local imports
from mem0_client import get_mem0_client
from reference_memory_sync import search_references
from episode_memory import get_episode_memory

# Setup logging
logger = logging.getLogger(__name__)

class StoryStructure:
    """Handles story structure using Save the Cat beat sheet approach."""
    
    # Save the Cat beat sheet structure
    BEAT_SHEET = [
        {
            "name": "Opening Image",
            "description": "Sets the tone, mood, and style. Gives a snapshot of the starting world and its problems.",
            "percentage": 0.01,
            "duration_factor": 0.01
        },
        {
            "name": "Theme Stated",
            "description": "The message or thematic premise - what the story is really about.",
            "percentage": 0.05,
            "duration_factor": 0.02
        },
        {
            "name": "Setup",
            "description": "Introduces the main characters, their habits, and their world.",
            "percentage": 0.10,
            "duration_factor": 0.08
        },
        {
            "name": "Catalyst",
            "description": "The inciting incident or call to adventure that disrupts the status quo.",
            "percentage": 0.15,
            "duration_factor": 0.02
        },
        {
            "name": "Debate",
            "description": "The protagonist questions whether to pursue the journey or goal.",
            "percentage": 0.20,
            "duration_factor": 0.08
        },
        {
            "name": "Break into Two",
            "description": "The protagonist makes the decision to take on the journey.",
            "percentage": 0.25,
            "duration_factor": 0.02
        },
        {
            "name": "B Story",
            "description": "A secondary story or relationship that carries the theme of the story.",
            "percentage": 0.30,
            "duration_factor": 0.03
        },
        {
            "name": "Fun and Games",
            "description": "The promise of the premise is explored. The enjoyable part of the story.",
            "percentage": 0.40,
            "duration_factor": 0.15
        },
        {
            "name": "Midpoint",
            "description": "A false victory or false defeat. Stakes are raised, and the goal is less attainable.",
            "percentage": 0.50,
            "duration_factor": 0.02
        },
        {
            "name": "Bad Guys Close In",
            "description": "Antagonistic forces regroup and close in on the protagonist.",
            "percentage": 0.60,
            "duration_factor": 0.08
        },
        {
            "name": "All Is Lost",
            "description": "The lowest point where it seems the goal is impossible to achieve.",
            "percentage": 0.70,
            "duration_factor": 0.02
        },
        {
            "name": "Dark Night of the Soul",
            "description": "The protagonist must make a final decision based on what they've learned.",
            "percentage": 0.75,
            "duration_factor": 0.05
        },
        {
            "name": "Break into Three",
            "description": "The protagonist figures out the solution and commits to the final push.",
            "percentage": 0.80,
            "duration_factor": 0.02
        },
        {
            "name": "Finale",
            "description": "The protagonist proves they've changed and succeeds (or fails tragically).",
            "percentage": 0.85,
            "duration_factor": 0.12
        },
        {
            "name": "Final Image",
            "description": "Shows how the world has changed, often mirroring the opening image.",
            "percentage": 0.98,
            "duration_factor": 0.02
        }
    ]
    
    def __init__(self, episodes_dir: str = "episodes"):
        """Initialize the story structure module.
        
        Args:
            episodes_dir: Directory to store episode data
        """
        self.episodes_dir = Path(episodes_dir)
        self.episodes_dir.mkdir(exist_ok=True)
        
        # Get mem0 client
        self.mem0_client = get_mem0_client()
        
        # Initialize OpenAI client
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        
        # Initialize OpenRouter client (fallback)
        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key:
            self.using_openrouter = True
            self.openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key
            )
            self.async_openrouter_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=openrouter_key
            )
        else:
            self.using_openrouter = False
            logger.warning("OPENROUTER_API_KEY not found in environment variables")
    
    def generate_episode_structure(self, episode_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate the structure for a new podcast episode.
        
        Args:
            episode_data: Data for the episode (title, theme, etc.)
        
        Returns:
            Dictionary with complete episode structure
        """
        # Generate or use episode ID
        episode_id = episode_data.get("episode_id", f"ep_{uuid.uuid4().hex[:8]}")
        
        # Get episode number
        episode_number = episode_data.get("episode_number")
        if episode_number is None:
            # Auto-increment from existing episodes
            existing_episodes = self.list_episodes(series=episode_data.get("series"))
            episode_number = max([ep.get("episode_number", 0) for ep in existing_episodes], default=0) + 1
        
        # Get or generate title
        title = episode_data.get("title")
        if not title:
            title = self._generate_title(
                theme=episode_data.get("theme"),
                series=episode_data.get("series"),
                episode_number=episode_number
            )
        
        # Initialize episode structure
        episode = {
            "episode_id": episode_id,
            "title": title,
            "series": episode_data.get("series", "Main Series"),
            "episode_number": episode_number,
            "theme": episode_data.get("theme"),
            "created_at": time.time(),
            "target_duration_minutes": episode_data.get("target_duration", 30),
            "status": "draft",
            "beats": self._calculate_beat_durations(episode_data.get("target_duration", 30)),
            "characters": [],
            "scenes": [],
            "script": None,
            "audio": None,
            "metadata": {}
        }
        
        # Add episode to memory
        self._add_episode_to_memory(episode)
        
        # Save episode structure
        self._save_episode(episode)
        
        return episode
    
    def _calculate_beat_durations(self, target_duration: int) -> List[Dict[str, Any]]:
        """Calculate durations for each beat based on target episode length.
        
        Args:
            target_duration: Target duration in minutes
        
        Returns:
            List of beats with calculated durations
        """
        total_seconds = target_duration * 60
        
        beats = []
        for beat in self.BEAT_SHEET:
            beat_duration = int(total_seconds * beat["duration_factor"])
            
            # Calculate timepoints for the beat
            start_percent = beat["percentage"] - (beat["duration_factor"] / 2)
            end_percent = beat["percentage"] + (beat["duration_factor"] / 2)
            
            start_time = int(total_seconds * start_percent)
            end_time = int(total_seconds * end_percent)
            
            beats.append({
                "name": beat["name"],
                "description": beat["description"],
                "duration_seconds": beat_duration,
                "start_time": start_time,
                "end_time": end_time
            })
        
        return beats
    
    def _generate_title(self, theme: Optional[str] = None, 
                      series: Optional[str] = None,
                      episode_number: Optional[int] = None) -> str:
        """Generate a title for the episode.
        
        Args:
            theme: Optional theme for the episode
            series: Optional series name
            episode_number: Optional episode number
        
        Returns:
            Generated title
        """
        try:
            # Prepare prompt for title generation
            prompt = "Generate a Star Trek-style podcast episode title"
            
            if theme:
                prompt += f" with the theme of '{theme}'"
            
            if series:
                prompt += f" for the series '{series}'"
            
            if episode_number:
                prompt += f", episode number {episode_number}"
            
            prompt += ". The title should be catchy, intriguing, and reference sci-fi concepts."
            
            # Use OpenRouter with Claude Opus 4.5 if available, otherwise fallback to OpenAI
            if self.using_openrouter:
                response = self.openrouter_client.chat.completions.create(
                    model="anthropic/claude-opus-4.5",
                    messages=[
                        {"role": "system", "content": "You are a professional sci-fi writer specializing in Star Trek."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=50
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a professional sci-fi writer specializing in Star Trek."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=50
                )
            
            # Extract and clean the title
            title = response.choices[0].message.content.strip()
            
            # Remove quotes if present
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            
            # If title is too long, truncate with ellipsis
            if len(title) > 80:
                title = title[:77] + "..."
            
            return title
        
        except Exception as e:
            logger.error(f"Error generating title: {e}")
            
            # Fallback title
            fallback = f"Episode {episode_number or 'X'}"
            if theme:
                fallback += f": {theme}"
            
            return fallback
    
    def _add_episode_to_memory(self, episode: Dict[str, Any]) -> None:
        """Add episode structure to memory for future reference.
        
        Args:
            episode: Episode structure dictionary
        """
        try:
            # Convert to string for storage
            episode_str = json.dumps(episode)
            
            metadata = {
                "episode_id": episode["episode_id"],
                "title": episode["title"],
                "series": episode["series"],
                "episode_number": episode["episode_number"]
            }
            
            # Add to memory
            self.mem0_client.add_story_structure(
                structure_data=episode,
                episode_id=episode["episode_id"]
            )
            
            logger.debug(f"Added episode structure to memory: {episode['episode_id']}")
        
        except Exception as e:
            logger.error(f"Error adding episode to memory: {e}")
    
    def _save_episode(self, episode: Dict[str, Any]) -> None:
        """Save episode data to file.
        
        Args:
            episode: Episode data
        """
        episode_dir = self.episodes_dir / episode["episode_id"]
        episode_dir.mkdir(exist_ok=True)
        
        episode_file = episode_dir / "structure.json"
        
        try:
            with open(episode_file, 'w') as f:
                json.dump(episode, f, indent=2)
            
            logger.info(f"Saved episode structure to {episode_file}")
        
        except Exception as e:
            logger.error(f"Error saving episode structure: {e}")
    
    def generate_character_cast(self, episode_id: str) -> List[Dict[str, Any]]:
        """Generate a cast of characters for the episode.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            List of character dictionaries
        """
        # Load episode data
        episode = self.get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return []
        
        try:
            # Search for existing character archetypes in memory
            character_archetypes = self.mem0_client.search_memory(
                "Star Trek character archetypes",
                user_id="reference_materials",
                memory_type=self.mem0_client.REFERENCE_MATERIAL,
                limit=3
            )
            
            # Create context from episode data
            context = {
                "title": episode["title"],
                "theme": episode["theme"],
                "series": episode["series"]
            }
            
            # Create prompt for character generation
            existing_archetypes = "\n".join([arch["memory"] for arch in character_archetypes])
            
            prompt = f"""
            Generate a cast of 4-6 main characters for a Star Trek-style podcast episode.
            
            Episode Title: {context['title']}
            Series: {context['series']}
            Theme: {context['theme'] or 'Not specified'}
            
            Character Information Reference:
            {existing_archetypes}
            
            For each character, provide:
            1. Name
            2. Species
            3. Role on the ship/station
            4. Personality traits
            5. Key backstory elements
            6. Voice description (for voice acting)
            
            The cast should be diverse and should typically include:
            - A commanding officer
            - A science or technical specialist
            - A security or tactical officer
            - A medical or counselor role
            - 1-2 additional specialists or guest characters
            
            Format each character as a detailed profile that can be used for voice casting and character development.
            """
            
            # Use OpenRouter with Claude Opus 4.5 if available, otherwise fallback to OpenAI
            if self.using_openrouter:
                response = self.openrouter_client.chat.completions.create(
                    model="anthropic/claude-opus-4.5",
                    messages=[
                        {"role": "system", "content": "You are a Star Trek universe expert and character creator."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=2000
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a Star Trek universe expert and character creator."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
                    max_tokens=2000
                )
            
            # Extract character data from response
            character_text = response.choices[0].message.content
            
            # Parse characters from the text
            characters = self._parse_characters(character_text)
            
            # Update episode with characters
            episode["characters"] = characters
            self._save_episode(episode)
            
            return characters
        
        except Exception as e:
            logger.error(f"Error generating characters: {e}")
            return []
    
    def _parse_characters(self, character_text: str) -> List[Dict[str, Any]]:
        """Parse character descriptions from generated text.
        
        Args:
            character_text: Generated character descriptions
        
        Returns:
            List of parsed character dictionaries
        """
        characters = []
        
        # Split by double newlines or numbered sections
        sections = re.split(r'\n\s*\n|\n\d+\.\s+', character_text)
        
        for section in sections:
            if not section.strip():
                continue
            
            # Extract character data
            char = {}
            
            # Extract name - usually at the beginning of the section
            name_match = re.search(r'^[*#]*\s*(?:Name:?\s*)?([A-Za-z\s\'\"]+)', section, re.MULTILINE)
            if name_match:
                char["name"] = name_match.group(1).strip()
            else:
                # Try to find a capitalized name at the beginning
                name_match = re.search(r'^([A-Z][A-Za-z\'\s]+)(?:\n|\:)', section)
                if name_match:
                    char["name"] = name_match.group(1).strip()
                else:
                    # Skip if no name found
                    continue
            
            # Extract species
            species_match = re.search(r'Species:?\s*([A-Za-z\s\-]+)', section, re.IGNORECASE)
            if species_match:
                char["species"] = species_match.group(1).strip()
            
            # Extract role
            role_match = re.search(r'Role:?\s*([^\n]+)', section, re.IGNORECASE)
            if not role_match:
                role_match = re.search(r'Position:?\s*([^\n]+)', section, re.IGNORECASE)
            
            if role_match:
                char["role"] = role_match.group(1).strip()
            
            # Extract personality
            personality_match = re.search(r'Personality:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                         section, re.IGNORECASE)
            if personality_match:
                char["personality"] = personality_match.group(1).strip()
            
            # Extract backstory
            backstory_match = re.search(r'Backstory:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                       section, re.IGNORECASE)
            if not backstory_match:
                backstory_match = re.search(r'Background:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                           section, re.IGNORECASE)
            
            if backstory_match:
                char["backstory"] = backstory_match.group(1).strip()
            
            # Extract voice description
            voice_match = re.search(r'Voice:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                   section, re.IGNORECASE)
            if voice_match:
                char["voice_description"] = voice_match.group(1).strip()
            
            # Add character ID
            char["character_id"] = f"char_{uuid.uuid4().hex[:8]}"
            
            # Add to characters list if we have the minimum info
            if "name" in char and ("role" in char or "personality" in char):
                characters.append(char)
        
        return characters
    
    async def generate_scenes(self, episode_id: str) -> List[Dict[str, Any]]:
        """Generate scenes for an episode based on its structure and characters.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            List of scene dictionaries
        """
        # Load episode data
        episode = self.get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return []
        
        # Ensure characters exist
        if not episode.get("characters"):
            logger.warning(f"No characters found for episode {episode_id}. Generating characters first.")
            characters = self.generate_character_cast(episode_id)
            episode["characters"] = characters
        
        try:
            # Calculate number of scenes based on beats and target duration
            target_seconds = episode.get("target_duration_minutes", 30) * 60
            beats = episode.get("beats", [])
            
            # Aim for scenes averaging 2-3 minutes
            target_scenes = max(5, min(15, target_seconds // 150))
            
            # Determine number of scenes per beat based on duration ratios
            scenes_per_beat = {}
            for beat in beats:
                # Calculate scenes proportional to beat duration
                scene_count = max(1, int((beat["duration_seconds"] / target_seconds) * target_scenes))
                scenes_per_beat[beat["name"]] = scene_count
            
            # Search for relevant reference materials
            query = f"Star Trek {episode.get('theme', '')}"
            references = search_references(query, limit=3)
            
            # Extract reference text
            reference_text = "\n".join([ref.get("memory", "") for ref in references])
            
            # Get previous episode context for continuity (if not first episode)
            previous_context = ""
            try:
                episode_number = episode.get("episode_number", 0)
                if episode_number > 1:
                    memory_manager = get_episode_memory()
                    context_data = memory_manager.get_previous_episode_context(
                        current_episode_number=episode_number,
                        series=episode.get("series"),
                        limit=15
                    )
                    
                    # Format previous context for prompt
                    if context_data.get("plot_points"):
                        previous_context += "\n\nPREVIOUS EPISODE PLOT POINTS:\n"
                        previous_context += "\n".join(context_data["plot_points"][:5])
                    
                    if context_data.get("unresolved_threads"):
                        previous_context += "\n\nUNRESOLVED THREADS TO CONSIDER:\n"
                        previous_context += "\n".join(context_data["unresolved_threads"][:3])
                    
                    if context_data.get("character_states"):
                        previous_context += "\n\nCHARACTER STATES FROM PREVIOUS EPISODES:\n"
                        previous_context += "\n".join(context_data["character_states"][:5])
            except Exception as e:
                logger.warning(f"Could not retrieve previous episode context (non-critical): {e}")
                previous_context = ""
            
            # Prepare character information
            character_info = "\n".join([
                f"{char.get('name', 'Unknown')}: {char.get('species', 'Unknown')} - {char.get('role', 'Unknown')}"
                for char in episode.get("characters", [])
            ])
            
            # Generate scene outlines for each beat
            all_scenes = []
            tasks = []
            
            for beat in beats:
                num_scenes = scenes_per_beat.get(beat["name"], 1)
                for i in range(num_scenes):
                    task = self._generate_scene_outline(
                        episode=episode,
                        beat=beat,
                        scene_number=len(tasks) + 1,
                        total_scenes=sum(scenes_per_beat.values()),
                        reference_text=reference_text,
                        character_info=character_info,
                        previous_context=previous_context
                    )
                    tasks.append(task)
            
            # Run scene generation concurrently
            scene_results = await asyncio.gather(*tasks)
            all_scenes = [scene for scene in scene_results if scene]
            
            # Update episode with scenes
            episode["scenes"] = all_scenes
            self._save_episode(episode)
            
            return all_scenes
        
        except Exception as e:
            logger.error(f"Error generating scenes: {e}")
            return []
    
    async def _generate_scene_outline(self, episode: Dict[str, Any], beat: Dict[str, Any],
                                    scene_number: int, total_scenes: int,
                                    reference_text: str, character_info: str,
                                    previous_context: str = "") -> Dict[str, Any]:
        """Generate a single scene outline.
        
        Args:
            episode: Episode data
            beat: The story beat this scene belongs to
            scene_number: Number of this scene in the overall sequence
            total_scenes: Total number of scenes in the episode
            reference_text: Relevant reference material text
            character_info: Character information string
        
        Returns:
            Scene dictionary
        """
        try:
            # Calculate approximate duration for this scene
            target_seconds = episode.get("target_duration_minutes", 30) * 60
            scene_duration = int(target_seconds / total_scenes)
            
            # Determine approximate position
            progress = scene_number / total_scenes
            
            # Create prompt for scene generation
            prompt = f"""
            Create a detailed scene outline for a Star Trek-style podcast episode.
            
            EPISODE INFORMATION:
            Title: {episode.get('title')}
            Theme: {episode.get('theme', 'Not specified')}
            
            STORY BEAT: {beat.get('name')}
            Beat Description: {beat.get('description')}
            Scene Number: {scene_number} of {total_scenes}
            Progress: {progress*100:.0f}% through the story
            
            CHARACTERS:
            {character_info}
            
            REFERENCE MATERIAL:
            {reference_text[:500] if reference_text else "No specific reference material."}
            
            {previous_context if previous_context else ""}
            
            Create a detailed scene outline with:
            1. Setting (where the scene takes place)
            2. Character participants (who is in this scene)
            3. Plot (what happens in this scene)
            4. Dialogue suggestions (key lines or exchanges)
            5. Atmosphere/mood
            6. Sound effects/music suggestions
            
            The scene should be appropriate for the beat it's in, advancing the story in a compelling way.
            Target scene length: {scene_duration//60} minutes {scene_duration%60} seconds.
            """
            
            # Use OpenRouter with Claude Opus 4.5 if available, otherwise fallback to OpenAI
            if self.using_openrouter:
                response = await self.async_openrouter_client.chat.completions.create(
                    model="anthropic/claude-opus-4.5",
                    messages=[
                        {"role": "system", "content": "You are an expert screenwriter specializing in science fiction and Star Trek."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
            else:
                response = await self.async_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert screenwriter specializing in science fiction and Star Trek."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000
                )
            
            # Extract scene content
            scene_content = response.choices[0].message.content
            
            # Parse scene into structured format
            scene = self._parse_scene(scene_content)
            
            # Add scene metadata
            scene["scene_id"] = f"scene_{uuid.uuid4().hex[:8]}"
            scene["scene_number"] = scene_number
            scene["beat"] = beat["name"]
            scene["duration_seconds"] = scene_duration
            
            return scene
        
        except Exception as e:
            logger.error(f"Error generating scene outline: {e}")
            return {}
    
    def _parse_scene(self, scene_content: str) -> Dict[str, Any]:
        """Parse scene description from generated text.
        
        Args:
            scene_content: Generated scene description
        
        Returns:
            Parsed scene dictionary
        """
        scene = {}
        
        # Extract setting
        setting_match = re.search(r'Setting:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                scene_content, re.IGNORECASE)
        if setting_match:
            scene["setting"] = setting_match.group(1).strip()
        
        # Extract characters
        characters_match = re.search(r'Characters?:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                   scene_content, re.IGNORECASE)
        if characters_match:
            characters_text = characters_match.group(1).strip()
            scene["characters"] = [char.strip() for char in re.split(r',|\n', characters_text) if char.strip()]
        
        # Extract plot
        plot_match = re.search(r'Plot:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                             scene_content, re.IGNORECASE)
        if plot_match:
            scene["plot"] = plot_match.group(1).strip()
        
        # Extract dialogue
        dialogue_match = re.search(r'Dialogue:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                 scene_content, re.IGNORECASE)
        if dialogue_match:
            scene["dialogue"] = dialogue_match.group(1).strip()
        
        # Extract atmosphere
        atmosphere_match = re.search(r'Atmosphere:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                   scene_content, re.IGNORECASE)
        if not atmosphere_match:
            atmosphere_match = re.search(r'Mood:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                       scene_content, re.IGNORECASE)
        
        if atmosphere_match:
            scene["atmosphere"] = atmosphere_match.group(1).strip()
        
        # Extract sound effects
        sound_match = re.search(r'Sound Effects:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                              scene_content, re.IGNORECASE)
        if not sound_match:
            sound_match = re.search(r'Sound:?\s*([^\n]+(?:\n[^\n]+)*?)(?:\n\s*[A-Za-z]+:|\Z)', 
                                  scene_content, re.IGNORECASE)
        
        if sound_match:
            scene["sound_effects"] = sound_match.group(1).strip()
        
        # If we couldn't parse structured data, save the whole content
        if len(scene) <= 1:
            scene["content"] = scene_content
        
        return scene
    
    def generate_episode_script(self, episode_id: str) -> Dict[str, Any]:
        """Generate a complete script for an episode.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Dictionary with complete script
        """
        # Load episode data
        logger.info(f"Loading episode data for {episode_id}...")
        episode = self.get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return {}
        
        # Ensure scenes exist
        if not episode.get("scenes"):
            logger.warning(f"No scenes found for episode {episode_id}. Generate scenes first.")
            return {}
        
        try:
            # Prepare script format
            logger.info(f"Preparing script format for episode: {episode.get('title')}")
            script = {
                "title": episode.get("title"),
                "episode_id": episode_id,
                "created_at": time.time(),
                "scenes": []
            }
            
            # Process each scene to generate detailed script
            total_scenes = len(episode.get("scenes", []))
            logger.info(f"Generating script for {total_scenes} scenes...")
            
            for i, scene in enumerate(episode.get("scenes", []), 1):
                logger.info(f"Generating script for scene {i}/{total_scenes}: {scene.get('beat', 'Unknown beat')}")
                # Generate script for this scene
                scene_script = self._generate_scene_script(episode, scene)
                script["scenes"].append(scene_script)
                logger.info(f"Completed scene {i}/{total_scenes}")
            
            # Update episode with script
            logger.info("Updating episode with generated script...")
            episode["script"] = script
            self._save_episode(episode)
            
            # Save script to separate file for easier editing
            logger.info("Saving script to file...")
            self._save_script(episode_id, script)
            
            # Auto-extract memories for continuity (optional - only if episode has script)
            try:
                logger.info("Extracting memories from episode for continuity...")
                memory_manager = get_episode_memory()
                memory_manager.extract_memories_from_episode(episode_id)
                logger.info("Memory extraction completed")
            except Exception as e:
                logger.warning(f"Memory extraction failed (non-critical): {e}")
            
            logger.info(f"Script generation completed for episode: {episode.get('title')}")
            return script
        
        except Exception as e:
            logger.error(f"Error generating episode script: {e}")
            return {}
    
    def _generate_scene_script(self, episode: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed script for a scene.
        
        Args:
            episode: Episode data
            scene: Scene data
        
        Returns:
            Dictionary with scene script
        """
        logger.info(f"Preparing to generate script for scene: {scene.get('beat', 'Unknown beat')}")
        
        # Get character information
        character_info = ""
        character_contexts = []
        for char in episode.get('characters', []):
            char_name = char.get('name', '')
            character_info += f"{char_name}: {char.get('species', '')} - {char.get('role', '')}\n"
            
            # Get character continuity context if not first episode
            try:
                episode_number = episode.get("episode_number", 0)
                if episode_number > 1:
                    memory_manager = get_episode_memory()
                    char_context = memory_manager.get_character_continuity_context(
                        character_name=char_name,
                        current_episode_number=episode_number
                    )
                    if char_context:
                        character_contexts.append(f"{char_name}'s previous developments: {', '.join(char_context[:3])}")
            except Exception:
                pass  # Non-critical, continue without character context
        
        # Create context for generation
        logger.info("Creating context for scene generation...")
        context = (
            f"Title: {episode.get('title', '')}\n"
            f"Theme: {episode.get('theme', '')}\n"
            f"Beat: {scene.get('beat', '')}\n"
            f"Setting: {scene.get('setting', '')}\n"
            f"Scene Number: {scene.get('scene_number', '')}\n\n"
            f"Character Information:\n{character_info}\n"
        )
        
        # Add character continuity context if available
        if character_contexts:
            context += "\n" + "\n".join(character_contexts) + "\n"
        
        # Get reference material
        logger.info("Searching for relevant reference material...")
        reference_text = search_references(
            query=f"{scene.get('beat', '')} {scene.get('setting', '')}",
            limit=3
        )
        
        # Create prompt
        logger.info("Creating generation prompt...")
        prompt = (
            f"Generate a detailed script for a Star Trek audio drama scene.\n\n"
            f"Context:\n{context}\n"
            f"Reference Material:\n{reference_text}\n\n"
            f"Generate a scene that includes:\n"
            f"1. Scene description\n"
            f"2. Character dialogue\n"
            f"3. Sound effects\n"
            f"4. Narration where needed\n\n"
            f"Format the output with clear scene headings and character names."
        )
        
        try:
            # Generate scene content
            logger.info("Sending request to AI model...")
            # Use OpenRouter with Claude Opus 4.5 if available, otherwise fallback to OpenAI
            if self.using_openrouter:
                response = self.openrouter_client.chat.completions.create(
                    model="anthropic/claude-opus-4.5",
                    messages=[
                        {"role": "system", "content": "You are an expert screenwriter for audio dramas."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are an expert screenwriter for audio dramas."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
            
            # Parse the generated content
            logger.info("Parsing generated content...")
            new_content = response.choices[0].message.content
            new_lines = self._parse_script_lines(new_content)
            
            # Create scene script
            logger.info("Creating final scene script...")
            scene_script = {
                "scene_number": scene.get('scene_number'),
                "beat": scene.get('beat'),
                "setting": scene.get('setting'),
                "lines": new_lines
            }
            
            logger.info(f"Successfully generated script for scene: {scene.get('beat', 'Unknown beat')}")
            return scene_script
            
        except Exception as e:
            logger.error(f"Error generating scene script: {e}")
            return {
                "scene_number": scene.get('scene_number'),
                "beat": scene.get('beat'),
                "setting": scene.get('setting'),
                "lines": []
            }
    
    def _parse_script_lines(self, script_content: str) -> List[Dict[str, Any]]:
        """Parse script content into structured lines.
        
        Args:
            script_content: Generated script content
        
        Returns:
            List of line dictionaries
        """
        lines = []
        
        # Split script into paragraphs
        paragraphs = re.split(r'\n{2,}', script_content)
        
        scene_description = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # Check for scene description in brackets
            description_match = re.search(r'\[(.*?)\]', paragraph)
            if description_match:
                scene_description = description_match.group(1).strip()
                # Check if there's content after the description
                remaining = re.sub(r'\[(.*?)\]', '', paragraph).strip()
                if not remaining:
                    lines.append({
                        "type": "description",
                        "content": scene_description
                    })
                    continue
                paragraph = remaining
            
            # Check for sound effect in parentheses
            sound_effect_match = re.search(r'\((.*?)\)', paragraph)
            if sound_effect_match and len(sound_effect_match.group(0)) > len(paragraph) * 0.7:
                lines.append({
                    "type": "sound_effect",
                    "content": sound_effect_match.group(1).strip()
                })
                continue
            
            # Check for character dialogue
            dialogue_match = re.search(r'^([A-Z][A-Z\s]+)(?:\s*\(.*?\))?\:\s*(.*)', paragraph)
            if dialogue_match:
                character = dialogue_match.group(1).strip()
                dialogue = dialogue_match.group(2).strip()
                
                # Check if it's the narrator
                if character.upper() == "NARRATOR":
                    lines.append({
                        "type": "narration",
                        "content": dialogue
                    })
                else:
                    lines.append({
                        "type": "dialogue",
                        "character": character,
                        "content": dialogue
                    })
                continue
            
            # If no specific format matched, treat as description
            lines.append({
                "type": "description",
                "content": paragraph
            })
        
        return lines
    
    def _save_script(self, episode_id: str, script: Dict[str, Any]) -> None:
        """Save script to a separate file.
        
        Args:
            episode_id: Episode ID
            script: Script data
        """
        episode_dir = self.episodes_dir / episode_id
        episode_dir.mkdir(exist_ok=True)
        
        script_file = episode_dir / "script.json"
        
        try:
            with open(script_file, 'w') as f:
                json.dump(script, f, indent=2)
            
            logger.info(f"Saved script to {script_file}")
        
        except Exception as e:
            logger.error(f"Error saving script: {e}")
    
    def get_episode(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get episode data by ID.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Episode dictionary or None if not found
        """
        episode_dir = self.episodes_dir / episode_id
        structure_file = episode_dir / "structure.json"
        
        if not structure_file.exists():
            logger.error(f"Episode structure file not found: {structure_file}")
            return None
        
        try:
            with open(structure_file, 'r') as f:
                return json.load(f)
        
        except Exception as e:
            logger.error(f"Error reading episode structure: {e}")
            return None
    
    def list_episodes(self, series: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all episodes, optionally filtered by series.
        
        Args:
            series: Optional series name to filter by
        
        Returns:
            List of episode summary dictionaries
        """
        episodes = []
        
        for episode_dir in self.episodes_dir.iterdir():
            if not episode_dir.is_dir():
                continue
            
            structure_file = episode_dir / "structure.json"
            if not structure_file.exists():
                continue
            
            try:
                with open(structure_file, 'r') as f:
                    episode = json.load(f)
                
                # Apply series filter if specified
                if series and episode.get("series") != series:
                    continue
                
                # Create summary
                summary = {
                    "episode_id": episode.get("episode_id"),
                    "title": episode.get("title"),
                    "series": episode.get("series"),
                    "episode_number": episode.get("episode_number"),
                    "status": episode.get("status", "draft"),
                    "created_at": episode.get("created_at"),
                    "has_script": bool(episode.get("script")),
                    "has_audio": bool(episode.get("audio"))
                }
                
                episodes.append(summary)
            
            except Exception as e:
                logger.error(f"Error reading episode structure from {structure_file}: {e}")
        
        # Sort by series and episode number
        episodes.sort(key=lambda ep: (ep.get("series", ""), ep.get("episode_number", 0)))
        
        return episodes

# Singleton instance
_story_structure = None

def get_story_structure() -> StoryStructure:
    """Get the StoryStructure singleton instance."""
    global _story_structure
    
    if _story_structure is None:
        _story_structure = StoryStructure()
    
    return _story_structure

def generate_episode(episode_data: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a new podcast episode structure.
    
    Args:
        episode_data: Data for the episode (title, theme, etc.)
    
    Returns:
        Dictionary with complete episode structure
    """
    story_structure = get_story_structure()
    return story_structure.generate_episode_structure(episode_data)

def generate_characters(episode_id: str) -> List[Dict[str, Any]]:
    """Generate characters for an episode.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        List of character dictionaries
    """
    story_structure = get_story_structure()
    return story_structure.generate_character_cast(episode_id)

async def generate_scenes(episode_id: str) -> List[Dict[str, Any]]:
    """Generate scenes for an episode.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        List of scene dictionaries
    """
    story_structure = get_story_structure()
    return await story_structure.generate_scenes(episode_id)

def generate_script(episode_id: str) -> Dict[str, Any]:
    """Generate script for an episode.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        Dictionary with complete script
    """
    story_structure = get_story_structure()
    return story_structure.generate_episode_script(episode_id)

def get_episode(episode_id: str) -> Optional[Dict[str, Any]]:
    """Get episode data by ID.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        Episode dictionary or None if not found
    """
    story_structure = get_story_structure()
    return story_structure.get_episode(episode_id)

def list_episodes(series: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all episodes, optionally filtered by series.
    
    Args:
        series: Optional series name to filter by
    
    Returns:
        List of episode summary dictionaries
    """
    story_structure = get_story_structure()
    return story_structure.list_episodes(series)