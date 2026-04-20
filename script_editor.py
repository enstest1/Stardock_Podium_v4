#!/usr/bin/env python
"""
Script Editor Module for Stardock Podium.

This module allows manual editing, regeneration flagging, and revision history
of AI-generated scripts before audio production.
"""

import os
import json
import logging
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import uuid

from script_line_ids import ensure_script_line_ids
import tempfile
import subprocess
import shutil

# Try to import OpenAI
try:
    from openai import OpenAI
except ImportError:
    logging.error("OpenAI not found. Please install it with: pip install openai")
    raise

# Local imports
from story_structure import get_story_structure, get_episode, generate_characters, generate_scenes, generate_script

# Setup logging
logger = logging.getLogger(__name__)

class ScriptEditor:
    """Editor for episode scripts with revision history and scene regeneration."""
    
    def __init__(self, episodes_dir: str = "episodes"):
        """Initialize the script editor.
        
        Args:
            episodes_dir: Directory containing episode data
        """
        self.episodes_dir = Path(episodes_dir)
        
        # Initialize OpenAI client for regeneration
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        
        # Initialize story structure
        self.story_structure = get_story_structure()
    
    def load_episode_script(self, episode_id: str) -> Dict[str, Any]:
        """Load the script for an episode.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Dictionary with script data
        """
        episode_dir = self.episodes_dir / episode_id
        script_file = episode_dir / "script.json"
        
        if not script_file.exists():
            logger.error(f"Script file not found: {script_file}")
            return {}
        
        try:
            with open(script_file, 'r') as f:
                script = json.load(f)
            
            return script
        except Exception as e:
            logger.error(f"Error loading script: {e}")
            return {}
    
    def save_script(self, script: Dict[str, Any]) -> bool:
        """Save a script to file, with revision history.
        
        Args:
            script: Updated script data
        
        Returns:
            Success status
        """
        if not script or 'episode_id' not in script:
            logger.error("Invalid script data: missing episode_id")
            return False
        
        episode_id = script['episode_id']
        episode_dir = self.episodes_dir / episode_id
        
        if not episode_dir.exists():
            logger.error(f"Episode directory not found: {episode_dir}")
            return False
        
        # Create revisions directory if it doesn't exist
        revisions_dir = episode_dir / "revisions"
        revisions_dir.mkdir(exist_ok=True)
        
        # Check if current script exists to create a revision
        script_file = episode_dir / "script.json"
        if script_file.exists():
            try:
                # Create revision of current script
                with open(script_file, 'r') as f:
                    current_script = json.load(f)
                
                # Generate revision ID and timestamp
                revision = {
                    "revision_id": f"rev_{uuid.uuid4().hex[:8]}",
                    "timestamp": time.time(),
                    "script": current_script
                }
                
                # Save revision
                revision_file = revisions_dir / f"{revision['revision_id']}.json"
                with open(revision_file, 'w') as f:
                    json.dump(revision, f, indent=2)
                
                logger.info(f"Created script revision: {revision['revision_id']}")
            
            except Exception as e:
                logger.error(f"Error creating script revision: {e}")
        
        # Save new script
        try:
            # Update modified timestamp
            script['updated_at'] = time.time()
            ensure_script_line_ids(script)

            with open(script_file, 'w') as f:
                json.dump(script, f, indent=2)
            
            logger.info(f"Saved script for episode {episode_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving script: {e}")
            return False
    
    def preview_scene_flow(self, script: Dict[str, Any]) -> List[str]:
        """Generate a preview of the scene flow in the script.
        
        Args:
            script: Script data
        
        Returns:
            List of scene summaries
        """
        if not script or 'scenes' not in script:
            logger.error("Invalid script data: missing scenes")
            return []
        
        scene_summaries = []
        
        for i, scene in enumerate(script['scenes']):
            # Extract basic info
            scene_number = scene.get('scene_number', i + 1)
            beat = scene.get('beat', 'Unknown beat')
            setting = scene.get('setting', 'Unknown setting')
            
            # Count dialogue lines by character
            character_lines = {}
            for line in scene.get('lines', []):
                if line.get('type') == 'dialogue':
                    character = line.get('character', 'Unknown')
                    if character not in character_lines:
                        character_lines[character] = 0
                    character_lines[character] += 1
            
            # Create character summary
            character_summary = ", ".join([f"{char} ({count} lines)" 
                                         for char, count in character_lines.items()])
            
            # Create scene summary
            summary = f"Scene {scene_number}: {beat} - {setting}"
            if character_summary:
                summary += f" - Characters: {character_summary}"
            
            scene_summaries.append(summary)
        
        return scene_summaries
    
    def update_line(self, script: Dict[str, Any], scene_index: int, 
                   line_index: int, new_text: str) -> Dict[str, Any]:
        """Update a specific line in the script.
        
        Args:
            script: Script data
            scene_index: Index of the scene
            line_index: Index of the line within the scene
            new_text: New content for the line
        
        Returns:
            Updated script
        """
        # Validate inputs
        if not script or 'scenes' not in script:
            logger.error("Invalid script data: missing scenes")
            return script
        
        if scene_index < 0 or scene_index >= len(script['scenes']):
            logger.error(f"Invalid scene index: {scene_index}")
            return script
        
        scene = script['scenes'][scene_index]
        
        if 'lines' not in scene:
            logger.error(f"Scene has no lines: {scene_index}")
            return script
        
        if line_index < 0 or line_index >= len(scene['lines']):
            logger.error(f"Invalid line index: {line_index}")
            return script
        
        # Update the line
        line = scene['lines'][line_index]
        line['content'] = new_text
        
        # Mark as manually edited
        if 'edit_history' not in line:
            line['edit_history'] = []
        
        line['edit_history'].append({
            "timestamp": time.time(),
            "type": "manual_edit"
        })
        
        return script
    
    def mark_scene_for_regeneration(self, script: Dict[str, Any], scene_index: int) -> Dict[str, Any]:
        """Mark a scene for regeneration.
        
        Args:
            script: Script data
            scene_index: Index of the scene
        
        Returns:
            Updated script
        """
        # Validate inputs
        if not script or 'scenes' not in script:
            logger.error("Invalid script data: missing scenes")
            return script
        
        if scene_index < 0 or scene_index >= len(script['scenes']):
            logger.error(f"Invalid scene index: {scene_index}")
            return script
        
        # Mark the scene
        scene = script['scenes'][scene_index]
        scene['needs_regeneration'] = True
        
        if 'edit_history' not in scene:
            scene['edit_history'] = []
        
        scene['edit_history'].append({
            "timestamp": time.time(),
            "type": "marked_for_regeneration"
        })
        
        return script
    
    def regenerate_scene(self, episode_id: str, scene_index: int,
                        instructions: Optional[str] = None) -> Dict[str, Any]:
        """Regenerate a specific scene with optional instructions.
        
        Args:
            episode_id: ID of the episode
            scene_index: Index of the scene to regenerate
            instructions: Optional special instructions for regeneration
        
        Returns:
            Updated script with regenerated scene
        """
        # Load episode and script
        episode = get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return {}
        
        script = self.load_episode_script(episode_id)
        if not script:
            logger.error(f"Script not found for episode: {episode_id}")
            return {}
        
        # Validate scene index
        if 'scenes' not in script:
            logger.error("Invalid script data: missing scenes")
            return script
        
        if scene_index < 0 or scene_index >= len(script['scenes']):
            logger.error(f"Invalid scene index: {scene_index}")
            return script
        
        # Get the scene to regenerate
        scene = script['scenes'][scene_index]
        
        # Get character information
        character_info = ""
        for char in episode.get('characters', []):
            character_info += f"{char.get('name', '')}: {char.get('species', '')} - {char.get('role', '')}\n"
        
        # Create context for regeneration
        context = (
            f"Title: {episode.get('title', '')}\n"
            f"Theme: {episode.get('theme', '')}\n"
            f"Beat: {scene.get('beat', '')}\n"
            f"Setting: {scene.get('setting', '')}\n"
            f"Scene Number: {scene.get('scene_number', scene_index + 1)}\n\n"
            f"Character Information:\n{character_info}\n"
        )
        
        # Add special instructions if provided
        special_instructions = ""
        if instructions:
            special_instructions = f"Special Instructions: {instructions}\n\n"
        
        # Construct prompt
        prompt = f"""
        You are tasked with regenerating a scene for a Star Trek-style podcast episode.
        
        CONTEXT:
        {context}
        
        {special_instructions}
        
        Please write a detailed scene script that maintains the same setting and beat as the original scene,
        but potentially improves the dialogue, pacing, and dramatic elements.
        
        Format the scene script as follows:
        1. Brief setting descriptions in [brackets]
        2. Character names in ALL CAPS, followed by their dialogue
        3. Sound effects in (parentheses)
        4. Narrator sections marked as NARRATOR
        """
        
        try:
            # Generate new scene content
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
            new_content = response.choices[0].message.content
            new_lines = self._parse_script_lines(new_content)
            
            # Update the scene
            scene['lines'] = new_lines
            scene.pop('needs_regeneration', None)  # Remove regeneration flag
            
            # Add to edit history
            if 'edit_history' not in scene:
                scene['edit_history'] = []
            
            scene['edit_history'].append({
                "timestamp": time.time(),
                "type": "regenerated",
                "instructions": instructions
            })
            
            # Save the updated script
            self.save_script(script)
            
            return script
        
        except Exception as e:
            logger.error(f"Error regenerating scene: {e}")
            return script
    
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
    
    def get_revisions(self, episode_id: str) -> List[Dict[str, Any]]:
        """Get all revisions for an episode script.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            List of revision metadata
        """
        episode_dir = self.episodes_dir / episode_id
        revisions_dir = episode_dir / "revisions"
        
        if not revisions_dir.exists():
            return []
        
        revisions = []
        
        for revision_file in revisions_dir.glob("*.json"):
            try:
                with open(revision_file, 'r') as f:
                    revision = json.load(f)
                
                # Extract metadata only
                revisions.append({
                    "revision_id": revision.get("revision_id"),
                    "timestamp": revision.get("timestamp"),
                    "file": revision_file.name
                })
            
            except Exception as e:
                logger.error(f"Error reading revision file {revision_file}: {e}")
        
        # Sort by timestamp
        revisions.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        
        return revisions
    
    def load_revision(self, episode_id: str, revision_id: str) -> Dict[str, Any]:
        """Load a specific revision of a script.
        
        Args:
            episode_id: ID of the episode
            revision_id: ID of the revision
        
        Returns:
            Revision script data
        """
        episode_dir = self.episodes_dir / episode_id
        revision_file = episode_dir / "revisions" / f"{revision_id}.json"
        
        if not revision_file.exists():
            logger.error(f"Revision file not found: {revision_file}")
            return {}
        
        try:
            with open(revision_file, 'r') as f:
                revision = json.load(f)
            
            return revision.get("script", {})
        
        except Exception as e:
            logger.error(f"Error loading revision: {e}")
            return {}
    
    def restore_revision(self, episode_id: str, revision_id: str) -> Dict[str, Any]:
        """Restore a script to a previous revision.
        
        Args:
            episode_id: ID of the episode
            revision_id: ID of the revision to restore
        
        Returns:
            Restored script
        """
        # Load the revision
        revision_script = self.load_revision(episode_id, revision_id)
        if not revision_script:
            logger.error(f"Failed to load revision: {revision_id}")
            return {}
        
        # Save as current script
        if self.save_script(revision_script):
            logger.info(f"Restored script to revision: {revision_id}")
            return revision_script
        else:
            logger.error(f"Failed to restore script to revision: {revision_id}")
            return {}
    
    def compare_revisions(self, episode_id: str, revision_id_a: str, 
                         revision_id_b: Optional[str] = None) -> Dict[str, Any]:
        """Compare two script revisions.
        
        Args:
            episode_id: ID of the episode
            revision_id_a: ID of the first revision
            revision_id_b: Optional ID of the second revision (current if None)
        
        Returns:
            Dictionary with comparison results
        """
        # Load first revision
        script_a = self.load_revision(episode_id, revision_id_a)
        if not script_a:
            logger.error(f"Failed to load revision A: {revision_id_a}")
            return {"error": f"Failed to load revision A: {revision_id_a}"}
        
        # Load second revision or current script
        if revision_id_b:
            script_b = self.load_revision(episode_id, revision_id_b)
            if not script_b:
                logger.error(f"Failed to load revision B: {revision_id_b}")
                return {"error": f"Failed to load revision B: {revision_id_b}"}
        else:
            script_b = self.load_episode_script(episode_id)
            if not script_b:
                logger.error(f"Failed to load current script for episode: {episode_id}")
                return {"error": f"Failed to load current script for episode: {episode_id}"}
        
        # Compare scenes
        comparison = {
            "revision_a": revision_id_a,
            "revision_b": revision_id_b or "current",
            "scene_changes": [],
            "overall_similarity": 0.0
        }
        
        # Check that both scripts have scenes
        if 'scenes' not in script_a or 'scenes' not in script_b:
            return {"error": "One or both scripts are missing scenes"}
        
        # Compare each scene
        a_scenes = script_a['scenes']
        b_scenes = script_b['scenes']
        
        # Count total scenes in both scripts
        total_scenes = max(len(a_scenes), len(b_scenes))
        matched_scenes = 0
        
        for i in range(total_scenes):
            if i < len(a_scenes) and i < len(b_scenes):
                # Both scripts have this scene
                scene_a = a_scenes[i]
                scene_b = b_scenes[i]
                
                # Compare scene attributes
                scene_comparison = self._compare_scenes(scene_a, scene_b)
                comparison["scene_changes"].append(scene_comparison)
                
                # Update matched scenes count
                if scene_comparison.get("similarity", 0) > 0.7:
                    matched_scenes += 1
            
            elif i < len(a_scenes):
                # Scene exists in A but not in B
                comparison["scene_changes"].append({
                    "scene_number": i + 1,
                    "action": "removed",
                    "similarity": 0.0,
                    "details": f"Scene {i + 1} from revision A is not present in revision B"
                })
            
            else:
                # Scene exists in B but not in A
                comparison["scene_changes"].append({
                    "scene_number": i + 1,
                    "action": "added",
                    "similarity": 0.0,
                    "details": f"Scene {i + 1} is new in revision B"
                })
        
        # Calculate overall similarity
        comparison["overall_similarity"] = matched_scenes / total_scenes if total_scenes > 0 else 1.0
        
        return comparison
    
    def _compare_scenes(self, scene_a: Dict[str, Any], scene_b: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two scenes for differences.
        
        Args:
            scene_a: First scene
            scene_b: Second scene
        
        Returns:
            Dictionary with comparison results
        """
        scene_number = scene_a.get('scene_number', 0)
        
        # Check for basic attribute changes
        attribute_changes = []
        for attr in ['beat', 'setting']:
            if scene_a.get(attr) != scene_b.get(attr):
                attribute_changes.append({
                    "attribute": attr,
                    "previous": scene_a.get(attr),
                    "current": scene_b.get(attr)
                })
        
        # Compare lines
        lines_a = scene_a.get('lines', [])
        lines_b = scene_b.get('lines', [])
        
        line_changes = []
        
        # Count total lines in both scenes
        total_lines = max(len(lines_a), len(lines_b))
        matched_lines = 0
        
        for i in range(total_lines):
            if i < len(lines_a) and i < len(lines_b):
                # Both scenes have this line
                line_a = lines_a[i]
                line_b = lines_b[i]
                
                # Check if line type changed
                type_changed = line_a.get('type') != line_b.get('type')
                
                # Check if content changed
                content_changed = line_a.get('content') != line_b.get('content')
                
                # Check if character changed (for dialogue)
                character_changed = False
                if line_a.get('type') == 'dialogue' and line_b.get('type') == 'dialogue':
                    character_changed = line_a.get('character') != line_b.get('character')
                
                if type_changed or content_changed or character_changed:
                    line_changes.append({
                        "line_number": i + 1,
                        "type_changed": type_changed,
                        "content_changed": content_changed,
                        "character_changed": character_changed,
                        "previous": {
                            "type": line_a.get('type'),
                            "content": line_a.get('content')[:50] + "..." if len(line_a.get('content', '')) > 50 else line_a.get('content', ''),
                            "character": line_a.get('character') if line_a.get('type') == 'dialogue' else None
                        },
                        "current": {
                            "type": line_b.get('type'),
                            "content": line_b.get('content')[:50] + "..." if len(line_b.get('content', '')) > 50 else line_b.get('content', ''),
                            "character": line_b.get('character') if line_b.get('type') == 'dialogue' else None
                        }
                    })
                else:
                    # Lines are the same
                    matched_lines += 1
            
            elif i < len(lines_a):
                # Line exists in A but not in B
                line_changes.append({
                    "line_number": i + 1,
                    "action": "removed",
                    "previous": {
                        "type": lines_a[i].get('type'),
                        "content": lines_a[i].get('content')[:50] + "..." if len(lines_a[i].get('content', '')) > 50 else lines_a[i].get('content', ''),
                        "character": lines_a[i].get('character') if lines_a[i].get('type') == 'dialogue' else None
                    }
                })
            
            else:
                # Line exists in B but not in A
                line_changes.append({
                    "line_number": i + 1,
                    "action": "added",
                    "current": {
                        "type": lines_b[i].get('type'),
                        "content": lines_b[i].get('content')[:50] + "..." if len(lines_b[i].get('content', '')) > 50 else lines_b[i].get('content', ''),
                        "character": lines_b[i].get('character') if lines_b[i].get('type') == 'dialogue' else None
                    }
                })
        
        # Calculate line similarity
        line_similarity = matched_lines / total_lines if total_lines > 0 else 1.0
        
        # Calculate overall scene similarity
        attribute_similarity = 1.0 - (len(attribute_changes) / 2)  # 2 possible attributes
        scene_similarity = (line_similarity * 0.8) + (attribute_similarity * 0.2)
        
        # Determine overall action
        if scene_similarity > 0.9:
            action = "unchanged"
        elif scene_similarity > 0.7:
            action = "modified"
        elif scene_similarity > 0.4:
            action = "heavily_modified"
        else:
            action = "completely_different"
        
        return {
            "scene_number": scene_number,
            "action": action,
            "similarity": scene_similarity,
            "attribute_changes": attribute_changes,
            "line_changes": line_changes
        }
    
    def edit_episode_script(self, episode_id: str) -> bool:
        """Open the script in a text editor for manual editing.
        If the script or scenes are missing, auto-generate characters and scenes first.
        Args:
            episode_id: ID of the episode
        Returns:
            Success status
        """
        # Load script
        script = self.load_episode_script(episode_id)
        if not script or not script.get('scenes'):
            logger.warning(f"Script or scenes missing for episode: {episode_id}. Attempting to auto-generate.")
            # Generate characters if missing
            episode = get_episode(episode_id)
            if episode is not None and not episode.get('characters'):
                logger.info(f"Generating characters for episode: {episode_id}")
                generate_characters(episode_id)
            # Generate scenes if missing
            episode = get_episode(episode_id)
            if episode is not None and not episode.get('scenes'):
                logger.info(f"Generating scenes for episode: {episode_id}")
                from story_os.asyncio_compat import run_coro
                run_coro(generate_scenes(episode_id))
            # Generate script
            logger.info(f"Generating script for episode: {episode_id}")
            generate_script = None
            try:
                from story_structure import generate_script as gen_script
                generate_script = gen_script
            except ImportError:
                pass
            if generate_script:
                script = generate_script(episode_id)
            else:
                logger.error("Could not import generate_script from story_structure.")
                return False
            if not script or not script.get('scenes'):
                logger.error(f"Failed to auto-generate script for episode: {episode_id}")
                return False
        # Continue as before...
        readable_script = self._create_readable_script(script)
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w+", delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(readable_script)
        try:
            editor = os.environ.get("EDITOR", "notepad" if os.name == "nt" else "nano")
            subprocess.run([editor, tmp_path], check=True)
            with open(tmp_path, 'r') as f:
                edited_script = f.read()
            new_script = self._parse_readable_script(edited_script, script)
            if self.save_script(new_script):
                logger.info(f"Script for episode {episode_id} updated successfully")
                return True
            else:
                logger.error(f"Failed to save updated script for episode {episode_id}")
                return False
        except Exception as e:
            logger.error(f"Error editing script: {e}")
            return False
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def _create_readable_script(self, script: Dict[str, Any]) -> str:
        """Create a human-readable version of the script.
        
        Args:
            script: Script data
        
        Returns:
            Human-readable script string
        """
        readable = f"TITLE: {script.get('title', 'Untitled')}\n"
        readable += f"EPISODE ID: {script.get('episode_id', 'unknown')}\n\n"
        readable += "=== SCRIPT START (DO NOT EDIT THIS LINE) ===\n\n"
        
        for i, scene in enumerate(script.get('scenes', [])):
            scene_number = scene.get('scene_number', i + 1)
            beat = scene.get('beat', 'Unknown beat')
            setting = scene.get('setting', 'Unknown setting')
            
            readable += f"### SCENE {scene_number}: {beat} ###\n"
            readable += f"SETTING: {setting}\n\n"
            
            for line in scene.get('lines', []):
                line_type = line.get('type', 'unknown')
                content = line.get('content', '')
                
                if line_type == 'description':
                    readable += f"[DESCRIPTION] {content}\n\n"
                elif line_type == 'dialogue':
                    character = line.get('character', 'UNKNOWN')
                    readable += f"{character}: {content}\n\n"
                elif line_type == 'sound_effect':
                    readable += f"(SOUND) {content}\n\n"
                elif line_type == 'narration':
                    readable += f"NARRATOR: {content}\n\n"
                else:
                    readable += f"[{line_type.upper()}] {content}\n\n"
            
            readable += "### END SCENE ###\n\n"
        
        readable += "=== SCRIPT END (DO NOT EDIT THIS LINE) ===\n"
        
        return readable
    
    def _parse_readable_script(self, readable_script: str, original_script: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a human-readable script back to structured format.
        
        Args:
            readable_script: Human-readable script string
            original_script: Original script data for reference
        
        Returns:
            Updated script data
        """
        # Create a copy of the original script
        new_script = {
            "title": original_script.get('title', 'Untitled'),
            "episode_id": original_script.get('episode_id', 'unknown'),
            "created_at": original_script.get('created_at', time.time()),
            "updated_at": time.time(),
            "scenes": []
        }
        
        # Extract content between start and end markers
        pattern = r"=== SCRIPT START \(DO NOT EDIT THIS LINE\) ===\n(.*?)\n=== SCRIPT END \(DO NOT EDIT THIS LINE\) ==="
        match = re.search(pattern, readable_script, re.DOTALL)
        
        if not match:
            logger.error("Failed to find script content markers")
            return original_script
        
        content = match.group(1)
        
        # Split into scenes
        scene_pattern = r"### SCENE (\d+): (.*?) ###\n(.*?)(?=### END SCENE ###)"
        scene_matches = re.finditer(scene_pattern, content, re.DOTALL)
        
        for scene_match in scene_matches:
            scene_number = int(scene_match.group(1))
            beat = scene_match.group(2).strip()
            scene_content = scene_match.group(3)
            
            # Extract setting
            setting_match = re.search(r"SETTING: (.*?)(?:\n\n|\Z)", scene_content)
            setting = setting_match.group(1).strip() if setting_match else ""
            
            # Remove setting line from content
            if setting_match:
                scene_content = scene_content.replace(setting_match.group(0), "", 1)
            
            # Parse lines
            lines = []
            
            # Split content into lines/paragraphs
            paragraphs = re.split(r'\n\n', scene_content.strip())
            
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                
                # Check line type
                if paragraph.startswith('[DESCRIPTION]'):
                    content = paragraph[len('[DESCRIPTION]'):].strip()
                    lines.append({
                        "type": "description",
                        "content": content
                    })
                
                elif paragraph.startswith('(SOUND)'):
                    content = paragraph[len('(SOUND)'):].strip()
                    lines.append({
                        "type": "sound_effect",
                        "content": content
                    })
                
                elif paragraph.startswith('NARRATOR:'):
                    content = paragraph[len('NARRATOR:'):].strip()
                    lines.append({
                        "type": "narration",
                        "content": content
                    })
                
                elif ':' in paragraph:
                    # Dialogue
                    parts = paragraph.split(':', 1)
                    character = parts[0].strip()
                    content = parts[1].strip()
                    
                    lines.append({
                        "type": "dialogue",
                        "character": character,
                        "content": content
                    })
                
                else:
                    # Default to description
                    lines.append({
                        "type": "description",
                        "content": paragraph
                    })
            
            # Create scene
            scene = {
                "scene_id": f"scene_{uuid.uuid4().hex[:8]}",
                "scene_number": scene_number,
                "beat": beat,
                "setting": setting,
                "lines": lines
            }
            
            # Check if this scene has an ID in the original script
            if 'scenes' in original_script:
                for original_scene in original_script['scenes']:
                    if original_scene.get('scene_number') == scene_number:
                        scene['scene_id'] = original_scene.get('scene_id', scene['scene_id'])
                        break
            
            new_script['scenes'].append(scene)
        
        # Sort scenes by scene number
        new_script['scenes'].sort(key=lambda s: s.get('scene_number', 0))
        
        return new_script

# Singleton instance
_script_editor = None

def get_script_editor() -> ScriptEditor:
    """Get the ScriptEditor singleton instance."""
    global _script_editor
    
    if _script_editor is None:
        _script_editor = ScriptEditor()
    
    return _script_editor

def load_episode_script(episode_id: str) -> Dict[str, Any]:
    """Load the script for an episode.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        Dictionary with script data
    """
    editor = get_script_editor()
    return editor.load_episode_script(episode_id)

def preview_scene_flow(script: Dict[str, Any]) -> List[str]:
    """Generate a preview of the scene flow in the script.
    
    Args:
        script: Script data
    
    Returns:
        List of scene summaries
    """
    editor = get_script_editor()
    return editor.preview_scene_flow(script)

def update_line(scene_index: int, line_index: int, new_text: str, 
               episode_id: str) -> Dict[str, Any]:
    """Update a specific line in the script.
    
    Args:
        scene_index: Index of the scene
        line_index: Index of the line within the scene
        new_text: New content for the line
        episode_id: ID of the episode
    
    Returns:
        Updated script
    """
    editor = get_script_editor()
    script = editor.load_episode_script(episode_id)
    
    if not script:
        logger.error(f"Failed to load script for episode: {episode_id}")
        return {}
    
    updated_script = editor.update_line(script, scene_index, line_index, new_text)
    
    if editor.save_script(updated_script):
        return updated_script
    else:
        logger.error(f"Failed to save updated script for episode: {episode_id}")
        return script

def mark_scene_for_regeneration(scene_index: int, episode_id: str) -> Dict[str, Any]:
    """Mark a scene for regeneration.
    
    Args:
        scene_index: Index of the scene
        episode_id: ID of the episode
    
    Returns:
        Updated script
    """
    editor = get_script_editor()
    script = editor.load_episode_script(episode_id)
    
    if not script:
        logger.error(f"Failed to load script for episode: {episode_id}")
        return {}
    
    updated_script = editor.mark_scene_for_regeneration(script, scene_index)
    
    if editor.save_script(updated_script):
        return updated_script
    else:
        logger.error(f"Failed to save updated script for episode: {episode_id}")
        return script

def regenerate_scene(episode_id: str, scene_index: int, 
                    instructions: Optional[str] = None) -> Dict[str, Any]:
    """Regenerate a specific scene with optional instructions.
    
    Args:
        episode_id: ID of the episode
        scene_index: Index of the scene to regenerate
        instructions: Optional special instructions for regeneration
    
    Returns:
        Updated script with regenerated scene
    """
    editor = get_script_editor()
    return editor.regenerate_scene(episode_id, scene_index, instructions)

def save_script(script: Dict[str, Any]) -> bool:
    """Save a script to file, with revision history.
    
    Args:
        script: Updated script data
    
    Returns:
        Success status
    """
    editor = get_script_editor()
    return editor.save_script(script)

def edit_episode_script(episode_id: str) -> bool:
    """Open the script in a text editor for manual editing.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        Success status
    """
    editor = get_script_editor()
    return editor.edit_episode_script(episode_id)