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
import json
import logging
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

load_dotenv()

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
    """Create necessary directories using the centralized path config.

    Honors the ``STARDOCK_*_DIR`` env overrides so cloud deployments (RunPod,
    Docker) can redirect user data to a persistent volume.
    """
    try:
        from config.paths import ensure_all_dirs
        ensure_all_dirs()
        logger.debug("Default directories ensured via config.paths")
    except Exception as e:
        logger.warning("config.paths unavailable (%s); falling back to legacy dir creation", e)
        for directory in ("books", "analysis", "episodes", "audio",
                           "voices", "temp", "data"):
            Path(directory).mkdir(exist_ok=True)

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
    name="doctor",
    help_text="Run environment diagnostics (GPU, paths, API keys, model weights)",
    arguments=[]
)
def cmd_doctor(args):
    """Check that everything is configured correctly.

    Designed to be the first thing you run after ``setup_runpod.sh`` on a
    fresh pod — surfaces missing API keys, missing model weights, missing
    books, CPU-only fallback, etc.
    """
    print("\n" + "=" * 60)
    print("  STARDOCK PODIUM — ENVIRONMENT DIAGNOSTICS")
    print("=" * 60)

    checks: List[tuple] = []

    # Python
    checks.append(("Python", f"{sys.version.split()[0]}", True))

    # GPU / torch
    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_name(0)
            vram_gb = (
                torch.cuda.get_device_properties(0).total_memory
                // 1024 // 1024 // 1024
            )
            checks.append(("GPU", f"{gpu} ({vram_gb} GB VRAM)", True))
        else:
            checks.append(("GPU", "NOT AVAILABLE — running on CPU", False))
    except Exception as e:
        checks.append(("GPU", f"torch import failed: {e}", False))

    # API keys
    for key in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "MEM0_API_KEY"):
        val = os.environ.get(key, "")
        if val:
            checks.append((key, f"set ({val[:6]}...)", True))
        else:
            checks.append((key, "NOT SET", False))

    # Optional Eleven key (warn only, not required)
    if os.environ.get("ELEVENLABS_API_KEY"):
        checks.append(("ELEVENLABS_API_KEY", "set (optional legacy)", True))

    # Kokoro model weights (optional — KPipeline auto-downloads from HF,
    # but an explicit path lets you pin weights to a persistent volume).
    model_path_env = os.environ.get("KOKORO_MODEL_PATH", "kokoro-tts-base-ft.pt")
    model_path = Path(model_path_env)
    if model_path.exists():
        size_mb = model_path.stat().st_size // 1024 // 1024
        checks.append(("Kokoro weights", f"{model_path} ({size_mb} MB)", True))
    else:
        checks.append((
            "Kokoro weights",
            f"{model_path} missing (will auto-download on first use)",
            True,  # not fatal — Kokoro can auto-fetch
        ))

    # Paths / directories
    try:
        from config.paths import (
            BOOKS_DIR, VOICES_DIR, VOICE_SAMPLES_DIR,
            EPISODES_DIR, AUDIO_DIR, DATA_DIR, SERIES_DIR,
        )
        epubs = list(BOOKS_DIR.glob("*.epub")) if BOOKS_DIR.exists() else []
        samples = (
            list(VOICE_SAMPLES_DIR.glob("*.wav"))
            if VOICE_SAMPLES_DIR.exists() else []
        )
        checks.append((
            "Books dir",
            f"{BOOKS_DIR} ({len(epubs)} EPUBs)",
            BOOKS_DIR.exists(),
        ))
        checks.append((
            "Voice samples",
            f"{VOICE_SAMPLES_DIR} ({len(samples)} WAVs)",
            VOICES_DIR.exists(),
        ))
        checks.append(("Episodes dir", f"{EPISODES_DIR}", EPISODES_DIR.exists()))
        checks.append(("Audio dir",    f"{AUDIO_DIR}",    AUDIO_DIR.exists()))
        checks.append(("Data dir",     f"{DATA_DIR}",     DATA_DIR.exists()))

        # Bible artifact
        bible_path = SERIES_DIR / "series_bible.json"
        if bible_path.exists():
            checks.append(("Series bible", "extracted", True))
        else:
            checks.append((
                "Series bible",
                "not yet extracted (run `python main.py ingest`)",
                False,
            ))
    except Exception as e:
        checks.append(("Paths", f"config.paths failed: {e}", False))

    # FFmpeg binary
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True,
        )
        if result.returncode == 0:
            first = result.stdout.splitlines()[0] if result.stdout else "ffmpeg"
            checks.append(("FFmpeg", first, True))
        else:
            checks.append(("FFmpeg", "binary present but errored", False))
    except FileNotFoundError:
        checks.append(("FFmpeg", "NOT on PATH", False))
    except Exception as e:
        checks.append(("FFmpeg", f"check failed: {e}", False))

    # Print results
    print()
    for name, value, ok in checks:
        icon = "[OK]" if ok else "[!!]"
        print(f"  {icon}  {name:<20} {value}")

    failed = [c for c in checks if not c[2]]
    print("\n" + "=" * 60)
    if failed:
        print(f"  {len(failed)} issue(s) need attention")
        print("=" * 60 + "\n")
        return False
    print("  All checks passed — ready to generate.")
    print("=" * 60 + "\n")
    return True


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
    help_text="Generate a new podcast episode (optional Level 3 prompt via --theme)",
    arguments=[
        {'name': '--title', **STR_ARG, 'help': 'Episode title', 'required': False},
        {'name': '--theme', **STR_ARG, 'help': 'Level 3 prompt — what THIS episode is about', 'required': False},
        {'name': '--series', **STR_ARG, 'help': 'Series name', 'default': 'Main Series'},
        {'name': '--episode-number', **INT_ARG, 'help': 'Episode number', 'required': False},
        {'name': '--duration', **INT_ARG, 'help': 'Target duration in minutes', 'default': 30},
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
    help_text="Register a character voice using a WAV reference clip (Kokoro)",
    arguments=[
        {
            'name': 'name',
            **STR_ARG,
            'help': (
                'Character name (match script), e.g. "COMMANDER ZARA VOSS"'
            ),
        },
        {
            'name': 'speaker_wav',
            **STR_ARG,
            'help': (
                'Path to mono 16 kHz WAV, e.g. voices/samples/zara_voss.wav'
            ),
        },
        {
            'name': '--language',
            **STR_ARG,
            'help': 'Language code (default: en)',
            'required': False,
            'default': 'en',
        },
        {
            'name': '--description',
            **STR_ARG,
            'help': 'Voice description',
            'required': False,
        },
        {
            'name': '--character-bio',
            **STR_ARG,
            'help': 'Character biography',
            'required': False,
        },
    ]
)
def cmd_register_voice(args):
    """Register a character voice with a Kokoro speaker WAV file."""
    from voice_registry import register_voice

    voice_data = {
        'name': args.name,
        'speaker_wav': args.speaker_wav,
        'language': getattr(args, 'language', None) or 'en',
        'description': getattr(args, 'description', None) or '',
        'character_bio': getattr(args, 'character_bio', None) or '',
    }

    result = register_voice(voice_data)
    if 'error' in result:
        print(f"\n❌ {result['error']}")
        return False
    print(f"\n✅ Voice registered: {result['name']}")
    print(f"   WAV:      {result['speaker_wav']}")
    print(f"   Language: {result['language']}")
    print(f"   ID:       {result['voice_registry_id']}")
    return True


@register_command(
    name="list-voices",
    help_text="List all registered voices (WAV paths + on-disk status)",
    arguments=[
        {
            'name': '--check-health',
            **BOOL_ARG,
            'help': 'Verify WAV files still exist',
        },
    ]
)
def cmd_list_voices(args):
    """List registered voices; optional health check."""
    from voice_registry import get_voice_registry

    registry = get_voice_registry()
    voices = registry.list_voices()

    if not voices:
        print("\nNo voices registered yet.")
        print(
            'Use: python main.py register-voice "CHARACTER NAME" '
            'voices/samples/name.wav'
        )
        return True

    print(f"\n{'─' * 60}")
    print(f"  {'NAME':<30} {'WAV FILE':<25} {'LANG'}")
    print(f"{'─' * 60}")

    for v in voices:
        wav = Path(v.get('speaker_wav', ''))
        exists = '✅' if wav.exists() else '❌'
        print(
            f"  {exists} {v['name']:<28} {wav.name:<25} "
            f"{v.get('language', 'en')}"
        )

    print(f"{'─' * 60}")
    print(f"  Total: {len(voices)} voices\n")

    if getattr(args, 'check_health', False):
        health = registry.check_all_voices_health()
        bad = [h for h in health.values() if h['status'] != 'healthy']
        if bad:
            print(f"⚠️  {len(bad)} voice(s) have missing or invalid WAV files.")
        else:
            print('✅ All WAV files present.')

    return True


@register_command(
    name="smoke-voice",
    help_text="Run a short Kokoro TTS test for a registered voice",
    arguments=[
        {
            'name': 'name',
            **STR_ARG,
            'help': 'Character name or voice registry ID',
        },
    ]
)
def cmd_smoke_voice(args):
    """Test a registered voice with a short Kokoro synthesis."""
    from voice_registry import get_voice_registry

    result = get_voice_registry().smoke_test_voice(args.name)
    if result.get('success'):
        print(f"\n✅ {result['message']}")
        print(f"   Listen: {result['output']}")
    else:
        print(f"\n❌ Smoke test failed: {result.get('error', 'unknown')}")
    return bool(result.get('success'))


@register_command(
    name="missing-voices",
    help_text=(
        "List episode characters that still need register-voice (WAV) setup"
    ),
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'Episode ID to check'},
    ]
)
def cmd_missing_voices(args):
    """Show characters that need WAV registration before audio generation."""
    from story_structure import get_story_structure
    from voice_registry import get_voice_registry

    ss = get_story_structure()
    episode = ss.get_episode(args.episode_id)
    if not episode:
        print(f"\n❌ Episode not found: {args.episode_id}")
        return False

    characters = episode.get('characters', [])
    if not characters:
        print(
            f"\n⚠️  No characters found. Run: "
            f'python main.py generate-characters {args.episode_id}'
        )
        return False

    registry = get_voice_registry()
    missing = registry.get_missing_voices(characters)
    registered = [c['name'] for c in characters if c['name'] not in missing]

    print(f"\n{'─' * 60}")
    print(
        f"  Voice status for episode: "
        f"{episode.get('title', args.episode_id)}"
    )
    print(f"{'─' * 60}")

    for name in registered:
        print(f"  ✅ {name}")

    for name in missing:
        slug = name.lower().replace(' ', '_')
        print(f"  ❌ {name}")
        print(f"       → Place WAV at: voices/samples/{slug}.wav")
        print(
            f'       → Then run:     python main.py register-voice '
            f'"{name}" voices/samples/{slug}.wav'
        )

    print(f"{'─' * 60}")
    print(f"  {len(registered)} ready  |  {len(missing)} missing\n")

    if missing:
        print('⚠️  Register all voices before generate-audio.')
        return False
    print('✅ All voices registered. Ready to generate audio.')
    return True

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
    name="reassemble-audio",
    help_text=(
        'Rebuild full_episode.mp3 from existing scene_audio.mp3 files and a '
        'fresh outro (no dialogue re-synthesis)'
    ),
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode'},
    ],
)
def cmd_reassemble_audio(args):
    """Stitch intro + scenes + outro without re-running Kokoro on lines."""
    from main import require_audio_stack
    if not require_audio_stack():
        return False
    from audio_pipeline import reassemble_episode_audio

    out = reassemble_episode_audio(args.episode_id)
    if out.get('error'):
        logger.error('%s', out['error'])
        return False
    logger.info('Reassemble OK → %s', out.get('full_episode_file'))
    return True


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
    from story_os.asyncio_compat import run_coro
    from story_structure import generate_scenes
    return run_coro(generate_scenes(args.episode_id))


@register_command(
    name="generate-script",
    help_text="Generate full script (uses agentic pipeline if USE_AGENTIC_PIPELINE)",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'ID of the episode'}
    ]
)
def cmd_generate_script(args):
    """Generate episode script.json from scenes."""
    from story_structure import generate_script
    result = generate_script(args.episode_id)
    return bool(result)


@register_command(
    name="init-story-os",
    help_text="Create series bible template and empty show state on disk",
    arguments=[
        {'name': '--series', **STR_ARG, 'help': 'Series display name', 'default': 'Main Series'}
    ]
)
def cmd_init_story_os(args):
    """Initialize Story OS files under data/series/<slug>/."""
    from story_os import io, models
    sid = io.series_slug(args.series)
    io.series_dir(sid)
    bible_path = io.series_dir(sid) / 'series_bible.json'
    if not bible_path.exists():
        bible = models.SeriesBible(
            series_id=sid,
            title=args.series,
            themes=[],
            tone_notes='',
            taboos=[],
            finale_notes='',
        )
        io.save_series_bible(bible)
    state = io.load_show_state(sid)
    if state is None:
        io.save_show_state(models.ShowState(series_id=sid), sid)
    logger.info('Story OS ready for series key %s', sid)
    return True


@register_command(
    name="plan-season",
    help_text="Write season_plan.json and episode_slots for a series",
    arguments=[
        {'name': '--series', **STR_ARG, 'help': 'Series display name', 'default': 'Main Series'},
        {'name': '--season', **STR_ARG, 'help': 'Season id', 'default': 's1'},
        {'name': '--episodes', **INT_ARG, 'help': 'Episode count', 'default': 10}
    ]
)
def cmd_plan_season(args):
    """Persist Save-the-Cat style beat mapping across the season."""
    from story_os import io
    from story_os.planner import plan_and_write
    sid = io.series_slug(args.series)
    plan_and_write(sid, args.season, int(args.episodes))
    return True


@register_command(
    name="ingest-series-bible",
    help_text="Chunk markdown/text from a folder into bible RAG store",
    arguments=[
        {'name': '--series', **STR_ARG, 'help': 'Series display name', 'default': 'Main Series'},
        {'name': 'folder', **DIR_ARG, 'help': 'Directory of .md/.txt bible files'}
    ]
)
def cmd_ingest_series_bible(args):
    """Ingest creator bible documents for USE_BIBLE_RAG."""
    from pathlib import Path
    from ingest_series_bible import ingest_cli
    if not Path(args.folder).is_dir():
        logger.error('Not a directory: %s', args.folder)
        return False
    ingest_cli(args.series, args.folder)
    return True


@register_command(
    name="promote-cast",
    help_text="Promote a guest character to permanent main cast in the series bible",
    arguments=[
        {'name': 'name', **STR_ARG, 'help': 'Character name (must match script)'},
        {'name': '--series', **STR_ARG, 'help': 'Series display name', 'default': 'Main Series'},
        {'name': '--species', **STR_ARG, 'help': 'Species', 'required': False},
        {'name': '--role', **STR_ARG, 'help': 'Ship/station role', 'required': False},
        {'name': '--personality', **STR_ARG, 'help': 'Personality summary', 'required': False},
        {'name': '--backstory', **STR_ARG, 'help': 'Backstory notes', 'required': False},
        {'name': '--voice-description', **STR_ARG, 'help': 'Voice casting notes', 'required': False},
    ]
)
def cmd_promote_cast(args):
    """Move a guest character into the permanent main_cast."""
    from story_os import io
    sid = io.series_slug(args.series)
    ok = io.promote_guest_to_main_cast(
        series_id=sid,
        name=args.name,
        species=getattr(args, 'species', None),
        role=getattr(args, 'role', None),
        personality=getattr(args, 'personality', None),
        backstory=getattr(args, 'backstory', None),
        voice_description=getattr(args, 'voice_description', None),
    )
    if ok:
        print(f'\n  Promoted "{args.name}" to permanent main cast.')
        print(f'  Updated: data/series/{sid}/series_bible.json')
    else:
        print(f'\n  Failed — series bible not found for "{sid}".')
    return ok


@register_command(
    name="new-show",
    help_text="Create a new podcast show from a concept prompt (Level 1)",
    arguments=[
        {
            'name': '--name',
            **STR_ARG,
            'help': 'Show name (e.g. "Prophets and Gamma")',
        },
        {
            'name': '--concept',
            **STR_ARG,
            'help': "Level 1 concept prompt — the show's premise",
        },
        {
            'name': '--auto-accept',
            **BOOL_ARG,
            'help': 'Skip interactive cast confirmation',
        },
    ]
)
def cmd_new_show(args):
    """Create a new show (Level 1 prompt -> series_bible.json)."""
    from show_os.new_show import ShowCreator
    try:
        creator = ShowCreator()
        result = creator.create_show(
            name=args.name,
            concept=args.concept,
            auto_accept=getattr(args, 'auto_accept', False),
        )
        print(f"\n  Show created: {result['name']}")
        print(f"   ID:          {result['show_id']}")
        print(f"   Bible:       {result['bible_path']}")
        print(f"   Show state:  {result['show_state_path']}")
        print('\nNext steps:')
        print(
            f'   1. Create a season:  python main.py new-season '
            f"--show {result['show_id']} --season 1 --arc \"...\"")
        print(
            '   2. Or skip and generate standalone episodes '
            'directly.')
        return True
    except Exception as e:
        print(f'\n  Show creation failed: {e}')
        return False


@register_command(
    name="new-season",
    help_text="Plan a season arc for an existing show (Level 2)",
    arguments=[
        {
            'name': '--show',
            **STR_ARG,
            'help': 'Show ID (slug from new-show output)',
        },
        {
            'name': '--season',
            **INT_ARG,
            'help': 'Season number (1, 2, 3...)',
        },
        {
            'name': '--arc',
            **STR_ARG,
            'help': 'Level 2 arc prompt',
        },
        {
            'name': '--episodes',
            **INT_ARG,
            'help': 'Number of episodes in the season',
            'default': 10,
        },
    ]
)
def cmd_new_season(args):
    """Plan a season arc (Level 2 prompt -> season_plan.json)."""
    from show_os.seasons import SeasonPlanner
    try:
        planner = SeasonPlanner()
        plan = planner.create_season(
            show_id=args.show,
            season_number=args.season,
            arc_prompt=args.arc,
            episode_count=args.episodes,
        )
        print(
            f"\n  Season {args.season} planned: "
            f"{plan['arc_title']}")
        print(f"   Episodes: {plan['episode_count']}")
        print('\nEpisode beats:')
        for beat in plan['episode_beats']:
            ep = beat['episode_number']
            imp = beat.get('arc_importance', '?')
            tens = beat.get('tension_level', '?')
            print(
                f"   Ep {ep} [{tens}/{imp}]: "
                f"{beat.get('arc_beat', '')[:70]}")
        return True
    except Exception as e:
        print(f'\n  Season planning failed: {e}')
        return False


@register_command(
    name="list-shows",
    help_text="List all created shows",
    arguments=[]
)
def cmd_list_shows(args):
    """List all shows in data/shows/."""
    from config.paths import SHOWS_DIR
    shows_dir = SHOWS_DIR
    if not shows_dir.exists():
        print(
            '\nNo shows created yet. Run: '
            'python main.py new-show --name ... --concept ...')
        return True

    shows = [d for d in shows_dir.iterdir() if d.is_dir()]
    if not shows:
        print('\nNo shows created yet.')
        return True

    print(f"\n{'=' * 64}")
    print(f"  {'SHOW ID':<25} {'NAME':<25} {'SEASON'}")
    print(f"{'=' * 64}")
    for show in sorted(shows, key=lambda s: s.name):
        state_path = show / 'show_state.json'
        if state_path.exists():
            with open(state_path, encoding='utf-8') as f:
                state = json.load(f)
            print(
                f"  {show.name:<25} "
                f"{state.get('name', '?'):<25} "
                f"{state.get('current_season', '-')}")
    print(f"{'=' * 64}\n")
    return True


@register_command(
    name="export-timeline",
    help_text="Export rough word-clock timeline JSON for an episode",
    arguments=[
        {'name': 'episode_id', **STR_ARG, 'help': 'Episode id'}
    ]
)
def cmd_export_timeline(args):
    """Write episodes/<id>/exports/timeline.json."""
    from export_timeline import export_episode_timeline
    export_episode_timeline(args.episode_id)
    return True

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