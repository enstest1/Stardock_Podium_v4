#!/usr/bin/env python
"""
Episode Memory Module for Stardock Podium.

This module handles the storage and retrieval of episode memories,
including plot points, character developments, and continuity information.
"""

import os
import json
import logging
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Local imports
from mem0_client import get_mem0_client

# Setup logging
logger = logging.getLogger(__name__)

class EpisodeMemory:
    """Manages episode memory and continuity."""
    
    # Constants for memory categories
    PLOT_POINT = "plot_point"
    CHARACTER_DEVELOPMENT = "character_development"
    WORLD_BUILDING = "world_building"
    CONTINUITY = "continuity"
    RELATIONSHIP = "relationship"
    CHARACTER_STATE = "character_state"
    UNRESOLVED_THREAD = "unresolved_thread"
    
    def __init__(self):
        """Initialize the episode memory manager."""
        from config.paths import EPISODES_DIR
        self.mem0_client = get_mem0_client()
        self.episodes_dir = EPISODES_DIR
    
    def _load_episode_data(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Load episode data from files (structure.json and script.json).
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            Episode dictionary with structure and script, or None if not found
        """
        episode_dir = self.episodes_dir / episode_id
        structure_file = episode_dir / "structure.json"
        
        if not structure_file.exists():
            logger.error(f"Episode structure file not found: {structure_file}")
            return None
        
        try:
            # Load structure
            with open(structure_file, 'r', encoding='utf-8') as f:
                episode = json.load(f)
            
            # Load script if it exists
            script_file = episode_dir / "script.json"
            if script_file.exists():
                try:
                    with open(script_file, 'r', encoding='utf-8') as f:
                        episode["script"] = json.load(f)
                except Exception as e:
                    logger.warning(f"Error loading script file: {e}")
            
            return episode
            
        except Exception as e:
            logger.error(f"Error reading episode structure: {e}")
            return None
    
    def extract_memories_from_episode(self, episode_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Extract memory entries from an episode.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Dictionary of memory entries by category
        """
        # Get episode data
        episode = self._load_episode_data(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return {}
        
        # Extract memories by category
        memories = {
            self.PLOT_POINT: self._extract_plot_points(episode),
            self.CHARACTER_DEVELOPMENT: self._extract_character_developments(episode),
            self.WORLD_BUILDING: self._extract_world_building(episode),
            self.CONTINUITY: self._extract_continuity_points(episode),
            self.RELATIONSHIP: self._extract_relationships(episode),
            self.CHARACTER_STATE: self._extract_character_states(episode),
            self.UNRESOLVED_THREAD: self._extract_unresolved_threads(episode)
        }
        
        # Save memories to database
        for category, entries in memories.items():
            for entry in entries:
                self.add_memory(
                    content=entry["content"],
                    category=category,
                    episode_id=episode_id,
                    metadata=entry.get("metadata", {})
                )
        
        # Save memories to JSON file for backup
        self.save_memories_to_json(episode_id, memories)
        
        return memories
    
    def _extract_plot_points(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract plot points from an episode.
        
        Args:
            episode: Episode data
        
        Returns:
            List of plot point memory entries
        """
        plot_points = []
        
        # Extract from beats
        if "beats" in episode:
            for beat in episode["beats"]:
                plot_points.append({
                    "content": f"In episode '{episode.get('title')}', during the '{beat.get('name')}' beat: {beat.get('description')}",
                    "metadata": {
                        "beat": beat.get("name"),
                        "episode_title": episode.get("title"),
                        "episode_number": episode.get("episode_number")
                    }
                })
        
        # Extract from scenes
        if "scenes" in episode:
            for scene in episode["scenes"]:
                if "plot" in scene:
                    plot_points.append({
                        "content": f"In episode '{episode.get('title')}', scene {scene.get('scene_number', 0)}: {scene.get('plot')}",
                        "metadata": {
                            "scene_number": scene.get("scene_number", 0),
                            "beat": scene.get("beat"),
                            "episode_title": episode.get("title"),
                            "episode_number": episode.get("episode_number")
                        }
                    })
        
        return plot_points
    
    def _extract_character_developments(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract character developments from an episode.
        
        Args:
            episode: Episode data
        
        Returns:
            List of character development memory entries
        """
        developments = []
        
        # First, get character information
        characters = {char.get("name"): char for char in episode.get("characters", [])}
        
        # Extract from script if available
        if episode.get("script") and episode["script"].get("scenes"):
            for scene in episode["script"]["scenes"]:
                # Get all dialogue lines for each character
                character_lines = {}
                for line in scene.get("lines", []):
                    if line.get("type") == "dialogue":
                        char_name = line.get("character")
                        if char_name not in character_lines:
                            character_lines[char_name] = []
                        character_lines[char_name].append(line.get("content", ""))
                
                # Look for character development in dialogue
                for char_name, lines in character_lines.items():
                    # Join lines for this character in this scene
                    char_dialogue = " ".join(lines)
                    
                    # Look for signs of character development in dialogue
                    dev_indicators = ["I've never", "I've learned", "I realize", "I understand",
                                    "I feel", "I've changed", "I used to", "I think", "I believe"]
                    
                    for indicator in dev_indicators:
                        if indicator.lower() in char_dialogue.lower():
                            # Extract the sentence containing the indicator
                            sentences = re.split(r'[.!?]+', char_dialogue)
                            relevant_sentence = next((s for s in sentences 
                                                  if indicator.lower() in s.lower()), "")
                            
                            if relevant_sentence:
                                developments.append({
                                    "content": f"Character Development for {char_name} in episode '{episode.get('title')}': {relevant_sentence.strip()}",
                                    "metadata": {
                                        "character": char_name,
                                        "episode_title": episode.get("title"),
                                        "episode_number": episode.get("episode_number"),
                                        "scene_number": scene.get("scene_number", 0)
                                    }
                                })
        
        # Add basic character introductions if this is their first appearance
        for char_name, char_data in characters.items():
            developments.append({
                "content": f"Character Introduction: {char_name} is a {char_data.get('species', 'unknown')} {char_data.get('role', 'crew member')} who appears in episode '{episode.get('title')}'. {char_data.get('personality', '')}",
                "metadata": {
                    "character": char_name,
                    "episode_title": episode.get("title"),
                    "episode_number": episode.get("episode_number"),
                    "character_role": char_data.get("role"),
                    "character_species": char_data.get("species")
                }
            })
        
        return developments
    
    def _extract_world_building(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract world-building elements from an episode.
        
        Args:
            episode: Episode data
        
        Returns:
            List of world-building memory entries
        """
        world_building = []
        
        # Extract from scenes
        if "scenes" in episode:
            for scene in episode["scenes"]:
                if "setting" in scene:
                    world_building.append({
                        "content": f"Setting in episode '{episode.get('title')}': {scene.get('setting')}",
                        "metadata": {
                            "type": "setting",
                            "episode_title": episode.get("title"),
                            "episode_number": episode.get("episode_number"),
                            "scene_number": scene.get("scene_number", 0)
                        }
                    })
        
        # Extract from script descriptions
        if episode.get("script") and episode["script"].get("scenes"):
            for scene in episode["script"]["scenes"]:
                for line in scene.get("lines", []):
                    if line.get("type") == "description":
                        # Look for setting descriptions
                        content = line.get("content", "")
                        
                        # Only include substantial descriptions
                        if len(content) > 40 and re.search(r'(starship|planet|space|station|base|world|alien|technology)', 
                                                         content, re.IGNORECASE):
                            world_building.append({
                                "content": f"World detail from episode '{episode.get('title')}': {content}",
                                "metadata": {
                                    "type": "description",
                                    "episode_title": episode.get("title"),
                                    "episode_number": episode.get("episode_number"),
                                    "scene_number": scene.get("scene_number", 0)
                                }
                            })
        
        return world_building
    
    def _extract_continuity_points(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract continuity points from an episode.
        
        Args:
            episode: Episode data
        
        Returns:
            List of continuity memory entries
        """
        continuity = []
        
        # Add basic episode information for continuity
        continuity.append({
            "content": f"Episode '{episode.get('title')}' (#{episode.get('episode_number')}) in series '{episode.get('series')}' deals with the theme of {episode.get('theme', 'space exploration')}.",
            "metadata": {
                "type": "episode_summary",
                "episode_title": episode.get("title"),
                "episode_number": episode.get("episode_number"),
                "series": episode.get("series")
            }
        })
        
        # Extract from script dialogue references to past events
        if episode.get("script") and episode["script"].get("scenes"):
            for scene in episode["script"]["scenes"]:
                for line in scene.get("lines", []):
                    if line.get("type") == "dialogue":
                        content = line.get("content", "")
                        
                        # Look for references to past events
                        past_indicators = ["remember when", "last time", "previously", "before",
                                          "used to", "back when", "last mission", "last episode"]
                        
                        for indicator in past_indicators:
                            if indicator.lower() in content.lower():
                                # Extract the sentence containing the indicator
                                sentences = re.split(r'[.!?]+', content)
                                relevant_sentence = next((s for s in sentences 
                                                      if indicator.lower() in s.lower()), "")
                                
                                if relevant_sentence:
                                    continuity.append({
                                        "content": f"Continuity reference from {line.get('character')} in episode '{episode.get('title')}': {relevant_sentence.strip()}",
                                        "metadata": {
                                            "type": "dialogue_reference",
                                            "character": line.get("character"),
                                            "episode_title": episode.get("title"),
                                            "episode_number": episode.get("episode_number"),
                                            "scene_number": scene.get("scene_number", 0)
                                        }
                                    })
        
        return continuity
    
    def _extract_relationships(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract relationship developments from an episode.
        
        Args:
            episode: Episode data
        
        Returns:
            List of relationship memory entries
        """
        relationships = []
        
        # Extract from script interactions
        if episode.get("script") and episode["script"].get("scenes"):
            # Track character interactions by scene
            scene_interactions = {}
            
            for scene in episode["script"]["scenes"]:
                scene_number = scene.get("scene_number", 0)
                scene_interactions[scene_number] = {}
                
                # Track speaking characters
                speaking_chars = set()
                
                for line in scene.get("lines", []):
                    if line.get("type") == "dialogue":
                        char_name = line.get("character")
                        speaking_chars.add(char_name)
                        
                        # Analyze dialogue for relationship indicators
                        content = line.get("content", "")
                        
                        # Check if addressing another character
                        for other_char in speaking_chars:
                            if other_char != char_name and other_char in content:
                                # Store the interaction
                                pair_key = tuple(sorted([char_name, other_char]))
                                if pair_key not in scene_interactions[scene_number]:
                                    scene_interactions[scene_number][pair_key] = []
                                
                                scene_interactions[scene_number][pair_key].append(content)
            
            # Generate relationship memories from interactions
            for scene_number, interactions in scene_interactions.items():
                for (char1, char2), dialogues in interactions.items():
                    # Only consider substantial interactions
                    if len(dialogues) >= 2:
                        relationships.append({
                            "content": f"Relationship between {char1} and {char2} in episode '{episode.get('title')}': They interact in scene {scene_number} with dialogue including: '{dialogues[0][:100]}...'",
                            "metadata": {
                                "characters": [char1, char2],
                                "episode_title": episode.get("title"),
                                "episode_number": episode.get("episode_number"),
                                "scene_number": scene_number
                            }
                        })
        
        return relationships
    
    def _extract_character_states(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract character states at the end of an episode.
        
        Args:
            episode: Episode data
            
        Returns:
            List of character state memory entries
        """
        states = []
        characters = episode.get("characters", [])
        
        # Extract final character states from script
        if episode.get("script") and episode["script"].get("scenes"):
            # Get last scene for final states
            last_scene = episode["script"]["scenes"][-1] if episode["script"]["scenes"] else None
            
            if last_scene:
                for line in last_scene.get("lines", []):
                    if line.get("type") == "dialogue":
                        char_name = line.get("speaker", "").strip()
                        if not char_name:
                            char_name = line.get("character", "").strip()
                        if char_name:
                            # Extract emotional/physical state indicators
                            content = line.get("content", "")
                            state_indicators = ["feel", "feeling", "am", "seem", "appear", 
                                              "look", "sound", "acting"]
                            
                            for indicator in state_indicators:
                                if indicator.lower() in content.lower():
                                    states.append({
                                        "content": f"Final state of {char_name} in episode '{episode.get('title')}': {content[:200]}",
                                        "metadata": {
                                            "character": char_name,
                                            "episode_title": episode.get("title"),
                                            "episode_number": episode.get("episode_number"),
                                            "type": "final_state",
                                            "scene_number": last_scene.get("scene_number", 0)
                                        }
                                    })
                                    break
        
        # Add basic character presence
        for char in characters:
            char_name = char.get("name")
            states.append({
                "content": f"{char_name} is part of the crew in episode '{episode.get('title')}'",
                "metadata": {
                    "character": char_name,
                    "episode_title": episode.get("title"),
                    "episode_number": episode.get("episode_number"),
                    "type": "presence"
                }
            })
        
        return states
    
    def _extract_unresolved_threads(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract unresolved plot threads and questions.
        
        Args:
            episode: Episode data
            
        Returns:
            List of unresolved thread memory entries
        """
        threads = []
        
        # Extract from script for questions and mysteries
        if episode.get("script") and episode["script"].get("scenes"):
            for scene in episode["script"]["scenes"]:
                for line in scene.get("lines", []):
                    if line.get("type") == "dialogue":
                        content = line.get("content", "")
                        
                        # Look for question marks and mystery indicators
                        if "?" in content:
                            # Check if it's a plot-related question
                            question_keywords = ["what", "why", "how", "who", "where", "when",
                                               "mystery", "unknown", "unclear", "wonder",
                                               "question", "investigate"]
                            
                            if any(keyword in content.lower() for keyword in question_keywords):
                                speaker = line.get("speaker", "").strip()
                                if not speaker:
                                    speaker = line.get("character", "").strip()
                                threads.append({
                                    "content": f"Unresolved question in episode '{episode.get('title')}': {content}",
                                    "metadata": {
                                        "character": speaker,
                                        "episode_title": episode.get("title"),
                                        "episode_number": episode.get("episode_number"),
                                        "scene_number": scene.get("scene_number", 0),
                                        "type": "question"
                                    }
                                })
        
        # Check if episode ends with a cliffhanger or open question
        if episode.get("script") and episode["script"].get("scenes"):
            last_scene = episode["script"]["scenes"][-1]
            last_lines = last_scene.get("lines", [])[-3:]  # Last 3 lines
            
            for line in last_lines:
                if line.get("type") == "description":
                    content = line.get("content", "")
                    cliffhanger_keywords = ["remains to be seen", "only time will tell",
                                          "what happens next", "uncertain", "mystery",
                                          "unanswered", "unknown"]
                    
                    if any(keyword in content.lower() for keyword in cliffhanger_keywords):
                        threads.append({
                            "content": f"Open thread at end of episode '{episode.get('title')}': {content}",
                            "metadata": {
                                "episode_title": episode.get("title"),
                                "episode_number": episode.get("episode_number"),
                                "scene_number": last_scene.get("scene_number", 0),
                                "type": "cliffhanger"
                            }
                        })
        
        return threads
    
    def save_memories_to_json(self, episode_id: str, memories: Dict[str, List[Dict[str, Any]]]) -> bool:
        """Save extracted memories to a JSON file for backup and reference.
        
        Args:
            episode_id: ID of the episode
            memories: Dictionary of memory entries by category
            
        Returns:
            Success status
        """
        try:
            episode_dir = self.episodes_dir / episode_id
            episode_dir.mkdir(parents=True, exist_ok=True)
            
            memories_file = episode_dir / "memories.json"
            
            # Prepare data for JSON
            json_data = {
                "episode_id": episode_id,
                "extracted_at": time.time(),
                "categories": memories
            }
            
            with open(memories_file, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved memories to {memories_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving memories to JSON: {e}")
            return False
    
    def load_memories_from_json(self, episode_id: str) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """Load memories from JSON file if it exists.
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            Dictionary of memory entries by category, or None if not found
        """
        try:
            episode_dir = self.episodes_dir / episode_id
            memories_file = episode_dir / "memories.json"
            
            if not memories_file.exists():
                return None
            
            with open(memories_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            return data.get("categories", {})
            
        except Exception as e:
            logger.error(f"Error loading memories from JSON: {e}")
            return None
    
    def add_memory(self, content: str, category: str, episode_id: str, 
                  metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add an episode memory entry.
        
        Args:
            content: Text content for the memory
            category: Category of memory (plot_point, character_development, etc.)
            episode_id: ID of the related episode
            metadata: Additional metadata
        
        Returns:
            Result of the memory addition
        """
        if not metadata:
            metadata = {}
        
        # Add required fields to metadata
        metadata.update({
            "category": category,
            "episode_id": episode_id,
            "created_at": time.time()
        })
        # Ensure series is present for cross-episode filtering (Mem0 + prompts)
        ep_obj = self._load_episode_data(episode_id)
        if ep_obj and ep_obj.get('series'):
            metadata.setdefault('series', ep_obj.get('series'))

        # Add to memory
        return self.mem0_client.add_episode_memory(
            content=content,
            episode_id=episode_id,
            metadata=metadata
        )
    
    def search_memories(self, query: str, category: Optional[str] = None, 
                       episode_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Search episode memories for relevant information.
        
        Args:
            query: Search query
            category: Optional memory category to filter by
            episode_id: Optional episode ID to filter by
            limit: Maximum number of results to return
        
        Returns:
            List of matching memory entries
        """
        memories = self.mem0_client.search_episode_memories(
            query=query,
            episode_id=episode_id,
            limit=limit
        )
        
        # Filter by category if specified
        if category and memories:
            memories = [m for m in memories 
                       if m.get('metadata', {}).get('category') == category]
        
        return memories
    
    def get_all_memories(self, episode_id: Optional[str] = None, 
                        category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all episode memories, optionally filtered.
        
        Args:
            episode_id: Optional episode ID to filter by
            category: Optional memory category to filter by
        
        Returns:
            List of memory entries
        """
        # Get all episode memories
        memories = self.mem0_client.get_all_memories(
            user_id="episodes",
            memory_type=self.mem0_client.EPISODE_MEMORY
        )
        
        # Filter by episode ID if specified
        if episode_id:
            memories = [m for m in memories 
                       if m.get('metadata', {}).get('episode_id') == episode_id]
        
        # Filter by category if specified
        if category:
            memories = [m for m in memories 
                       if m.get('metadata', {}).get('category') == category]
        
        return memories
    
    def get_character_memories(self, character_name: str) -> List[Dict[str, Any]]:
        """Get all memories related to a specific character.
        
        Args:
            character_name: Name of the character
        
        Returns:
            List of memory entries about the character
        """
        # Search for character-specific memories
        memories = self.mem0_client.search_episode_memories(
            query=character_name,
            limit=50  # Get a large number of results
        )
        
        # Filter to only include memories explicitly about this character
        filtered_memories = []
        for memory in memories:
            metadata = memory.get('metadata', {})
            
            # Include character development memories for this character
            if (metadata.get('category') == self.CHARACTER_DEVELOPMENT and 
                metadata.get('character') == character_name):
                filtered_memories.append(memory)
            
            # Include relationship memories involving this character
            elif (metadata.get('category') == self.RELATIONSHIP and 
                 character_name in metadata.get('characters', [])):
                filtered_memories.append(memory)
            
            # For other memory types, check if the character is mentioned prominently
            elif (character_name.lower() in memory.get('memory', '').lower() and
                 re.search(r'\b' + re.escape(character_name) + r'\b', 
                          memory.get('memory', ''), re.IGNORECASE)):
                filtered_memories.append(memory)
        
        return filtered_memories
    
    def get_timeline(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get a chronological timeline of key events.
        
        Returns:
            Dictionary of episode IDs mapped to key plot points
        """
        # Get all continuity and plot point memories
        continuity_memories = self.get_all_memories(category=self.CONTINUITY)
        plot_memories = self.get_all_memories(category=self.PLOT_POINT)
        
        # Organize by episode
        timeline = {}
        
        for memory in continuity_memories + plot_memories:
            metadata = memory.get('metadata', {})
            episode_id = metadata.get('episode_id')
            
            if not episode_id:
                continue
            
            if episode_id not in timeline:
                timeline[episode_id] = []
            
            # Extract key information
            episode_title = metadata.get('episode_title', 'Unknown Episode')
            episode_number = metadata.get('episode_number', 0)
            
            # Add to timeline with sorting metadata
            timeline[episode_id].append({
                "memory_id": memory.get('id'),
                "content": memory.get('memory', ''),
                "category": metadata.get('category'),
                "episode_title": episode_title,
                "episode_number": episode_number,
                "scene_number": metadata.get('scene_number', 0) if 'scene_number' in metadata else 0,
                "type": metadata.get('type', 'general')
            })
        
        # Sort each episode's events by scene number
        for episode_id in timeline:
            timeline[episode_id].sort(key=lambda x: (x.get('scene_number', 0), x.get('memory_id', '')))
        
        return timeline
    
    def get_previous_episode_context(self, current_episode_number: int, 
                                     series: Optional[str] = None,
                                     limit: int = 20) -> Dict[str, Any]:
        """Get relevant context from previous episodes for continuity.
        
        Args:
            current_episode_number: Episode number of the current episode
            series: Optional series name to filter by
            limit: Maximum number of memories to retrieve
            
        Returns:
            Dictionary with context organized by category
        """
        # Get all recent memories
        all_memories = self.get_all_memories()

        # Filter to previous episodes
        previous_memories = []
        for memory in all_memories:
            metadata = memory.get('metadata', {})
            ep_num = metadata.get('episode_number', 0)

            # Include memories from previous episodes
            if ep_num > 0 and ep_num < current_episode_number:
                series_meta = metadata.get('series')
                if not series:
                    match_series = True
                elif series_meta is None or series_meta == '':
                    # Legacy rows without series still count for continuity
                    match_series = True
                else:
                    match_series = series_meta == series
                if match_series:
                    previous_memories.append(memory)
        
        # Sort by episode number (most recent first)
        previous_memories.sort(key=lambda x: x.get('metadata', {}).get('episode_number', 0), 
                              reverse=True)
        
        # Limit results
        previous_memories = previous_memories[:limit]
        
        # Organize by category
        context = {
            "plot_points": [],
            "character_states": [],
            "unresolved_threads": [],
            "relationships": [],
            "world_building": []
        }
        
        for memory in previous_memories:
            metadata = memory.get('metadata', {})
            category = metadata.get('category')
            content = memory.get('memory', '')
            
            if category == self.PLOT_POINT:
                context["plot_points"].append(content)
            elif category == self.CHARACTER_STATE:
                context["character_states"].append(content)
            elif category == self.UNRESOLVED_THREAD:
                context["unresolved_threads"].append(content)
            elif category == self.RELATIONSHIP:
                context["relationships"].append(content)
            elif category == self.WORLD_BUILDING:
                context["world_building"].append(content)
        
        return context
    
    def get_character_continuity_context(self, character_name: str, 
                                        current_episode_number: int) -> List[str]:
        """Get continuity context for a specific character.
        
        Args:
            character_name: Name of the character
            current_episode_number: Current episode number
            
        Returns:
            List of context strings about the character
        """
        # Get character memories from previous episodes
        character_memories = self.get_character_memories(character_name)
        
        # Filter to previous episodes only
        previous_memories = []
        for memory in character_memories:
            metadata = memory.get('metadata', {})
            ep_num = metadata.get('episode_number', 0)
            
            if ep_num > 0 and ep_num < current_episode_number:
                previous_memories.append(memory.get('memory', ''))
        
        # Return most recent first (limit 10)
        return previous_memories[:10]

# Singleton instance
_episode_memory = None

def get_episode_memory() -> EpisodeMemory:
    """Get the EpisodeMemory singleton instance."""
    global _episode_memory
    
    if _episode_memory is None:
        _episode_memory = EpisodeMemory()
    
    return _episode_memory

def extract_memories(episode_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Extract and store memories from an episode.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        Dictionary of memory entries by category
    """
    memory_manager = get_episode_memory()
    return memory_manager.extract_memories_from_episode(episode_id)

def add_memory(content: str, category: str, episode_id: str,
              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Add an episode memory entry.
    
    Args:
        content: Text content for the memory
        category: Category of memory
        episode_id: ID of the related episode
        metadata: Additional metadata
    
    Returns:
        Result of the memory addition
    """
    memory_manager = get_episode_memory()
    return memory_manager.add_memory(content, category, episode_id, metadata)

def search_memories(query: str, category: Optional[str] = None,
                  episode_id: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """Search episode memories.
    
    Args:
        query: Search query
        category: Optional memory category to filter by
        episode_id: Optional episode ID to filter by
        limit: Maximum number of results to return
    
    Returns:
        List of matching memory entries
    """
    memory_manager = get_episode_memory()
    return memory_manager.search_memories(query, category, episode_id, limit)

def get_timeline() -> Dict[str, List[Dict[str, Any]]]:
    """Get a chronological timeline of key events.
    
    Returns:
        Dictionary of episode IDs mapped to key plot points
    """
    memory_manager = get_episode_memory()
    return memory_manager.get_timeline()

def get_character_history(character_name: str) -> List[Dict[str, Any]]:
    """Get the development history of a character.
    
    Args:
        character_name: Name of the character
    
    Returns:
        List of memory entries about the character
    """
    memory_manager = get_episode_memory()
    return memory_manager.get_character_memories(character_name)