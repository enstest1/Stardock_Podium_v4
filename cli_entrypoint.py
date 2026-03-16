#!/usr/bin/env python
"""
CLI Entrypoint for the Stardock Podium AI System.

This module serves as the main command-line interface for the Star Trek-style podcast
generation system. It provides commands for:
- Book ingestion and analysis
- Episode generation and management
- Voice registry management
- Audio generation and post-processing
- Quality checking

All functionality is accessible through a unified CLI using argparse.
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("stardock_podium.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Create base directories
def create_directories():
    """Create necessary directories for the application."""
    directories = [
        "books",
        "analysis",
        "episodes",
        "audio",
        "voices",
        "temp",
        "data"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.debug(f"Created directory: {directory}")

class CommandRegistry:
    """Registry for all available commands."""
    
    def __init__(self):
        self.commands = {}
        
    def register(self, name: str, func: callable, help_text: str, arguments: List[Dict[str, Any]]):
        """Register a command with its function, help text, and arguments."""
        self.commands[name] = {
            'func': func,
            'help': help_text,
            'arguments': arguments
        }
    
    def get_command(self, name: str):
        """Get a registered command by name."""
        return self.commands.get(name)
    
    def get_all_commands(self):
        """Get all registered commands."""
        return self.commands

# Initialize command registry
cmd_registry = CommandRegistry()

# Define argument types for better clarity
STR_ARG = {'type': str}
INT_ARG = {'type': int}
FLOAT_ARG = {'type': float}
BOOL_ARG = {'action': 'store_true'}
FILE_ARG = {'type': str}  # Actually a path, but represented as string
DIR_ARG = {'type': str}   # Actually a path, but represented as string

def register_command(name: str, help_text: str, arguments: List[Dict[str, Any]]):
    """Decorator to register commands with the registry."""
    def decorator(func):
        cmd_registry.register(name, func, help_text, arguments)
        return func
    return decorator

# Command implementations will be imported from respective modules after they are created

@register_command(
    name="ingest",
    help_text="Ingest and process reference books",
    arguments=[
        {'name': 'file_path', **FILE_ARG, 'help': 'Path to EPUB file to ingest'},
        {'name': '--analyze', **BOOL_ARG, 'help': 'Perform style analysis after ingestion'}
    ]
)
def cmd_ingest(args):
    """Ingest an EPUB book and optionally analyze its style."""
    from epub_processor import process_epub
    result = process_epub(args.file_path)
    
    if args.analyze and result:
        from book_style_analysis import analyze_book_style
        analyze_book_style(result['book_id'])
    
    if result:
        logger.info(f"Successfully ingested: {result['title']}")
        return True
    return False

@register_command(
    name="analyze",
    help_text="Analyze style and content of ingested books",
    arguments=[
        {'name': 'book_id', **STR_ARG, 'help': 'ID of the book to analyze'},
        {'name': '--deep', **BOOL_ARG, 'help': 'Perform deep analysis'}
    ]
)
def cmd_analyze(args):
    """Analyze the style and content of an ingested book."""
    from book_style_analysis import analyze_book_style
    return analyze_book_style(args.book_id, deep=args.deep)

@register_command(
    name="sync-memory",
    help_text="Sync reference materials to vector memory",
    arguments=[
        {'name': '--all', **BOOL_ARG, 'help': 'Sync all available books'},
        {'name': '--book-id', **STR_ARG, 'help': 'ID of specific book to sync', 'required': False}
    ]
)
def cmd_sync_memory(args):
    """Sync reference materials to the vector memory database."""
    from reference_memory_sync import sync_references
    
    if args.all:
        return sync_references()
    elif args.book_id:
        return sync_references(book_id=args.book_id)
    else:
        logger.error("Either --all or --book-id must be specified")
        return False

@register_command(
    name="generate-episode",
    help_text="Generate a new podcast episode",
    arguments=[
        {'name': '--title', **STR_ARG, 'help': 'Episode title', 'required': False},
        {'name': '--theme', **STR_ARG, 'help': 'Theme or topic for the episode', 'required': False},
        {'name': '--series', **STR_ARG, 'help': 'Series name', 'default': 'Main Series'},
        {'name': '--episode-number', **INT_ARG, 'help': 'Episode number', 'required': False},
        {'name': '--duration', **INT_ARG, 'help': 'Target duration in minutes', 'default': 30}
    ]
)
def cmd_generate_episode(args):
    """Generate a new podcast episode."""
    from story_structure import generate_episode
    
    episode_data = {
        'title': args.title,
        'theme': args.theme,
        'series': args.series,
        'episode_number': args.episode_number,
        'target_duration': args.duration
    }
    
    return generate_episode(episode_data)

@register_command(
    name="edit-script",
    help_text="Edit an episode script",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode to edit'}
    ]
)
def cmd_edit_script(args):
    """Open an episode script for editing."""
    from script_editor import edit_episode_script
    return edit_episode_script(args.episode_id)

@register_command(
    name="regenerate-scene",
    help_text="Regenerate a scene in an episode",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode'},
        {'name': 'scene_index', **INT_ARG, 'help': 'Index of the scene to regenerate'},
        {'name': '--instructions', **STR_ARG, 'help': 'Special instructions for regeneration', 'required': False}
    ]
)
def cmd_regenerate_scene(args):
    """Regenerate a specific scene in an episode."""
    from script_editor import regenerate_scene
    return regenerate_scene(args.episode_id, args.scene_index, args.instructions)

@register_command(
    name="register-voice",
    help_text="Register a new voice in the voice registry",
    arguments=[
        {'name': 'name', **STR_ARG, 'help': 'Character name for the voice'},
        {'name': 'voice_id', **STR_ARG, 'help': 'ElevenLabs voice ID'},
        {'name': '--description', **STR_ARG, 'help': 'Voice description', 'required': False},
        {'name': '--character-bio', **STR_ARG, 'help': 'Character biography', 'required': False}
    ]
)
def cmd_register_voice(args):
    """Register a new voice in the voice registry."""
    from voice_registry import register_voice
    
    voice_data = {
        'name': args.name,
        'voice_id': args.voice_id,
        'description': args.description,
        'character_bio': args.character_bio
    }
    
    return register_voice(voice_data)

@register_command(
    name="list-voices",
    help_text="List all registered voices",
    arguments=[]
)
def cmd_list_voices(args):
    """List all registered voices."""
    from voice_registry import list_voices
    return list_voices()

@register_command(
    name="generate-audio",
    help_text="Generate audio for an episode",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode'},
        {'name': '--output-dir', **DIR_ARG, 'help': 'Output directory', 'default': 'audio'},
        {'name': '--format', **STR_ARG, 'help': 'Output format', 'default': 'mp3'},
        {'name': '--quality', **STR_ARG, 'help': 'Audio quality', 'default': 'high', 
         'choices': ['low', 'medium', 'high']}
    ]
)
def cmd_generate_audio(args):
    """Generate audio for an episode."""
    from audio_pipeline import generate_episode_audio
    
    options = {
        'output_dir': args.output_dir,
        'format': args.format,
        'quality': args.quality
    }
    
    return generate_episode_audio(args.episode_id, options)

@register_command(
    name="check-quality",
    help_text="Check the quality of an episode",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode to check'},
        {'name': '--script-only', **BOOL_ARG, 'help': 'Check only the script quality'},
        {'name': '--audio-only', **BOOL_ARG, 'help': 'Check only the audio quality'}
    ]
)
def cmd_check_quality(args):
    """Check the quality of an episode."""
    from quality_checker import check_episode_quality
    
    check_options = {
        'check_script': not args.audio_only,
        'check_audio': not args.script_only
    }
    
    return check_episode_quality(args.episode_id, check_options)

@register_command(
    name="list-episodes",
    help_text="List all generated episodes",
    arguments=[
        {'name': '--series', **STR_ARG, 'help': 'Filter by series', 'required': False},
        {'name': '--status', **STR_ARG, 'help': 'Filter by status', 'required': False, 
         'choices': ['draft', 'complete', 'published']}
    ]
)
def cmd_list_episodes(args):
    """List all generated episodes."""
    from episode_metadata import list_episodes
    
    filters = {}
    if args.series:
        filters['series'] = args.series
    if args.status:
        filters['status'] = args.status
    
    return list_episodes(filters)

@register_command(
    name="generate-characters",
    help_text="Generate a cast of characters for an episode",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode to generate characters for'}
    ]
)
def cmd_generate_characters(args):
    """Generate characters for an episode."""
    from story_structure import generate_characters
    return generate_characters(args.episode_id)

@register_command(
    name="generate-scenes",
    help_text="Generate scenes for an episode (requires characters)",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode to generate scenes for'}
    ]
)
def cmd_generate_scenes(args):
    """Generate scenes for an episode."""
    import asyncio
    from story_structure import generate_scenes
    return asyncio.run(generate_scenes(args.episode_id))

@register_command(
    name="extract-memories",
    help_text="Extract and store memories from an episode for continuity",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode to extract memories from'}
    ]
)
def cmd_extract_memories(args):
    """Extract memories from an episode."""
    from episode_memory import extract_memories
    memories = extract_memories(args.episode_id)
    print(f"Extracted memories for episode {args.episode_id}")
    print(f"Categories: {list(memories.keys())}")
    for category, entries in memories.items():
        print(f"  {category}: {len(entries)} entries")
    return True

@register_command(
    name="view-memories",
    help_text="View memories for an episode",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode to view memories for'},
        {'name': '--category', **STR_ARG, 'help': 'Filter by memory category', 'required': False}
    ]
)
def cmd_view_memories(args):
    """View memories for an episode."""
    from episode_memory import get_episode_memory
    memory_manager = get_episode_memory()
    
    if args.category:
        memories = memory_manager.get_all_memories(episode_id=args.episode_id, category=args.category)
    else:
        memories = memory_manager.get_all_memories(episode_id=args.episode_id)
    
    print(f"Found {len(memories)} memories for episode {args.episode_id}")
    for memory in memories[:10]:  # Show first 10
        metadata = memory.get('metadata', {})
        print(f"\nCategory: {metadata.get('category', 'unknown')}")
        print(f"Content: {memory.get('memory', '')[:200]}...")
    
    return True

@register_command(
    name="get-continuity",
    help_text="Get continuity context from previous episodes",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the current episode'},
        {'name': '--limit', **INT_ARG, 'help': 'Maximum number of memories to retrieve', 'default': 20}
    ]
)
def cmd_get_continuity(args):
    """Get continuity context for an episode."""
    from episode_memory import get_episode_memory
    from story_structure import get_story_structure
    memory_manager = get_episode_memory()
    story_structure = get_story_structure()
    
    # Get episode to find episode number
    episode = story_structure.get_episode(args.episode_id)
    if not episode:
        print(f"Episode not found: {args.episode_id}")
        return False
    
    episode_number = episode.get("episode_number", 0)
    series = episode.get("series")
    
    context = memory_manager.get_previous_episode_context(
        current_episode_number=episode_number,
        series=series,
        limit=args.limit
    )
    
    print(f"Continuity context for episode {episode_number}:\n")
    print(f"Plot Points: {len(context.get('plot_points', []))}")
    print(f"Character States: {len(context.get('character_states', []))}")
    print(f"Unresolved Threads: {len(context.get('unresolved_threads', []))}")
    print(f"Relationships: {len(context.get('relationships', []))}")
    print(f"World Building: {len(context.get('world_building', []))}")
    
    if context.get('unresolved_threads'):
        print("\nUnresolved Threads:")
        for thread in context['unresolved_threads'][:5]:
            print(f"  - {thread[:150]}...")
    
    return True

def main():
    """Main entry point for the CLI."""
    # Create required directories
    create_directories()
    
    # Set up the argument parser
    parser = argparse.ArgumentParser(
        description='Stardock Podium - AI Star Trek podcast generator',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Add version
    parser.add_argument('--version', action='version', version='Stardock Podium v0.1.0')
    
    # Create subparsers for each command
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Register all commands from the registry
    for cmd_name, cmd_info in cmd_registry.get_all_commands().items():
        cmd_parser = subparsers.add_parser(cmd_name, help=cmd_info['help'])
        
        for arg in cmd_info['arguments']:
            arg_name = arg.pop('name')
            cmd_parser.add_argument(arg_name, **arg)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Get and execute the command
    cmd_info = cmd_registry.get_command(args.command)
    if not cmd_info:
        logger.error(f"Unknown command: {args.command}")
        return 1
    
    try:
        result = cmd_info['func'](args)
        return 0 if result else 1
    except Exception as e:
        logger.exception(f"Error executing command {args.command}: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())