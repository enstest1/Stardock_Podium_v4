#!/usr/bin/env python
"""
Quality Checker Module for Stardock Podium.

This module verifies the quality of generated episodes, both in terms
of script content and audio production, flagging issues for improvement.
"""

import os
from story_os.legacy import legacy
import json
import logging
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import uuid

# Try to import required libraries
try:
    import ffmpeg
except ImportError:
    logging.error("ffmpeg-python not found. Please install it with: pip install ffmpeg-python")
    raise

try:
    from openai import OpenAI
except ImportError:
    logging.error("OpenAI not found. Please install it with: pip install openai")
    raise

# Local imports
from story_structure import get_episode
from script_editor import load_episode_script
from episode_metadata import update_metadata
from episode_memory import get_episode_memory

# Setup logging
logger = logging.getLogger(__name__)

class QualityChecker:
    """Quality verification for episodes and audio."""
    
    def __init__(self, episodes_dir: str = "episodes"):
        """Initialize the quality checker.
        
        Args:
            episodes_dir: Directory containing episode data
        """
        self.episodes_dir = Path(episodes_dir)
        
        # Initialize OpenAI client for content checking
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=api_key)
        
        # Initialize episode memory
        self.episode_memory = get_episode_memory()
    
    def check_episode_quality(self, episode_id: str, 
                            check_options: Dict[str, bool] = None) -> Dict[str, Any]:
        """Check the quality of an episode.
        
        Args:
            episode_id: ID of the episode
            check_options: Options for what to check
        
        Returns:
            Dictionary with quality check results
        """
        if check_options is None:
            check_options = {
                "check_script": True,
                "check_audio": True
            }
        
        # Get episode data
        episode = get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return {"error": f"Episode not found: {episode_id}"}
        
        # Create results structure
        results = {
            "episode_id": episode_id,
            "title": episode.get("title", "Unknown"),
            "check_time": time.time(),
            "script_quality": None,
            "audio_quality": None,
            "overall_quality": None,
            "issues": [],
            "recommendations": []
        }
        
        # Check script quality if requested
        if check_options.get("check_script", True):
            script_results = self._check_script_quality(episode_id)
            results["script_quality"] = script_results
            
            # Add script issues to the main issues list
            if "issues" in script_results:
                for issue in script_results["issues"]:
                    results["issues"].append({
                        "type": "script",
                        "severity": issue.get("severity", "warning"),
                        "description": issue.get("description", "Unknown issue"),
                        "location": issue.get("location")
                    })
            
            # Add script recommendations
            if "recommendations" in script_results:
                results["recommendations"].extend(script_results["recommendations"])
        
        # Check audio quality if requested
        if check_options.get("check_audio", True):
            audio_results = self._check_audio_quality(episode_id)
            results["audio_quality"] = audio_results
            
            # Add audio issues to the main issues list
            if "issues" in audio_results:
                for issue in audio_results["issues"]:
                    results["issues"].append({
                        "type": "audio",
                        "severity": issue.get("severity", "warning"),
                        "description": issue.get("description", "Unknown issue"),
                        "location": issue.get("location")
                    })
            
            # Add audio recommendations
            if "recommendations" in audio_results:
                results["recommendations"].extend(audio_results["recommendations"])
        
        # Determine overall quality
        if results["script_quality"] and results["audio_quality"]:
            # Average of script and audio quality
            script_score = results["script_quality"].get("score", 0)
            audio_score = results["audio_quality"].get("score", 0)
            
            results["overall_quality"] = {
                "score": (script_score + audio_score) / 2,
                "grade": self._score_to_grade((script_score + audio_score) / 2)
            }
        elif results["script_quality"]:
            # Only script quality available
            results["overall_quality"] = {
                "score": results["script_quality"].get("score", 0),
                "grade": results["script_quality"].get("grade", "N/A")
            }
        elif results["audio_quality"]:
            # Only audio quality available
            results["overall_quality"] = {
                "score": results["audio_quality"].get("score", 0),
                "grade": results["audio_quality"].get("grade", "N/A")
            }
        
        # Save quality check results
        self._save_quality_check(episode_id, results)
        
        # Update episode metadata with quality info
        metadata_update = {
            "quality_check": {
                "checked_at": results["check_time"],
                "overall_grade": results["overall_quality"]["grade"] if results["overall_quality"] else "N/A",
                "issue_count": len(results["issues"])
            }
        }
        
        update_metadata(episode_id, metadata_update)
        
        return results
    
    def _check_script_quality(self, episode_id: str) -> Dict[str, Any]:
        """Check the quality of an episode script.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Dictionary with script quality check results
        """
        # Load episode and script
        episode = get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return {"error": f"Episode not found: {episode_id}"}
        
        script = load_episode_script(episode_id)
        if not script:
            logger.error(f"Script not found for episode: {episode_id}")
            return {"error": f"Script not found: {episode_id}"}
        
        # Initialize results
        results = {
            "issues": [],
            "score": 0.0,
            "grade": "N/A",
            "recommendations": []
        }
        
        # Check overall script structure
        structure_issues = self._check_script_structure(script, episode)
        results["issues"].extend(structure_issues)
        
        # Check for continuity with previous episodes
        continuity_issues = self._check_continuity(episode_id, script)
        results["issues"].extend(continuity_issues)
        
        # Check dialogue quality
        dialogue_issues = self._check_dialogue_quality(script)
        results["issues"].extend(dialogue_issues)
        
        # Check pacing
        pacing_issues = self._check_pacing(script)
        results["issues"].extend(pacing_issues)
        
        # Generate AI evaluation for overall quality
        ai_evaluation = self._evaluate_script_with_ai(script, episode)
        
        if "score" in ai_evaluation:
            results["score"] = ai_evaluation["score"]
            results["grade"] = self._score_to_grade(ai_evaluation["score"])
        
        if "issues" in ai_evaluation:
            results["issues"].extend(ai_evaluation["issues"])
        
        if "recommendations" in ai_evaluation:
            results["recommendations"] = ai_evaluation["recommendations"]
        
        # Sort issues by severity
        results["issues"].sort(key=lambda x: self._severity_to_value(x.get("severity", "warning")), reverse=True)
        
        return results
    
    def _check_script_structure(self, script: Dict[str, Any], 
                              episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check the structure of a script against Save the Cat beats.
        
        Args:
            script: Script data
            episode: Episode data
        
        Returns:
            List of structure issues
        """
        issues = []
        
        # Get beat sheet
        beats = episode.get("beats", [])
        if not beats:
            issues.append({
                "severity": "warning",
                "description": "Episode is missing beat sheet structure",
                "location": None
            })
            return issues
        
        # Get scenes
        scenes = script.get("scenes", [])
        if not scenes:
            issues.append({
                "severity": "error",
                "description": "Script has no scenes",
                "location": None
            })
            return issues
        
        # Check that each beat has at least one scene
        beat_coverage = {beat["name"]: 0 for beat in beats}
        
        for scene in scenes:
            beat = scene.get("beat")
            if beat in beat_coverage:
                beat_coverage[beat] += 1
        
        # Report missing beats
        for beat, count in beat_coverage.items():
            if count == 0:
                issues.append({
                    "severity": "warning",
                    "description": f"Beat '{beat}' has no corresponding scenes",
                    "location": None
                })
        
        # Check for proper beat sequence
        beat_names = [beat["name"] for beat in beats]
        scene_beats = [scene.get("beat") for scene in scenes if scene.get("beat") in beat_names]
        
        if scene_beats:
            # Get the order of beats as they appear in scenes
            actual_beat_order = []
            for beat in scene_beats:
                if beat not in actual_beat_order:
                    actual_beat_order.append(beat)
            
            # Compare to expected order
            for i, beat in enumerate(actual_beat_order):
                expected_index = beat_names.index(beat)
                
                # Check if this beat appears out of order
                if i > 0 and expected_index < beat_names.index(actual_beat_order[i-1]):
                    issues.append({
                        "severity": "warning",
                        "description": f"Beat '{beat}' appears out of sequence in the script",
                        "location": f"After scene with beat '{actual_beat_order[i-1]}'"
                    })
        
        return issues
    
    def _check_continuity(self, episode_id: str, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check script for continuity with previous episodes.
        
        Args:
            episode_id: ID of the episode
            script: Script data
        
        Returns:
            List of continuity issues
        """
        issues = []
        
        # Get episode data
        episode = get_episode(episode_id)
        if not episode:
            return issues
        
        # Get episode number and series
        episode_number = episode.get("episode_number", 0)
        series = episode.get("series", "")
        
        # Skip continuity check for first episode in a series
        if episode_number <= 1:
            return issues
        
        # Get references to previous episodes
        timeline = self.episode_memory.get_timeline()
        
        # Find characters from previous episodes
        previous_characters = set()
        
        for ep_id, events in timeline.items():
            # Skip the current episode
            if ep_id == episode_id:
                continue
            
            # Check if this is from the same series
            ep_episode = get_episode(ep_id)
            if not ep_episode or ep_episode.get("series") != series:
                continue
            
            # Check if this is a previous episode
            if ep_episode.get("episode_number", 0) >= episode_number:
                continue
            
            # Get character names from events
            for event in events:
                if "character" in event.get("metadata", {}):
                    previous_characters.add(event["metadata"]["character"])
                
                # Also check for characters in relationships
                if "characters" in event.get("metadata", {}):
                    previous_characters.update(event["metadata"]["characters"])
        
        # Check if script has references to previous characters
        current_characters = set()
        character_references = {}
        
        for scene in script.get("scenes", []):
            for line in scene.get("lines", []):
                if line.get("type") == "dialogue":
                    character = line.get("character")
                    if character:
                        current_characters.add(character)
                
                # Check content for character references
                content = line.get("content", "")
                for character in previous_characters:
                    if re.search(r'\b' + re.escape(character) + r'\b', content):
                        if character not in character_references:
                            character_references[character] = 0
                        character_references[character] += 1
        
        # Check for previous significant characters not appearing in this episode
        missing_characters = previous_characters - current_characters
        
        # Only consider it an issue if the character was referenced but doesn't appear
        for character in missing_characters:
            if character in character_references and character_references[character] > 0:
                issues.append({
                    "severity": "info",
                    "description": f"Character '{character}' from previous episodes is referenced but doesn't appear",
                    "location": None
                })
        
        # Check for inconsistencies with previous episode memories
        # Get relevant memories
        memories = self.episode_memory.search_memories(
            query=episode.get("title", ""),
            category=self.episode_memory.CONTINUITY,
            limit=10
        )
        
        for memory in memories:
            memory_text = memory.get("memory", "")
            
            # Check for potential contradictions
            for scene in script.get("scenes", []):
                for line in scene.get("lines", []):
                    content = line.get("content", "")
                    
                    # This is a simplified check - would need NLP for better contradiction detection
                    if content and len(content) > 20 and self._might_contradict(content, memory_text):
                        issues.append({
                            "severity": "warning",
                            "description": f"Possible continuity contradiction with earlier episode",
                            "location": f"Scene {scene.get('scene_number')}, line type {line.get('type')}"
                        })
        
        return issues
    
    def _might_contradict(self, text_a: str, text_b: str) -> bool:
        """Simple check if two texts might contradict each other.
        
        Args:
            text_a: First text
            text_b: Second text
        
        Returns:
            True if contradiction is possible
        """
        # This is a very simplified check
        # Would need NLP/AI for better contradiction detection
        
        # Check if both texts contain the same named entities but with different verbs
        # This is prone to false positives, but it's a starting point
        
        # Extract potential entity names (capitalized words)
        entities_a = set(re.findall(r'\b[A-Z][a-z]+\b', text_a))
        entities_b = set(re.findall(r'\b[A-Z][a-z]+\b', text_b))
        
        # Find common entities
        common_entities = entities_a.intersection(entities_b)
        
        if not common_entities:
            return False
        
        # Check for negations around common entities
        negation_words = ['not', 'never', 'no', "didn't", "doesn't", "isn't", "wasn't", "couldn't"]
        
        for entity in common_entities:
            # Check for negations in context of this entity
            context_a = self._get_context(text_a, entity, window=3)
            context_b = self._get_context(text_b, entity, window=3)
            
            # If one has negation and the other doesn't for the same entity
            has_negation_a = any(neg in context_a for neg in negation_words)
            has_negation_b = any(neg in context_b for neg in negation_words)
            
            if has_negation_a != has_negation_b:
                return True
        
        return False
    
    def _get_context(self, text: str, keyword: str, window: int = 3) -> str:
        """Get context around a keyword in text.
        
        Args:
            text: Text to search
            keyword: Keyword to find
            window: Number of words for context on each side
        
        Returns:
            Context string
        """
        words = text.split()
        if keyword not in words:
            return ""
        
        idx = words.index(keyword)
        start = max(0, idx - window)
        end = min(len(words), idx + window + 1)
        
        return " ".join(words[start:end])
    
    def _check_dialogue_quality(self, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check the quality of dialogue in the script.
        
        Args:
            script: Script data
        
        Returns:
            List of dialogue issues
        """
        issues = []
        
        # Get scenes
        scenes = script.get("scenes", [])
        if not scenes:
            return issues
        
        # Track dialogue lines per character
        character_lines = {}
        
        # Track repetitive phrases
        phrase_counts = {}
        
        for scene_idx, scene in enumerate(scenes):
            scene_number = scene.get("scene_number", scene_idx + 1)
            
            # Check dialogue in this scene
            for line_idx, line in enumerate(scene.get("lines", [])):
                if line.get("type") != "dialogue":
                    continue
                
                character = line.get("character", "")
                content = line.get("content", "")
                
                # Count character lines
                if character not in character_lines:
                    character_lines[character] = 0
                character_lines[character] += 1
                
                # Check for very short or very long dialogue
                if len(content) < 10:
                    issues.append({
                        "severity": "info",
                        "description": f"Very short dialogue line for {character}",
                        "location": f"Scene {scene_number}, line {line_idx + 1}"
                    })
                elif len(content) > 200:
                    issues.append({
                        "severity": "warning",
                        "description": f"Very long dialogue line for {character}",
                        "location": f"Scene {scene_number}, line {line_idx + 1}"
                    })
                
                # Check for repetitive phrases
                words = content.split()
                if len(words) >= 3:
                    for i in range(len(words) - 2):
                        phrase = " ".join(words[i:i+3])
                        phrase = phrase.lower()
                        
                        if phrase not in phrase_counts:
                            phrase_counts[phrase] = []
                        
                        phrase_counts[phrase].append({
                            "scene_number": scene_number,
                            "line_index": line_idx,
                            "character": character
                        })
        
        # Check for disproportionate dialogue
        total_lines = sum(character_lines.values())
        if total_lines > 0:
            for character, count in character_lines.items():
                # If a character has more than 50% of all dialogue
                if count > total_lines * 0.5:
                    issues.append({
                        "severity": "warning",
                        "description": f"Character '{character}' has disproportionate dialogue ({count} lines, {count/total_lines*100:.1f}% of total)",
                        "location": None
                    })
                # If a character has only one line
                elif count == 1:
                    issues.append({
                        "severity": "info",
                        "description": f"Character '{character}' has only one line in the script",
                        "location": None
                    })
        
        # Check for repetitive phrases
        for phrase, occurrences in phrase_counts.items():
            if len(occurrences) >= 3:
                # Only report if same character uses the phrase multiple times
                character_counts = {}
                for occurrence in occurrences:
                    character = occurrence["character"]
                    if character not in character_counts:
                        character_counts[character] = 0
                    character_counts[character] += 1
                
                for character, count in character_counts.items():
                    if count >= 3:
                        issues.append({
                            "severity": "info",
                            "description": f"Character '{character}' repeats phrase '{phrase}' {count} times",
                            "location": f"First occurrence: Scene {occurrences[0]['scene_number']}, line {occurrences[0]['line_index'] + 1}"
                        })
        
        return issues
    
    def _check_pacing(self, script: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check the pacing of the script.
        
        Args:
            script: Script data
        
        Returns:
            List of pacing issues
        """
        issues = []
        
        # Get scenes
        scenes = script.get("scenes", [])
        if not scenes:
            return issues
        
        # Check scene length distribution
        scene_lengths = [len(scene.get("lines", [])) for scene in scenes]
        
        if scene_lengths:
            avg_length = sum(scene_lengths) / len(scene_lengths)
            
            # Check for very short scenes
            for i, length in enumerate(scene_lengths):
                if length <= 2:
                    issues.append({
                        "severity": "info",
                        "description": f"Very short scene with only {length} lines",
                        "location": f"Scene {scenes[i].get('scene_number', i + 1)}"
                    })
            
            # Check for very long scenes
            for i, length in enumerate(scene_lengths):
                if length >= avg_length * 2:
                    issues.append({
                        "severity": "warning",
                        "description": f"Very long scene with {length} lines (average is {avg_length:.1f})",
                        "location": f"Scene {scenes[i].get('scene_number', i + 1)}"
                    })
        
        # Check for long dialogue stretches without action or sound effects
        for scene_idx, scene in enumerate(scenes):
            scene_number = scene.get("scene_number", scene_idx + 1)
            
            dialogue_stretch = 0
            last_non_dialogue = 0
            
            for line_idx, line in enumerate(scene.get("lines", [])):
                if line.get("type") == "dialogue":
                    dialogue_stretch += 1
                else:
                    # Reset counter if we hit a non-dialogue line
                    if dialogue_stretch >= 6:
                        issues.append({
                            "severity": "info",
                            "description": f"Long stretch of dialogue ({dialogue_stretch} lines) without action or sound effects",
                            "location": f"Scene {scene_number}, lines {last_non_dialogue + 1}-{line_idx}"
                        })
                    
                    dialogue_stretch = 0
                    last_non_dialogue = line_idx
            
            # Check end of scene
            if dialogue_stretch >= 6:
                issues.append({
                    "severity": "info",
                    "description": f"Long stretch of dialogue ({dialogue_stretch} lines) without action or sound effects",
                    "location": f"Scene {scene_number}, at end of scene"
                })
        
        return issues
    
    def _evaluate_script_with_ai(self, script: Dict[str, Any], 
                               episode: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to evaluate the script quality.
        
        Args:
            script: Script data
            episode: Episode data
        
        Returns:
            Dictionary with AI evaluation results
        """
        if not (os.environ.get('OPENROUTER_API_KEY')
                or os.environ.get('OPENAI_API_KEY')):
            logger.error("No LLM API key for AI evaluation")
            return {}

        try:
            # Create a simplified version of the script for evaluation
            simplified_script = self._simplify_script_for_evaluation(script)
            
            # Create prompt for evaluation
            prompt = f"""
            You are a professional script evaluator for podcast episodes. Please evaluate the following
            {legacy('evaluator_genre')} and rate its quality.
            
            EPISODE INFORMATION:
            Title: {episode.get('title', 'Unknown')}
            Theme: {episode.get('theme', 'Not specified')}
            
            SCRIPT:
            {simplified_script}
            
            Please provide:
            1. A quality score from 0 to 10 (where 10 is excellent)
            2. A list of 1-3 significant issues with the script, if any
            3. 1-3 specific recommendations for improving the script
            
            Format your response as JSON with the following structure:
            {{
                "score": <score>,
                "issues": [
                    {{"severity": "<error|warning|info>", "description": "<issue description>", "location": "<location in script>"}}
                ],
                "recommendations": [
                    "<recommendation>"
                ]
            }}
            """
            
            # Query the AI
            from story_os import llm
            content = llm.complete(
                'editor',
                "You are a professional script evaluator. Return only valid JSON.",
                prompt, json=True, temperature=0.3, max_tokens=1000)
            content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip())

            # Parse the result
            try:
                result_json = json.loads(content)
                return result_json
            except json.JSONDecodeError:
                logger.error("Failed to parse AI evaluation result as JSON")
                # Try to extract score from text
                text = response.choices[0].message.content
                score_match = re.search(r'score[\":\s]+(\d+(?:\.\d+)?)', text)
                
                if score_match:
                    score = float(score_match.group(1))
                    return {"score": score}
                
                return {}
        
        except Exception as e:
            logger.error(f"Error evaluating script with AI: {e}")
            return {}
    
    def _simplify_script_for_evaluation(self, script: Dict[str, Any]) -> str:
        """Create a simplified version of the script for AI evaluation.
        
        Args:
            script: Script data
        
        Returns:
            Simplified script text
        """
        simplified = ""
        
        for scene_idx, scene in enumerate(script.get("scenes", [])):
            scene_number = scene.get("scene_number", scene_idx + 1)
            beat = scene.get("beat", "")
            setting = scene.get("setting", "")
            
            simplified += f"SCENE {scene_number}: {beat}\n"
            simplified += f"SETTING: {setting}\n\n"
            
            for line in scene.get("lines", []):
                line_type = line.get("type", "")
                content = line.get("content", "")
                
                if line_type == "dialogue":
                    character = line.get("character", "")
                    simplified += f"{character}: {content}\n\n"
                elif line_type == "narration":
                    simplified += f"NARRATOR: {content}\n\n"
                elif line_type == "sound_effect":
                    simplified += f"(SOUND: {content})\n\n"
                elif line_type == "description":
                    simplified += f"[DESCRIPTION: {content}]\n\n"
            
            simplified += "---\n\n"
        
        return simplified
    
    def _check_audio_quality(self, episode_id: str) -> Dict[str, Any]:
        """Check the quality of episode audio.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Dictionary with audio quality check results
        """
        # Get episode data
        episode = get_episode(episode_id)
        if not episode:
            logger.error(f"Episode not found: {episode_id}")
            return {"error": f"Episode not found: {episode_id}"}
        
        # Check if episode has audio
        audio_path = episode.get("audio", {}).get("file_path")
        if not audio_path:
            logger.error(f"Episode has no audio: {episode_id}")
            return {"error": f"Episode has no audio: {episode_id}"}
        
        # Initialize results
        results = {
            "issues": [],
            "score": 0.0,
            "grade": "N/A",
            "recommendations": []
        }
        
        # Check audio file integrity
        integrity_issues = self._check_audio_integrity(audio_path)
        results["issues"].extend(integrity_issues)
        
        # Check audio properties
        property_issues = self._check_audio_properties(audio_path)
        results["issues"].extend(property_issues)
        
        # Analyze scene audio files
        audio_dir = Path(audio_path).parent
        scene_issues = self._check_scene_audio(audio_dir)
        results["issues"].extend(scene_issues)
        
        # Calculate score based on issues
        if results["issues"]:
            # Count by severity
            error_count = sum(1 for issue in results["issues"] if issue.get("severity") == "error")
            warning_count = sum(1 for issue in results["issues"] if issue.get("severity") == "warning")
            info_count = sum(1 for issue in results["issues"] if issue.get("severity") == "info")
            
            # Calculate weighted score
            total_issues = len(results["issues"])
            weighted_total = error_count * 5 + warning_count * 2 + info_count
            
            # Base score of 10, reduced by weighted issues
            raw_score = 10 - (weighted_total / max(1, total_issues * 2))
            results["score"] = max(0, min(10, raw_score))
        else:
            # No issues found
            results["score"] = 10.0
        
        results["grade"] = self._score_to_grade(results["score"])
        
        # Generate recommendations based on issues
        results["recommendations"] = self._generate_audio_recommendations(results["issues"])
        
        return results
    
    def _check_audio_integrity(self, audio_path: str) -> List[Dict[str, Any]]:
        """Check the integrity of an audio file.
        
        Args:
            audio_path: Path to the audio file
        
        Returns:
            List of integrity issues
        """
        issues = []
        
        # Check if file exists
        if not os.path.exists(audio_path):
            issues.append({
                "severity": "error",
                "description": "Audio file does not exist",
                "location": audio_path
            })
            return issues
        
        try:
            # Use ffmpeg to check file integrity
            probe = ffmpeg.probe(audio_path)
            
            # Check for audio streams
            audio_streams = [stream for stream in probe.get("streams", []) 
                           if stream.get("codec_type") == "audio"]
            
            if not audio_streams:
                issues.append({
                    "severity": "error",
                    "description": "Audio file contains no audio streams",
                    "location": audio_path
                })
            
            # Check duration
            duration = float(probe.get("format", {}).get("duration", 0))
            
            if duration < 30:
                issues.append({
                    "severity": "error",
                    "description": f"Audio file is too short: {duration:.1f} seconds",
                    "location": audio_path
                })
            
            # Check if file is empty
            size = int(probe.get("format", {}).get("size", 0))
            
            if size == 0:
                issues.append({
                    "severity": "error",
                    "description": "Audio file is empty (zero bytes)",
                    "location": audio_path
                })
            
        except Exception as e:
            issues.append({
                "severity": "error",
                "description": f"Error probing audio file: {str(e)}",
                "location": audio_path
            })
        
        return issues
    
    def _check_audio_properties(self, audio_path: str) -> List[Dict[str, Any]]:
        """Check the properties of an audio file.
        
        Args:
            audio_path: Path to the audio file
        
        Returns:
            List of property issues
        """
        issues = []
        
        # Skip if file doesn't exist
        if not os.path.exists(audio_path):
            return issues
        
        try:
            # Use ffmpeg to analyze audio properties
            probe = ffmpeg.probe(audio_path)
            
            # Get first audio stream
            audio_streams = [stream for stream in probe.get("streams", []) 
                           if stream.get("codec_type") == "audio"]
            
            if not audio_streams:
                return issues
            
            audio_stream = audio_streams[0]
            
            # Check codec
            codec = audio_stream.get("codec_name", "")
            if codec not in ["mp3", "aac", "opus"]:
                issues.append({
                    "severity": "warning",
                    "description": f"Non-standard audio codec: {codec}",
                    "location": audio_path
                })
            
            # Check sample rate
            sample_rate = int(audio_stream.get("sample_rate", 0))
            if sample_rate < 44100:
                issues.append({
                    "severity": "warning",
                    "description": f"Low sample rate: {sample_rate} Hz",
                    "location": audio_path
                })
            
            # Check channel count
            channels = int(audio_stream.get("channels", 0))
            if channels != 2:
                issues.append({
                    "severity": "info",
                    "description": f"Non-stereo audio: {channels} channels",
                    "location": audio_path
                })
            
            # Check bit rate
            bit_rate = int(probe.get("format", {}).get("bit_rate", 0))
            if bit_rate < 128000:
                issues.append({
                    "severity": "warning",
                    "description": f"Low bit rate: {bit_rate // 1000} kbps",
                    "location": audio_path
                })
            
            # Check for silent parts
            # This would require more complex analysis
            
        except Exception as e:
            issues.append({
                "severity": "warning",
                "description": f"Error analyzing audio properties: {str(e)}",
                "location": audio_path
            })
        
        return issues
    
    def _check_scene_audio(self, audio_dir: Path) -> List[Dict[str, Any]]:
        """Check audio files for individual scenes.
        
        Args:
            audio_dir: Directory containing audio files
        
        Returns:
            List of scene audio issues
        """
        issues = []
        
        # Look for scene directories
        scene_dirs = [d for d in audio_dir.glob("scene_*") if d.is_dir()]
        
        if not scene_dirs:
            issues.append({
                "severity": "info",
                "description": "No scene audio directories found",
                "location": str(audio_dir)
            })
            return issues
        
        # Check each scene directory
        for scene_dir in scene_dirs:
            scene_name = scene_dir.name
            scene_audio = scene_dir / "scene_audio.mp3"
            
            if not scene_audio.exists():
                issues.append({
                    "severity": "warning",
                    "description": f"Missing scene audio file for {scene_name}",
                    "location": str(scene_dir)
                })
                continue
            
            # Check scene audio file
            scene_issues = self._check_audio_integrity(str(scene_audio))
            
            for issue in scene_issues:
                issue["location"] = f"{scene_name}/{os.path.basename(issue['location'])}"
                issues.append(issue)
            
            # Check for temp directory with voice clips
            temp_dir = scene_dir / "temp"
            if temp_dir.exists() and temp_dir.is_dir():
                # Count voice clips
                voice_clips = list(temp_dir.glob("*.mp3"))
                
                if not voice_clips:
                    issues.append({
                        "severity": "info",
                        "description": f"No voice clips found for {scene_name}",
                        "location": str(temp_dir)
                    })
        
        return issues
    
    def _generate_audio_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on audio issues.
        
        Args:
            issues: List of audio issues
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Count issues by type
        integrity_issues = [i for i in issues if "integrity" in i.get("description", "").lower()]
        property_issues = [i for i in issues if any(term in i.get("description", "").lower() 
                                                 for term in ["sample rate", "bit rate", "codec", "channels"])]
        scene_issues = [i for i in issues if "scene" in i.get("location", "").lower()]
        
        # Recommendations for integrity issues
        if integrity_issues:
            recommendations.append(
                "Regenerate audio files that have integrity issues to ensure playability."
            )
        
        # Recommendations for property issues
        if property_issues:
            rate_issues = [i for i in property_issues if "rate" in i.get("description", "").lower()]
            if rate_issues:
                recommendations.append(
                    "Increase audio quality settings (sample rate, bit rate) for better sound fidelity."
                )
        
        # Recommendations for scene issues
        if scene_issues:
            missing_scenes = [i for i in scene_issues if "missing" in i.get("description", "").lower()]
            if missing_scenes:
                recommendations.append(
                    "Generate audio for all scenes to ensure complete episode coverage."
                )
        
        # Generic recommendation if none specific
        if not recommendations:
            recommendations.append(
                "Consider normalizing audio levels across all scenes for consistent volume."
            )
        
        return recommendations
    
    def _score_to_grade(self, score: float) -> str:
        """Convert a numerical score to a letter grade.
        
        Args:
            score: Numerical score (0-10)
        
        Returns:
            Letter grade
        """
        if score >= 9.5:
            return "A+"
        elif score >= 9.0:
            return "A"
        elif score >= 8.5:
            return "A-"
        elif score >= 8.0:
            return "B+"
        elif score >= 7.5:
            return "B"
        elif score >= 7.0:
            return "B-"
        elif score >= 6.5:
            return "C+"
        elif score >= 6.0:
            return "C"
        elif score >= 5.5:
            return "C-"
        elif score >= 5.0:
            return "D+"
        elif score >= 4.0:
            return "D"
        else:
            return "F"
    
    def _severity_to_value(self, severity: str) -> int:
        """Convert severity string to numerical value for sorting.
        
        Args:
            severity: Severity string
        
        Returns:
            Numerical value
        """
        if severity == "error":
            return 3
        elif severity == "warning":
            return 2
        elif severity == "info":
            return 1
        else:
            return 0
    
    def _save_quality_check(self, episode_id: str, results: Dict[str, Any]) -> None:
        """Save quality check results to file.
        
        Args:
            episode_id: ID of the episode
            results: Quality check results
        """
        episode_dir = self.episodes_dir / episode_id
        quality_file = episode_dir / "quality_check.json"
        
        try:
            with open(quality_file, 'w') as f:
                json.dump(results, f, indent=2)
            
            logger.info(f"Quality check results saved to {quality_file}")
        except Exception as e:
            logger.error(f"Error saving quality check results: {e}")

# Singleton instance
_quality_checker = None

def get_quality_checker() -> QualityChecker:
    """Get the QualityChecker singleton instance."""
    global _quality_checker
    
    if _quality_checker is None:
        _quality_checker = QualityChecker()
    
    return _quality_checker

def check_episode_quality(episode_id: str, check_options: Dict[str, bool] = None) -> Dict[str, Any]:
    """Check the quality of an episode.
    
    Args:
        episode_id: ID of the episode
        check_options: Options for what to check
    
    Returns:
        Dictionary with quality check results
    """
    checker = get_quality_checker()
    return checker.check_episode_quality(episode_id, check_options)