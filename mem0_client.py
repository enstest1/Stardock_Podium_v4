#!/usr/bin/env python
"""
Mem0 Client Module for Stardock Podium.

Provides a wrapper around the Mem0 vector database API for storing and retrieving
episode memory, character information, and reference materials.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import uuid

# Import Mem0 SDK
try:
    from mem0 import Memory, MemoryClient
except ImportError:
    logging.error("Mem0 SDK not found. Please install it with: pip install mem0")
    raise

# Setup logging
logger = logging.getLogger(__name__)

class Mem0Client:
    """Client for interacting with Mem0 vector database.
    
    This class handles the connection to Mem0 and provides methods for
    storing and retrieving different types of data:
    - Episode memory (plots, characters, events)
    - Reference materials (from ingested books)
    - Character information
    - Voice metadata
    """
    
    # Constants for memory types/categories
    REFERENCE_MATERIAL = "reference_material"
    EPISODE_MEMORY = "episode_memory"
    CHARACTER_INFO = "character_info"
    VOICE_METADATA = "voice_metadata"
    STORY_STRUCTURE = "story_structure"
    
    def __init__(self, api_key: Optional[str] = None, config_path: Optional[str] = None):
        """Initialize the Mem0 client with API key or config.
        
        Args:
            api_key: Optional Mem0 API key (if not provided, will try to load from config or env)
            config_path: Optional path to a configuration file
        """
        self.api_key = api_key or os.environ.get("MEM0_API_KEY")
        self.config_path = config_path or "data/mem0_config.json"
        self.config = self._load_config()
        
        self._initialize_client()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default."""
        config_file = Path(self.config_path)
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
        
        # Default configuration
        default_config = {
            "version": "v1.1",
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-large"
                }
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "stardock_podium",
                    "embedding_model_dims": 3072,
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                }
            }
        }
        
        # Ensure directory exists
        config_file.parent.mkdir(exist_ok=True, parents=True)
        
        # Save default config
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def _initialize_client(self):
        """Initialize the Mem0 client with the current configuration."""
        try:
            if self.api_key:
                # Use managed platform with API key
                os.environ["MEM0_API_KEY"] = self.api_key
                self.client = MemoryClient()
                logger.info("Initialized Mem0 client using API key")
            else:
                # Use local configuration
                self.memory = Memory.from_config(self.config)
                logger.info("Initialized Mem0 client using local configuration")
        except Exception as e:
            logger.error(f"Failed to initialize Mem0 client: {e}")
            raise
    
    def add_memory(self, content: str, user_id: str, memory_type: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add a memory to the database.
        
        Args:
            content: The text content to store
            user_id: The user ID (used for namespacing)
            memory_type: The type/category of memory
            metadata: Optional metadata to store with the memory
        
        Returns:
            Dict with memory ID and status
        """
        if not metadata:
            metadata = {}
        
        # Ensure memory_type is in metadata for filtering
        metadata["memory_type"] = memory_type
        
        try:
            if hasattr(self, 'client'):
                # Managed platform — mem0ai>=1.0
                result = self.client.add(
                    content,
                    user_id=user_id,
                    metadata=metadata,
                )
            else:
                result = self.memory.add(
                    content, user_id=user_id, metadata=metadata)
            
            logger.debug(f"Added memory: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to add memory: {e}")
            raise
    
    def search_memory(self, query: str, user_id: str, memory_type: Optional[str] = None, 
                     limit: int = 5) -> List[Dict[str, Any]]:
        """Search memories based on a query string.
        
        Args:
            query: The search query
            user_id: The user ID to search within
            memory_type: Optional memory type to filter by
            limit: Maximum number of results to return
        
        Returns:
            List of memory objects matching the query
        """
        try:
            if hasattr(self, 'client'):
                # Managed platform — mem0ai>=1.0 requires
                # user_id inside filters. Custom fields like
                # memory_type go inside metadata={}.
                search_filters = {'user_id': user_id}
                if memory_type:
                    search_filters['metadata'] = {
                        'memory_type': memory_type}
                raw = self.client.search(
                    query,
                    filters=search_filters,
                    limit=limit,
                )
                # API may return {'results': [...]} or a bare list
                if isinstance(raw, dict):
                    results = raw.get('results', [])
                else:
                    results = raw if isinstance(raw, list) else []
            else:
                search_results = self.memory.search(
                    query, user_id=user_id, limit=limit)
                if memory_type and 'results' in search_results:
                    results = [
                        r for r in search_results['results']
                        if r.get('metadata', {}).get(
                            'memory_type') == memory_type
                    ]
                else:
                    results = search_results.get('results', [])
            
            logger.debug(f"Search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return []
    
    def get_all_memories(self, user_id: str, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all memories for a user, optionally filtered by type.
        
        Args:
            user_id: The user ID to retrieve memories for
            memory_type: Optional memory type to filter by
        
        Returns:
            List of memory objects
        """
        try:
            if hasattr(self, 'client'):
                # Managed platform — mem0ai>=1.0 uses filters={}
                search_filters = {'user_id': user_id}
                if memory_type:
                    search_filters['metadata'] = {
                        'memory_type': memory_type}
                raw = self.client.get_all(
                    filters=search_filters)
                if isinstance(raw, dict):
                    results = raw.get('results', [])
                else:
                    results = raw if isinstance(raw, list) else []
            else:
                all_memories = self.memory.get_all(
                    user_id=user_id)
                if memory_type and 'results' in all_memories:
                    results = [
                        r for r in all_memories['results']
                        if r.get('metadata', {}).get(
                            'memory_type') == memory_type
                    ]
                else:
                    results = all_memories.get('results', [])
            
            logger.debug(f"Retrieved {len(results)} memories")
            return results
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []
    
    def add_reference_material(self, content: str, source: str, 
                              metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add reference material from ingested books.
        
        Args:
            content: The text content to store
            source: Source identifier (book ID, title, etc.)
            metadata: Additional metadata about the content
        
        Returns:
            Dict with memory ID and status
        """
        if not metadata:
            metadata = {}
        
        metadata.update({
            "source": source,
            "added_at": time.time()
        })
        
        return self.add_memory(
            content=content,
            user_id="reference_materials",
            memory_type=self.REFERENCE_MATERIAL,
            metadata=metadata
        )
    
    def add_episode_memory(self, content: str, episode_id: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add episode memory (plot points, events, character development).
        
        Args:
            content: The memory content
            episode_id: Episode identifier
            metadata: Additional metadata
        
        Returns:
            Dict with memory ID and status
        """
        if not metadata:
            metadata = {}
        
        metadata.update({
            "episode_id": episode_id,
            "added_at": time.time()
        })
        
        return self.add_memory(
            content=content,
            user_id="episodes",
            memory_type=self.EPISODE_MEMORY,
            metadata=metadata
        )
    
    def add_character_info(self, character_name: str, info: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Add or update character information.
        
        Args:
            character_name: Name of the character
            info: Character information
            metadata: Additional metadata
        
        Returns:
            Dict with memory ID and status
        """
        if not metadata:
            metadata = {}
        
        metadata.update({
            "character_name": character_name,
            "updated_at": time.time()
        })
        
        return self.add_memory(
            content=info,
            user_id="characters",
            memory_type=self.CHARACTER_INFO,
            metadata=metadata
        )
    
    def search_reference_materials(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search reference materials based on semantic similarity.
        
        Args:
            query: The search query
            limit: Maximum number of results to return
        
        Returns:
            List of matching reference materials
        """
        return self.search_memory(
            query=query,
            user_id="reference_materials",
            memory_type=self.REFERENCE_MATERIAL,
            limit=limit
        )
    
    def search_episode_memories(self, query: str, episode_id: Optional[str] = None, 
                              limit: int = 5) -> List[Dict[str, Any]]:
        """Search episode memories.
        
        Args:
            query: The search query
            episode_id: Optional episode ID to filter by
            limit: Maximum number of results to return
        
        Returns:
            List of matching episode memories
        """
        results = self.search_memory(
            query=query,
            user_id="episodes",
            memory_type=self.EPISODE_MEMORY,
            limit=limit
        )
        
        # Filter by episode ID if specified
        if episode_id:
            results = [r for r in results 
                      if r.get('metadata', {}).get('episode_id') == episode_id]
        
        return results
    
    def search_character_info(self, query: str, character_name: Optional[str] = None, 
                             limit: int = 5) -> List[Dict[str, Any]]:
        """Search character information.
        
        Args:
            query: The search query
            character_name: Optional character name to filter by
            limit: Maximum number of results to return
        
        Returns:
            List of matching character information
        """
        results = self.search_memory(
            query=query,
            user_id="characters",
            memory_type=self.CHARACTER_INFO,
            limit=limit
        )
        
        # Filter by character name if specified
        if character_name:
            results = [r for r in results 
                      if r.get('metadata', {}).get('character_name') == character_name]
        
        return results
    
    def get_character_info(self, character_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific character.
        
        Args:
            character_name: Name of the character
        
        Returns:
            Character information or None if not found
        """
        results = self.get_all_memories(
            user_id="characters",
            memory_type=self.CHARACTER_INFO
        )
        
        for result in results:
            if result.get('metadata', {}).get('character_name') == character_name:
                return result
        
        return None
    
    def delete_memory(self, memory_id: str) -> bool:
        """Delete a specific memory by ID.
        
        Args:
            memory_id: ID of the memory to delete
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if hasattr(self, 'client'):
                # Using managed platform
                self.client.delete(memory_id)
            else:
                # Using local memory
                self.memory.delete(memory_id)
            
            logger.debug(f"Deleted memory: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    def add_story_structure(self, structure_data: Dict[str, Any], 
                           episode_id: Optional[str] = None) -> Dict[str, Any]:
        """Add story structure information.
        
        Args:
            structure_data: Story structure data (dict converted to JSON)
            episode_id: Optional episode identifier
        
        Returns:
            Dict with memory ID and status
        """
        metadata = {
            "added_at": time.time()
        }
        
        if episode_id:
            metadata["episode_id"] = episode_id
        
        # Convert dict to JSON string for storage
        content = json.dumps(structure_data)
        
        return self.add_memory(
            content=content,
            user_id="story_structures",
            memory_type=self.STORY_STRUCTURE,
            metadata=metadata
        )
    
    def get_story_structure(self, episode_id: str) -> Optional[Dict[str, Any]]:
        """Get story structure for a specific episode.
        
        Args:
            episode_id: Episode identifier
        
        Returns:
            Story structure data or None if not found
        """
        results = self.get_all_memories(
            user_id="story_structures",
            memory_type=self.STORY_STRUCTURE
        )
        
        for result in results:
            if result.get('metadata', {}).get('episode_id') == episode_id:
                try:
                    # Parse JSON string back to dict
                    return json.loads(result['memory'])
                except Exception as e:
                    logger.error(f"Failed to parse story structure data: {e}")
                    return None
        
        return None
    
    def batch_add_memories(self, memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add multiple memories in a batch operation.
        
        Args:
            memories: List of memory objects with fields:
                - content: The memory content
                - user_id: The user ID
                - memory_type: The type of memory
                - metadata: Optional metadata
        
        Returns:
            List of results for each memory added
        """
        results = []
        
        for memory in memories:
            try:
                result = self.add_memory(
                    content=memory['content'],
                    user_id=memory['user_id'],
                    memory_type=memory['memory_type'],
                    metadata=memory.get('metadata', {})
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to add memory in batch: {e}")
                results.append({"error": str(e)})
        
        return results

# Singleton instance
_mem0_client = None

def get_mem0_client() -> Mem0Client:
    """Get the Mem0Client singleton instance."""
    global _mem0_client
    
    if _mem0_client is None:
        _mem0_client = Mem0Client()
    
    return _mem0_client