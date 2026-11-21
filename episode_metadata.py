#!/usr/bin/env python
"""
Episode Metadata Module for Stardock Podium.

This module handles the management, storage, and retrieval of episode
metadata, including tagging, categorization, and organizational features.
"""

import os
from story_os.legacy import legacy
import json
import logging
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Set
import uuid

# Local imports
from story_structure import get_story_structure, get_episode
from mem0_client import get_mem0_client

# Setup logging
logger = logging.getLogger(__name__)

class EpisodeMetadata:
    """Manages episode metadata and organization."""
    
    def __init__(self, episodes_dir: str = "episodes", metadata_dir: str = "data/metadata"):
        """Initialize the episode metadata manager.
        
        Args:
            episodes_dir: Directory containing episode data
            metadata_dir: Directory to store metadata files
        """
        self.episodes_dir = Path(episodes_dir)
        self.metadata_dir = Path(metadata_dir)
        self.metadata_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize story structure and mem0 client
        self.story_structure = get_story_structure()
        self.mem0_client = get_mem0_client()
        
        # Load series registry
        self._series_registry = self._load_series_registry()
        
        # Load tags registry
        self._tags_registry = self._load_tags_registry()
    
    def _load_series_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load the series registry.
        
        Returns:
            Dictionary of series with metadata
        """
        series_file = self.metadata_dir / "series_registry.json"
        
        if series_file.exists():
            try:
                with open(series_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading series registry: {e}")
        
        # Return empty registry if file doesn't exist or loading fails
        return {}
    
    def _save_series_registry(self) -> None:
        """Save the series registry to file."""
        series_file = self.metadata_dir / "series_registry.json"
        
        try:
            with open(series_file, 'w') as f:
                json.dump(self._series_registry, f, indent=2)
            
            logger.debug("Series registry saved")
        except Exception as e:
            logger.error(f"Error saving series registry: {e}")
    
    def _load_tags_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load the tags registry.
        
        Returns:
            Dictionary of tags with metadata
        """
        tags_file = self.metadata_dir / "tags_registry.json"
        
        if tags_file.exists():
            try:
                with open(tags_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading tags registry: {e}")
        
        # Return empty registry if file doesn't exist or loading fails
        return {}
    
    def _save_tags_registry(self) -> None:
        """Save the tags registry to file."""
        tags_file = self.metadata_dir / "tags_registry.json"
        
        try:
            with open(tags_file, 'w') as f:
                json.dump(self._tags_registry, f, indent=2)
            
            logger.debug("Tags registry saved")
        except Exception as e:
            logger.error(f"Error saving tags registry: {e}")
    
    def register_series(self, series_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new series or update existing one.
        
        Args:
            series_data: Dictionary with series information
        
        Returns:
            Updated series data with status
        """
        # Ensure series has a name
        series_name = series_data.get('name')
        if not series_name:
            error_msg = "Series must have a name"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Normalize series name for ID
        series_id = series_data.get('series_id') or self._normalize_id(series_name)
        
        # Check if series already exists
        is_update = series_id in self._series_registry
        
        # Create or update series entry
        self._series_registry[series_id] = {
            "series_id": series_id,
            "name": series_name,
            "description": series_data.get('description', ''),
            "created_at": self._series_registry.get(series_id, {}).get('created_at', time.time()),
            "updated_at": time.time(),
            "tags": series_data.get('tags', []),
            "metadata": series_data.get('metadata', {})
        }
        
        # Save registry
        self._save_series_registry()
        
        return {
            "series_id": series_id,
            "action": "updated" if is_update else "created",
            "series_data": self._series_registry[series_id]
        }
    
    def get_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        """Get series information by ID.
        
        Args:
            series_id: ID of the series
        
        Returns:
            Series data or None if not found
        """
        return self._series_registry.get(series_id)
    
    def list_series(self) -> List[Dict[str, Any]]:
        """List all registered series.
        
        Returns:
            List of series data
        """
        return list(self._series_registry.values())
    
    def delete_series(self, series_id: str) -> Dict[str, Any]:
        """Delete a series from the registry.
        
        Args:
            series_id: ID of the series to delete
        
        Returns:
            Status information
        """
        if series_id not in self._series_registry:
            return {"success": False, "error": f"Series not found: {series_id}"}
        
        # Check if there are episodes in this series
        episodes = self.list_episodes(filters={"series": series_id})
        if episodes:
            return {
                "success": False, 
                "error": f"Cannot delete series with episodes. Found {len(episodes)} episodes."
            }
        
        # Delete from registry
        deleted_series = self._series_registry.pop(series_id)
        self._save_series_registry()
        
        return {"success": True, "deleted_series": deleted_series}
    
    def create_tag(self, tag_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a tag in the registry.
        
        Args:
            tag_data: Dictionary with tag information
        
        Returns:
            Updated tag data with status
        """
        # Ensure tag has a name
        tag_name = tag_data.get('name')
        if not tag_name:
            error_msg = "Tag must have a name"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Normalize tag name for ID
        tag_id = tag_data.get('tag_id') or self._normalize_id(tag_name)
        
        # Check if tag already exists
        is_update = tag_id in self._tags_registry
        
        # Create or update tag entry
        self._tags_registry[tag_id] = {
            "tag_id": tag_id,
            "name": tag_name,
            "description": tag_data.get('description', ''),
            "color": tag_data.get('color', '#cccccc'),
            "created_at": self._tags_registry.get(tag_id, {}).get('created_at', time.time()),
            "updated_at": time.time(),
            "category": tag_data.get('category', 'general')
        }
        
        # Save registry
        self._save_tags_registry()
        
        return {
            "tag_id": tag_id,
            "action": "updated" if is_update else "created",
            "tag_data": self._tags_registry[tag_id]
        }
    
    def get_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Get tag information by ID.
        
        Args:
            tag_id: ID of the tag
        
        Returns:
            Tag data or None if not found
        """
        return self._tags_registry.get(tag_id)
    
    def list_tags(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered tags, optionally filtered by category.
        
        Args:
            category: Optional category to filter by
        
        Returns:
            List of tag data
        """
        if category:
            return [tag for tag in self._tags_registry.values() 
                   if tag.get('category') == category]
        else:
            return list(self._tags_registry.values())
    
    def delete_tag(self, tag_id: str) -> Dict[str, Any]:
        """Delete a tag from the registry.
        
        Args:
            tag_id: ID of the tag to delete
        
        Returns:
            Status information
        """
        if tag_id not in self._tags_registry:
            return {"success": False, "error": f"Tag not found: {tag_id}"}
        
        # Delete from registry
        deleted_tag = self._tags_registry.pop(tag_id)
        self._save_tags_registry()
        
        # Remove this tag from all episodes
        self._remove_tag_from_all_episodes(tag_id)
        
        return {"success": True, "deleted_tag": deleted_tag}
    
    def _remove_tag_from_all_episodes(self, tag_id: str) -> None:
        """Remove a tag from all episodes.
        
        Args:
            tag_id: ID of the tag to remove
        """
        # Iterate through episodes directory
        for episode_dir in self.episodes_dir.iterdir():
            if not episode_dir.is_dir():
                continue
            
            # Check for metadata file
            metadata_file = episode_dir / "metadata.json"
            if not metadata_file.exists():
                continue
            
            try:
                # Load metadata
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Check if this tag is present
                if 'tags' in metadata and tag_id in metadata['tags']:
                    # Remove the tag
                    metadata['tags'].remove(tag_id)
                    
                    # Save updated metadata
                    with open(metadata_file, 'w') as f:
                        json.dump(metadata, f, indent=2)
            
            except Exception as e:
                logger.error(f"Error updating metadata file {metadata_file}: {e}")
    
    def update_episode_metadata(self, episode_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update metadata for an episode.
        
        Args:
            episode_id: ID of the episode
            metadata: Updated metadata fields
        
        Returns:
            Updated episode metadata
        """
        # Get episode directory
        episode_dir = self.episodes_dir / episode_id
        if not episode_dir.exists() or not episode_dir.is_dir():
            error_msg = f"Episode directory not found: {episode_id}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Check if episode structure exists
        structure_file = episode_dir / "structure.json"
        if not structure_file.exists():
            error_msg = f"Episode structure file not found: {episode_id}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Load current metadata
        metadata_file = episode_dir / "metadata.json"
        current_metadata = {}
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    current_metadata = json.load(f)
            except Exception as e:
                logger.error(f"Error loading current metadata: {e}")
        
        # Update metadata
        updated_metadata = current_metadata.copy()
        updated_metadata.update(metadata)
        
        # Ensure certain fields are always present
        if 'episode_id' not in updated_metadata:
            updated_metadata['episode_id'] = episode_id
        
        if 'tags' not in updated_metadata:
            updated_metadata['tags'] = []
        
        if 'updated_at' not in updated_metadata:
            updated_metadata['updated_at'] = time.time()
        
        # Save metadata
        try:
            with open(metadata_file, 'w') as f:
                json.dump(updated_metadata, f, indent=2)
            
            logger.info(f"Updated metadata for episode {episode_id}")
            return updated_metadata
        
        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            return {"error": f"Error saving metadata: {e}"}
    
    def get_episode_metadata(self, episode_id: str) -> Dict[str, Any]:
        """Get metadata for an episode.
        
        Args:
            episode_id: ID of the episode
        
        Returns:
            Episode metadata
        """
        # Check episode directory
        episode_dir = self.episodes_dir / episode_id
        if not episode_dir.exists() or not episode_dir.is_dir():
            logger.error(f"Episode directory not found: {episode_id}")
            return {}
        
        # Check metadata file
        metadata_file = episode_dir / "metadata.json"
        if not metadata_file.exists():
            # If no metadata file, return basic info from structure
            structure_file = episode_dir / "structure.json"
            if structure_file.exists():
                try:
                    with open(structure_file, 'r') as f:
                        structure = json.load(f)
                    
                    # Create basic metadata
                    return {
                        "episode_id": episode_id,
                        "title": structure.get("title", ""),
                        "series": structure.get("series", ""),
                        "episode_number": structure.get("episode_number", 0),
                        "created_at": structure.get("created_at", 0),
                        "tags": []
                    }
                except Exception as e:
                    logger.error(f"Error reading structure file: {e}")
                    return {}
            else:
                logger.error(f"Episode structure file not found: {episode_id}")
                return {}
        
        # Read metadata file
        try:
            with open(metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading metadata file: {e}")
            return {}
    
    def add_tag_to_episode(self, episode_id: str, tag_id: str) -> Dict[str, Any]:
        """Add a tag to an episode.
        
        Args:
            episode_id: ID of the episode
            tag_id: ID of the tag to add
        
        Returns:
            Updated episode metadata
        """
        # Check if tag exists
        if tag_id not in self._tags_registry:
            error_msg = f"Tag not found: {tag_id}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Get current metadata
        metadata = self.get_episode_metadata(episode_id)
        if not metadata:
            error_msg = f"Episode not found: {episode_id}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Add tag if not already present
        if 'tags' not in metadata:
            metadata['tags'] = []
        
        if tag_id not in metadata['tags']:
            metadata['tags'].append(tag_id)
            
            # Update metadata
            return self.update_episode_metadata(episode_id, metadata)
        
        return metadata
    
    def remove_tag_from_episode(self, episode_id: str, tag_id: str) -> Dict[str, Any]:
        """Remove a tag from an episode.
        
        Args:
            episode_id: ID of the episode
            tag_id: ID of the tag to remove
        
        Returns:
            Updated episode metadata
        """
        # Get current metadata
        metadata = self.get_episode_metadata(episode_id)
        if not metadata:
            error_msg = f"Episode not found: {episode_id}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Remove tag if present
        if 'tags' in metadata and tag_id in metadata['tags']:
            metadata['tags'].remove(tag_id)
            
            # Update metadata
            return self.update_episode_metadata(episode_id, metadata)
        
        return metadata
    
    def list_episodes(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """List all episodes with metadata, applying optional filters.
        
        Args:
            filters: Optional dictionary of filter criteria
        
        Returns:
            List of episode metadata
        """
        # Get all episodes from story structure
        all_episodes = self.story_structure.list_episodes()
        
        # Enhance with metadata
        enhanced_episodes = []
        
        for episode in all_episodes:
            episode_id = episode.get("episode_id")
            if not episode_id:
                continue
            
            # Get metadata
            metadata = self.get_episode_metadata(episode_id)
            
            # Create enhanced info
            enhanced = {**episode, **metadata}
            enhanced_episodes.append(enhanced)
        
        # Apply filters if provided
        if filters:
            filtered_episodes = []
            
            for episode in enhanced_episodes:
                include = True
                
                for key, value in filters.items():
                    if key == 'tags':
                        # Special handling for tags filter
                        episode_tags = episode.get('tags', [])
                        if not set(value).issubset(set(episode_tags)):
                            include = False
                            break
                    elif key == 'series':
                        # Check series name or ID
                        if value != episode.get('series'):
                            include = False
                            break
                    elif key == 'status':
                        if value != episode.get('status'):
                            include = False
                            break
                    elif key == 'search':
                        # Search in title or description
                        title = episode.get('title', '').lower()
                        description = episode.get('description', '').lower()
                        if value.lower() not in title and value.lower() not in description:
                            include = False
                            break
                    elif key == 'date_range':
                        # Check if episode created_at is within range
                        if not self._is_in_date_range(
                            episode.get('created_at', 0), 
                            value.get('start'), 
                            value.get('end')
                        ):
                            include = False
                            break
                    elif key not in episode or episode[key] != value:
                        include = False
                        break
                
                if include:
                    filtered_episodes.append(episode)
            
            return filtered_episodes
        
        return enhanced_episodes
    
    def _is_in_date_range(self, timestamp: float, start: Optional[float] = None, 
                         end: Optional[float] = None) -> bool:
        """Check if a timestamp is within a date range.
        
        Args:
            timestamp: The timestamp to check
            start: Optional start timestamp
            end: Optional end timestamp
        
        Returns:
            True if timestamp is within range, False otherwise
        """
        if start is not None and timestamp < start:
            return False
        
        if end is not None and timestamp > end:
            return False
        
        return True
    
    def _normalize_id(self, name: str) -> str:
        """Normalize a name to create a valid ID.
        
        Args:
            name: Name to normalize
        
        Returns:
            Normalized ID
        """
        # Remove non-alphanumeric characters and replace spaces with underscores
        normalized = re.sub(r'[^\w\s]', '', name).strip().lower().replace(' ', '_')
        
        # If empty after normalization, use a random ID
        if not normalized:
            normalized = f"id_{uuid.uuid4().hex[:8]}"
        
        return normalized
    
    def generate_episode_feed(self, format: str = "json", 
                            filters: Optional[Dict[str, Any]] = None) -> str:
        """Generate an episode feed in the specified format.
        
        Args:
            format: Output format (json, rss, etc.)
            filters: Optional filters to apply
        
        Returns:
            Formatted feed string
        """
        # Get filtered episodes
        episodes = self.list_episodes(filters=filters)
        
        # Sort by episode number and series
        episodes.sort(key=lambda ep: (ep.get("series", ""), ep.get("episode_number", 0)))
        
        if format.lower() == "json":
            return json.dumps({
                "episodes": episodes,
                "generated_at": time.time(),
                "count": len(episodes)
            }, indent=2)
        elif format.lower() == "rss":
            # Simple RSS generation for podcast feed
            rss = '<?xml version="1.0" encoding="UTF-8"?>\n'
            rss += '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">\n'
            rss += '  <channel>\n'
            rss += '    <title>Stardock Podium AI Podcast</title>\n'
            rss += f"    <description>{legacy('rss_description')}</description>\n"
            rss += f'    <lastBuildDate>{time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())}</lastBuildDate>\n'
            
            for episode in episodes:
                # Skip episodes without audio
                if not episode.get("has_audio"):
                    continue
                
                episode_id = episode.get("episode_id")
                title = episode.get("title", "Unknown Episode")
                description = episode.get("description", "")
                series = episode.get("series", "Main Series")
                
                rss += '    <item>\n'
                rss += f'      <title>{title}</title>\n'
                rss += f'      <description>{description}</description>\n'
                rss += f'      <guid>{episode_id}</guid>\n'
                
                # Add enclosure if audio file path is known
                audio_file = self.episodes_dir / episode_id / "audio" / "full_episode.mp3"
                if audio_file.exists():
                    file_size = audio_file.stat().st_size
                    rss += f'      <enclosure url="episodes/{episode_id}/audio/full_episode.mp3" length="{file_size}" type="audio/mpeg" />\n'
                
                rss += '    </item>\n'
            
            rss += '  </channel>\n'
            rss += '</rss>\n'
            
            return rss
        else:
            error_msg = f"Unsupported feed format: {format}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})
    
    def analyze_episode_stats(self) -> Dict[str, Any]:
        """Analyze statistics about episodes.
        
        Returns:
            Dictionary with episode statistics
        """
        episodes = self.list_episodes()
        
        # Count by series
        series_counts = {}
        for episode in episodes:
            series = episode.get("series", "Uncategorized")
            if series not in series_counts:
                series_counts[series] = 0
            series_counts[series] += 1
        
        # Count by status
        status_counts = {}
        for episode in episodes:
            status = episode.get("status", "draft")
            if status not in status_counts:
                status_counts[status] = 0
            status_counts[status] += 1
        
        # Count by tag
        tag_counts = {}
        for episode in episodes:
            for tag_id in episode.get("tags", []):
                if tag_id not in tag_counts:
                    tag_counts[tag_id] = 0
                tag_counts[tag_id] += 1
        
        # Get tag names
        tag_stats = []
        for tag_id, count in tag_counts.items():
            tag_info = self.get_tag(tag_id)
            if tag_info:
                tag_stats.append({
                    "tag_id": tag_id,
                    "name": tag_info.get("name", "Unknown"),
                    "count": count
                })
        
        # Get series info
        series_stats = []
        for series_id, count in series_counts.items():
            series_info = self.get_series(series_id)
            if series_info:
                series_stats.append({
                    "series_id": series_id,
                    "name": series_info.get("name", series_id),
                    "count": count
                })
            else:
                series_stats.append({
                    "series_id": series_id,
                    "name": series_id,
                    "count": count
                })
        
        # Calculate other stats
        total_episodes = len(episodes)
        episodes_with_audio = sum(1 for ep in episodes if ep.get("has_audio"))
        
        return {
            "total_episodes": total_episodes,
            "episodes_with_audio": episodes_with_audio,
            "series_stats": series_stats,
            "status_counts": status_counts,
            "tag_stats": tag_stats,
            "generated_at": time.time()
        }

# Singleton instance
_episode_metadata = None

def get_episode_metadata_manager() -> EpisodeMetadata:
    """Get the EpisodeMetadata singleton instance."""
    global _episode_metadata
    
    if _episode_metadata is None:
        _episode_metadata = EpisodeMetadata()
    
    return _episode_metadata

def update_metadata(episode_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update metadata for an episode.
    
    Args:
        episode_id: ID of the episode
        metadata: Updated metadata fields
    
    Returns:
        Updated episode metadata
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.update_episode_metadata(episode_id, metadata)

def get_metadata(episode_id: str) -> Dict[str, Any]:
    """Get metadata for an episode.
    
    Args:
        episode_id: ID of the episode
    
    Returns:
        Episode metadata
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.get_episode_metadata(episode_id)

def list_episodes(filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """List all episodes with metadata, applying optional filters.
    
    Args:
        filters: Optional dictionary of filter criteria
    
    Returns:
        List of episode metadata
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.list_episodes(filters)

def register_series(series_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new series or update existing one.
    
    Args:
        series_data: Dictionary with series information
    
    Returns:
        Updated series data with status
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.register_series(series_data)

def list_series() -> List[Dict[str, Any]]:
    """List all registered series.
    
    Returns:
        List of series data
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.list_series()

def create_tag(tag_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update a tag in the registry.
    
    Args:
        tag_data: Dictionary with tag information
    
    Returns:
        Updated tag data with status
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.create_tag(tag_data)

def list_tags(category: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all registered tags, optionally filtered by category.
    
    Args:
        category: Optional category to filter by
    
    Returns:
        List of tag data
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.list_tags(category)

def add_tag_to_episode(episode_id: str, tag_id: str) -> Dict[str, Any]:
    """Add a tag to an episode.
    
    Args:
        episode_id: ID of the episode
        tag_id: ID of the tag to add
    
    Returns:
        Updated episode metadata
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.add_tag_to_episode(episode_id, tag_id)

def generate_feed(format: str = "json", 
                filters: Optional[Dict[str, Any]] = None) -> str:
    """Generate an episode feed in the specified format.
    
    Args:
        format: Output format (json, rss, etc.)
        filters: Optional filters to apply
    
    Returns:
        Formatted feed string
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.generate_episode_feed(format, filters)

def get_episode_stats() -> Dict[str, Any]:
    """Get statistics about episodes.
    
    Returns:
        Dictionary with episode statistics
    """
    metadata_manager = get_episode_metadata_manager()
    return metadata_manager.analyze_episode_stats()