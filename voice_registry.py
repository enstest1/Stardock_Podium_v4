#!/usr/bin/env python
"""
Voice Registry Module for Stardock Podium.

This module manages the registration, retrieval, and mapping of character
voices using the ElevenLabs API. It maintains persistent voice metadata
to ensure character voice consistency across episodes.
"""

import os
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

# Try to import ElevenLabs
try:
    from elevenlabs import ElevenLabs, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
except ImportError:
    logging.error("ElevenLabs not found. Please install it with: pip install elevenlabs")
    raise

# Local imports
from mem0_client import get_mem0_client

# Setup logging
logger = logging.getLogger(__name__)

class VoiceRegistry:
    """Manages voice registration and retrieval for characters."""
    
    def __init__(self, voices_dir: str = "voices"):
        """Initialize the voice registry.
        
        Args:
            voices_dir: Directory to store voice metadata
        """
        self.voices_dir = Path(voices_dir)
        self.voices_dir.mkdir(exist_ok=True)
        
        # Load ElevenLabs API key from environment
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY not found in environment variables")
        
        # Initialize ElevenLabs client if API key is available
        if self.api_key:
            self.client = ElevenLabsClient(api_key=self.api_key)
            self.elevenlabs = ElevenLabs(api_key=self.api_key)
        else:
            self.client = None
            self.elevenlabs = None
        
        # Initialize mem0 client
        self.mem0_client = get_mem0_client()
        
        # Load registry
        self.registry = self._load_registry()
    
    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load the voice registry from file.
        
        Returns:
            Dictionary of voice registry entries
        """
        registry_file = self.voices_dir / "registry.json"
        
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading voice registry: {e}")
        
        # Return empty registry if file doesn't exist or loading fails
        return {}
    
    def _save_registry(self) -> None:
        """Save the voice registry to file."""
        registry_file = self.voices_dir / "registry.json"
        
        try:
            with open(registry_file, 'w') as f:
                json.dump(self.registry, f, indent=2)
            
            logger.info("Voice registry saved successfully")
        except Exception as e:
            logger.error(f"Error saving voice registry: {e}")
    
    def register_voice(self, voice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new voice in the registry.
        
        Args:
            voice_data: Voice data including name, voice_id, and description
        
        Returns:
            Registered voice data with ID
        """
        # Ensure required fields are present
        required_fields = ['name', 'voice_id']
        for field in required_fields:
            if field not in voice_data:
                error_msg = f"Missing required field: {field}"
                logger.error(error_msg)
                return {"error": error_msg}
        
        # Check if voice exists with ElevenLabs if client is available
        if self.client and 'voice_id' in voice_data:
            try:
                # Check if voice ID exists
                voices = self.client.voices.get_all()
                voice_ids = [voice.voice_id for voice in voices.voices]
                
                if voice_data['voice_id'] not in voice_ids:
                    error_msg = f"Voice ID not found in ElevenLabs: {voice_data['voice_id']}"
                    logger.error(error_msg)
                    return {"error": error_msg}
            except Exception as e:
                logger.warning(f"Couldn't verify voice ID with ElevenLabs: {e}")
        
        # Generate a unique voice registry ID
        voice_registry_id = voice_data.get('voice_registry_id', f"voice_{uuid.uuid4().hex[:8]}")
        
        # Prepare voice entry
        voice_entry = {
            "voice_registry_id": voice_registry_id,
            "name": voice_data['name'],
            "voice_id": voice_data['voice_id'],
            "description": voice_data.get('description', ''),
            "character_bio": voice_data.get('character_bio', ''),
            "created_at": time.time(),
            "updated_at": time.time(),
            "settings": voice_data.get('settings', {})
        }
        
        # Add to registry
        self.registry[voice_registry_id] = voice_entry
        
        # Save registry
        self._save_registry()
        
        # Add to memory
        self._add_voice_to_memory(voice_entry)
        
        return voice_entry
    
    def get_voice(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get a voice by ID or character name.
        
        Args:
            identifier: Voice registry ID or character name
        
        Returns:
            Voice data if found, None otherwise
        """
        # Check if it's a direct ID match
        if identifier in self.registry:
            return self.registry[identifier]
        
        # Check for character name match
        for voice_id, voice in self.registry.items():
            if voice.get('name', '').lower() == identifier.lower():
                return voice
        
        # No match found
        return None
    
    def update_voice(self, voice_registry_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing voice entry.
        
        Args:
            voice_registry_id: ID of the voice in the registry
            updates: Dictionary of fields to update
        
        Returns:
            Updated voice data
        """
        # Check if voice exists
        if voice_registry_id not in self.registry:
            error_msg = f"Voice not found in registry: {voice_registry_id}"
            logger.error(error_msg)
            return {"error": error_msg}
        
        # Create a copy of the current entry
        voice_entry = self.registry[voice_registry_id].copy()
        
        # Update fields
        for key, value in updates.items():
            if key != 'voice_registry_id':  # Don't allow changing the ID
                voice_entry[key] = value
        
        # Update timestamp
        voice_entry['updated_at'] = time.time()
        
        # Save to registry
        self.registry[voice_registry_id] = voice_entry
        self._save_registry()
        
        # Update in memory
        self._add_voice_to_memory(voice_entry)
        
        return voice_entry
    
    def delete_voice(self, voice_registry_id: str) -> Dict[str, Any]:
        """Delete a voice from the registry.
        
        Args:
            voice_registry_id: ID of the voice in the registry
        
        Returns:
            Status of the delete operation
        """
        # Check if voice exists
        if voice_registry_id not in self.registry:
            error_msg = f"Voice not found in registry: {voice_registry_id}"
            logger.error(error_msg)
            return {"error": error_msg, "success": False}
        
        # Remove from registry
        deleted_voice = self.registry.pop(voice_registry_id)
        
        # Save registry
        self._save_registry()
        
        return {"success": True, "deleted": deleted_voice}
    
    def list_voices(self) -> List[Dict[str, Any]]:
        """List all registered voices.
        
        Returns:
            List of all voice entries
        """
        return list(self.registry.values())
    
    def _add_voice_to_memory(self, voice_entry: Dict[str, Any]) -> None:
        """Add voice entry to memory for searchability.
        
        Args:
            voice_entry: Voice entry to add to memory
        """
        try:
            # Create memory-friendly representation
            voice_info = (
                f"Voice Registry Entry - Character: {voice_entry.get('name', '')}\n"
                f"Voice ID: {voice_entry.get('voice_id', '')}\n"
                f"Description: {voice_entry.get('description', '')}\n"
                f"Character Bio: {voice_entry.get('character_bio', '')}"
            )
            
            # Add to memory
            self.mem0_client.add_memory(
                content=voice_info,
                user_id="voice_registry",
                memory_type=self.mem0_client.VOICE_METADATA,
                metadata={
                    "voice_registry_id": voice_entry.get("voice_registry_id"),
                    "name": voice_entry.get("name"),
                    "voice_id": voice_entry.get("voice_id")
                }
            )
            
            logger.debug(f"Added voice to memory: {voice_entry.get('name')}")
        except Exception as e:
            logger.error(f"Error adding voice to memory: {e}")
    
    def find_voices_by_description(self, description: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Find voices that match a description using semantic search.
        
        Args:
            description: Voice or character description
            limit: Maximum number of results
        
        Returns:
            List of matching voice entries
        """
        # Search memory for matching voices
        results = self.mem0_client.search_memory(
            query=description,
            user_id="voice_registry",
            memory_type=self.mem0_client.VOICE_METADATA,
            limit=limit
        )
        
        # Convert to voice entries
        voices = []
        for result in results:
            metadata = result.get('metadata', {})
            voice_id = metadata.get('voice_registry_id')
            
            if voice_id and voice_id in self.registry:
                voices.append(self.registry[voice_id])
        
        return voices
    
    def create_voice_from_description(self, name: str, description: str) -> Dict[str, Any]:
        """Create a new ElevenLabs voice from a text description.
        
        Args:
            name: Name of the character/voice
            description: Detailed voice description
        
        Returns:
            Created voice data
        """
        if not self.client:
            error_msg = "ElevenLabs client not initialized (no API key)"
            logger.error(error_msg)
            return {"error": error_msg}
        
        try:
            # Generate voice samples
            voice_preview = self.client.text_to_voice.create_previews(
                voice_description=description,
                text="Welcome to Stardock Podium, the Star Trek podcast generator. My name is " + name + ". I'll be your guide through this adventure.",
            )
            
            if not voice_preview.previews:
                error_msg = "No voice previews generated"
                logger.error(error_msg)
                return {"error": error_msg}
            
            # Create voice from preview
            voice = self.client.text_to_voice.create_voice_from_preview(
                voice_name=name,
                voice_description=description,
                generated_voice_id=voice_preview.previews[0].generated_voice_id,
            )
            
            # Register voice
            voice_data = {
                "name": name,
                "voice_id": voice.voice_id,
                "description": description,
                "settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            
            return self.register_voice(voice_data)
        
        except Exception as e:
            error_msg = f"Error creating voice: {e}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def generate_speech(self, text: str, voice_identifier: str, 
                      output_path: Optional[str] = None) -> bytes:
        """Generate speech audio for a given text and voice.
        
        Args:
            text: Text to convert to speech
            voice_identifier: Voice registry ID or character name
            output_path: Optional path to save the audio file
        
        Returns:
            Audio data as bytes
        """
        if not self.elevenlabs:
            raise RuntimeError("ElevenLabs client not initialized")
        
        # Get voice data
        voice_data = self.get_voice(voice_identifier)
        if not voice_data:
            raise ValueError(f"Voice not found: {voice_identifier}")
        
        voice_id = voice_data['voice_id']
        settings = voice_data.get('settings', {})
        
        voice_settings = VoiceSettings(
            stability=settings.get('stability', 0.5),
            similarity_boost=settings.get('similarity_boost', 0.75),
            style=settings.get('style', 0.0),
            use_speaker_boost=settings.get('use_speaker_boost', True)
        )
        
        try:
            # Generate audio using the text_to_speech API
            audio_data = self.elevenlabs.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id="eleven_multilingual_v2",
                voice_settings=voice_settings
            )
            
            # Convert generator to bytes if needed
            if hasattr(audio_data, '__iter__') and not isinstance(audio_data, bytes):
                audio_data = b''.join(chunk for chunk in audio_data)
            
            # Save to file if output path is specified
            if output_path:
                with open(output_path, 'wb') as f:
                    if isinstance(audio_data, bytes):
                        f.write(audio_data)
                    else:
                        f.write(audio_data.read() if hasattr(audio_data, 'read') else bytes(audio_data))
                logger.info(f"Audio saved to {output_path}")
            
            return audio_data
        
        except Exception as e:
            error_msg = f"Error generating speech: {e}"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
    
    def check_voice_health(self, voice_registry_id: str) -> Dict[str, Any]:
        """Check if a voice is still available in ElevenLabs.
        
        Args:
            voice_registry_id: Voice registry ID
        
        Returns:
            Health status of the voice
        """
        if not self.client:
            return {"status": "unknown", "message": "ElevenLabs client not initialized"}
        
        # Get voice data
        voice_data = self.get_voice(voice_registry_id)
        if not voice_data:
            return {"status": "error", "message": f"Voice not found in registry: {voice_registry_id}"}
        
        voice_id = voice_data['voice_id']
        
        try:
            # Check if voice ID exists
            voices = self.client.voices.get_all()
            voice_ids = [voice.voice_id for voice in voices.voices]
            
            if voice_id in voice_ids:
                return {"status": "healthy", "message": "Voice available in ElevenLabs"}
            else:
                return {"status": "missing", "message": "Voice not found in ElevenLabs"}
        
        except Exception as e:
            return {"status": "error", "message": f"Error checking voice health: {e}"}
    
    def check_all_voices_health(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all voices in the registry.
        
        Returns:
            Health status for all registered voices
        """
        health_status = {}
        
        for voice_id in self.registry:
            health_status[voice_id] = self.check_voice_health(voice_id)
        
        return health_status
    
    def map_characters_to_voices(self, characters: List[Dict[str, Any]]) -> Dict[str, str]:
        """Map character names to voice IDs based on descriptions.
        
        Args:
            characters: List of character dictionaries
        
        Returns:
            Dictionary mapping character names to voice registry IDs
        """
        character_voices = {}
        
        for character in characters:
            character_name = character.get('name', '')
            if not character_name:
                continue
            
            # Check if character already has a voice
            existing_voice = None
            for voice in self.registry.values():
                if voice.get('name', '').lower() == character_name.lower():
                    existing_voice = voice
                    break
            
            if existing_voice:
                character_voices[character_name] = existing_voice['voice_registry_id']
                continue
            
            # Try to find a matching voice based on description
            voice_description = character.get('voice_description', '')
            if voice_description:
                matching_voices = self.find_voices_by_description(voice_description, limit=1)
                
                if matching_voices:
                    # Use the best match
                    character_voices[character_name] = matching_voices[0]['voice_registry_id']
                    
                    # Update voice name to match character
                    self.update_voice(
                        matching_voices[0]['voice_registry_id'],
                        {'name': character_name}
                    )
                else:
                    # Create a new voice if possible
                    if self.client:
                        new_voice = self.create_voice_from_description(
                            name=character_name,
                            description=voice_description
                        )
                        
                        if 'voice_registry_id' in new_voice:
                            character_voices[character_name] = new_voice['voice_registry_id']
        
        return character_voices

# Singleton instance
_voice_registry = None

def get_voice_registry() -> VoiceRegistry:
    """Get the VoiceRegistry singleton instance."""
    global _voice_registry
    
    if _voice_registry is None:
        _voice_registry = VoiceRegistry()
    
    return _voice_registry

def register_voice(voice_data: Dict[str, Any]) -> Dict[str, Any]:
    """Register a new voice in the registry.
    
    Args:
        voice_data: Voice data including name, voice_id, and description
    
    Returns:
        Registered voice data with ID
    """
    registry = get_voice_registry()
    return registry.register_voice(voice_data)

def get_voice(identifier: str) -> Optional[Dict[str, Any]]:
    """Get a voice by ID or character name.
    
    Args:
        identifier: Voice registry ID or character name
    
    Returns:
        Voice data if found, None otherwise
    """
    registry = get_voice_registry()
    return registry.get_voice(identifier)

def list_voices() -> List[Dict[str, Any]]:
    """List all registered voices.
    
    Returns:
        List of all voice entries
    """
    registry = get_voice_registry()
    return registry.list_voices()

def generate_speech(text: str, voice_identifier: str, 
                   output_path: Optional[str] = None) -> bytes:
    """Generate speech audio for a given text and voice.
    
    Args:
        text: Text to convert to speech
        voice_identifier: Voice registry ID or character name
        output_path: Optional path to save the audio file
    
    Returns:
        Audio data as bytes
    """
    registry = get_voice_registry()
    return registry.generate_speech(text, voice_identifier, output_path)

def create_voice_from_description(name: str, description: str) -> Dict[str, Any]:
    """Create a new ElevenLabs voice from a text description.
    
    Args:
        name: Name of the character/voice
        description: Detailed voice description
    
    Returns:
        Created voice data
    """
    registry = get_voice_registry()
    return registry.create_voice_from_description(name, description)

def map_characters_to_voices(characters: List[Dict[str, Any]]) -> Dict[str, str]:
    """Map character names to voice IDs based on descriptions.
    
    Args:
        characters: List of character dictionaries
    
    Returns:
        Dictionary mapping character names to voice registry IDs
    """
    registry = get_voice_registry()
    return registry.map_characters_to_voices(characters)