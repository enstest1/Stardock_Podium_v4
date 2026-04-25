#!/usr/bin/env python
"""
Stardock Podium - AI Star Trek Podcast Generator

This module serves as the main entry point for the Stardock Podium system. It performs
environment checks, initializes all required components, and launches the CLI interface.

The system is designed to run natively on Windows 10 without requiring Docker or WSL,
while providing a complete pipeline for generating Star Trek-style podcast episodes
from reference materials.
"""

from dotenv import load_dotenv
load_dotenv()

import os
import sys
import platform
import logging
import importlib.util
import subprocess
from pathlib import Path

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

# Required modules — split so non‑audio commands (list-voices, missing-voices,
# init-story-os, ingest) can run even on a machine without ffmpeg/torch/kokoro
# installed. Audio commands lazy‑check via ``require_audio_stack()`` below.
REQUIRED_CORE = [
    ('mem0', 'Mem0 Vector Database Client'),
    ('ebooklib', 'EPUB Processing Library'),
    ('openai', 'OpenAI API Client'),
    ('nltk', 'Natural Language Toolkit'),
]

OPTIONAL_AUDIO = [
    ('ffmpeg', 'FFmpeg Python Bindings'),
    ('torch', 'PyTorch (for GPU acceleration)'),
    ('kokoro', 'Kokoro TTS (dialogue synthesis)'),
]

# Back‑compat export — some external tooling imported REQUIRED_MODULES.
REQUIRED_MODULES = REQUIRED_CORE + OPTIONAL_AUDIO
# ElevenLabs removed — Kokoro is now the sole TTS engine


def require_audio_stack() -> bool:
    """Hard‑check the audio dependencies at the point they are actually used.

    Call from the entry of any CLI handler that invokes Kokoro / ffmpeg
    (``generate-audio``, ``register-voice``, ``smoke-voice``, …).

    Returns:
        True if every audio dep is importable and FFmpeg is on PATH.
        False if any is missing (after logging a human‑readable error).
    """
    missing: list[str] = []
    for module_name, module_desc in OPTIONAL_AUDIO:
        if importlib.util.find_spec(module_name) is None:
            missing.append(f"{module_name} ({module_desc})")

    try:
        result = subprocess.run(
            ['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode != 0:
            missing.append('ffmpeg binary (on PATH, not working)')
    except FileNotFoundError:
        missing.append('ffmpeg binary (not on PATH)')

    if missing:
        logger.error(
            "Audio command requires the following (missing): %s",
            ', '.join(missing))
        logger.error(
            "Install instructions: see README — section 'PyTorch: GPU wheel' "
            "for torch, `pip install kokoro-tts ffmpeg-python` for the rest, "
            "and https://ffmpeg.org/download.html for the FFmpeg binary.")
        return False
    return True

def check_environment():
    """
    Check if the environment is suitable for running the application.
    Returns True if all checks pass, False otherwise.
    """
    checks_passed = True
    
    # Check platform
    logger.info(f"Detected platform: {platform.system()} {platform.release()}")
    if platform.system() != "Windows":
        logger.warning("This application is optimized for Windows 10. Some features may not work as expected.")
    
    # Check Python version
    python_version = sys.version_info
    logger.info(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        logger.error("Python 3.8+ is required to run this application.")
        checks_passed = False
    
    # Core modules — hard fail if missing (nothing works without these).
    for module_name, module_desc in REQUIRED_CORE:
        if importlib.util.find_spec(module_name) is None:
            logger.error(
                f"Required module not found: {module_name} ({module_desc})")
            checks_passed = False
        else:
            logger.info(f"Module found: {module_name}")

    # Audio stack — warn only. ``require_audio_stack()`` enforces at the
    # point of use so you can still run list-voices / missing-voices / ingest
    # on a machine that doesn't have Kokoro, torch, or FFmpeg installed.
    missing_audio: list[str] = []
    for module_name, module_desc in OPTIONAL_AUDIO:
        if importlib.util.find_spec(module_name) is None:
            missing_audio.append(f"{module_name} ({module_desc})")
        else:
            logger.info(f"Module found: {module_name}")

    # FFmpeg binary — warn‑only here, enforced in require_audio_stack().
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            ffmpeg_version = result.stdout.split('\n')[0]
            logger.info(f"FFmpeg found: {ffmpeg_version}")
        else:
            missing_audio.append('ffmpeg binary (not working on PATH)')
    except FileNotFoundError:
        missing_audio.append('ffmpeg binary (not on PATH)')

    if missing_audio:
        logger.warning(
            "Audio stack incomplete (non‑audio commands will still work): %s",
            ', '.join(missing_audio))
    
    # Check for API keys in environment variables
    api_keys = {
        'OPENAI_API_KEY': 'OpenAI API',
        'OPENROUTER_API_KEY': 'OpenRouter API',
        'MEM0_API_KEY': 'Mem0 API',
    }
    
    for env_var, service_name in api_keys.items():
        if not os.getenv(env_var):
            logger.warning(f"Environment variable {env_var} for {service_name} not found.")
    
    return checks_passed

def create_default_directories():
    """Create all necessary directories using the centralized path config.

    User-data dirs (books, voices, episodes, audio, data/*, analysis, temp)
    are created via ``config.paths.ensure_all_dirs()`` which honors
    ``STARDOCK_*_DIR`` env overrides for cloud deployments.
    Logs stay local/ephemeral per pod.
    """
    from config.paths import ensure_all_dirs
    ensure_all_dirs()
    Path("logs").mkdir(exist_ok=True)
    logger.debug("Default directories ensured via config.paths")

def check_nltk_data():
    """Ensure required NLTK data is downloaded."""
    try:
        import nltk
        required_packages = ['punkt', 'averaged_perceptron_tagger', 'maxent_ne_chunker', 'words']
        
        for package in required_packages:
            try:
                nltk.data.find(f'tokenizers/{package}')
                logger.debug(f"NLTK package found: {package}")
            except LookupError:
                logger.info(f"Downloading NLTK package: {package}")
                nltk.download(package, quiet=True)
    except ImportError:
        logger.error("NLTK not installed. Skipping NLTK data check.")

def display_welcome_message():
    """Display the welcome message with proper encoding."""
    # Set console encoding to UTF-8
    import sys
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
    
    welcome_text = """
    ╔════════════════════════════════════════════════════════════════════════════╗
    ║                                                                            ║
    ║  ███████╗████████╗ █████╗ ██████╗ ██████╗  ██████╗  ██████╗ ██╗          ║
    ║  ██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔═══██╗██╔═══██╗██║          ║
    ║  ███████╗   ██║   ███████║██║  ██║██║  ██║██║   ██║██║   ██║██║          ║
    ║  ╚════██║   ██║   ██╔══██║██║  ██║██║  ██║██║   ██║██║   ██║██║          ║
    ║  ███████║   ██║   ██║  ██║██████╔╝██████╔╝╚██████╔╝╚██████╔╝███████╗     ║
    ║  ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝     ║
    ║                                                                            ║
    ║  ██████╗  ██████╗ ██████╗ ██╗██╗   ██╗███╗   ███╗                        ║
    ║  ██╔══██╗██╔═══██╗██╔══██╗██║██║   ██║████╗ ████║                        ║
    ║  ██████╔╝██║   ██║██║  ██║██║██║   ██║██╔████╔██║                        ║
    ║  ██╔═══╝ ██║   ██║██║  ██║██║██║   ██║██║╚██╔╝██║                        ║
    ║  ██║     ╚██████╔╝██████╔╝██║╚██████╔╝██║ ╚═╝ ██║                        ║
    ║  ╚═╝      ╚═════╝ ╚═════╝ ╚═╝ ╚═════╝ ╚═╝     ╚═╝                        ║
    ║                                                                            ║
    ║  Welcome to Stardock Podium - Your AI-Powered Star Trek Podcast Generator   ║
    ║                                                                            ║
    ╚════════════════════════════════════════════════════════════════════════════╝
    """
    print(welcome_text)

def init_modules():
    """Initialize required modules and verify they're working."""
    try:
        # Import and initialize modules
        from mem0_client import get_mem0_client
        from epub_processor import EPUBProcessor
        from voice_registry import VoiceRegistry

        # Mem0 (or no-op stub if OPENAI / Mem0 unavailable — see get_mem0_client)
        get_mem0_client()
        
        # Initialize voice registry
        voice_registry = VoiceRegistry()
        voice_count = len(voice_registry.list_voices())
        logger.info(f"Voice registry initialized with {voice_count} voices")
        
        return True
    except Exception as e:
        logger.exception(f"Error initializing modules: {e}")
        return False

def _run_full_ingest(force: bool = False) -> int:
    """
    Full ingest pipeline:
      1. Sync all EPUBs from books/ to Mem0
      2. Extract series bible + style profile
      3. Reload KnowledgeContext

    Usage:
        python main.py ingest
        python main.py ingest --force
    """
    logger.info("=" * 60)
    logger.info("FULL INGEST PIPELINE STARTING")
    logger.info("Force mode: %s", force)
    logger.info("=" * 60)

    # Step 0.5: Process any raw EPUBs that haven't been processed yet
    logger.info("Step 0/3 — Processing raw EPUBs in books/...")
    try:
        from epub_processor import get_processor, list_books
        from config.paths import BOOKS_DIR
        processor = get_processor()
        books_dir = BOOKS_DIR
        epub_files = list(books_dir.glob('*.epub'))
        if epub_files:
            already_processed = {
                b.get('file_path', '')
                for b in list_books()
            }
            new_epubs = [
                f for f in epub_files
                if str(f) not in already_processed
            ]
            if new_epubs or force:
                targets = epub_files if force else new_epubs
                for epub_path in targets:
                    logger.info('Processing EPUB: %s', epub_path.name)
                    result = processor.process_epub(str(epub_path))
                    if result:
                        logger.info(
                            '  -> %s (%s chapters, %s sections)',
                            result.get('title', '?'),
                            result.get('num_chapters', 0),
                            result.get('num_sections', 0),
                        )
                    else:
                        logger.warning(
                            '  -> Failed to process %s',
                            epub_path.name)
            else:
                logger.info('All EPUBs already processed.')
        else:
            logger.info('No EPUB files in books/ — skipping.')
    except Exception as e:
        logger.error("EPUB processing failed: %s", e)
        return 1

    # Step 1: Sync books
    logger.info("Step 1/3 — Syncing books to Mem0...")
    try:
        from reference_memory_sync import sync_references
        sync_result = sync_references(force=force)
        synced = sync_result.get("summary", {}).get(
            "total_sections_synced", 0)
        logger.info("Step 1 complete: %s sections synced", synced)
    except Exception as e:
        logger.error("Step 1 failed: %s", e)
        return 1

    # Step 2: Extract series bible
    logger.info("Step 2/3 — Extracting series bible and style profile...")
    try:
        from book_knowledge import SeriesBibleExtractor
        extractor = SeriesBibleExtractor()
        extraction = extractor.extract_from_all_books(force=force)
        if extraction.get("series_bible"):
            logger.info("Step 2 complete: series bible extracted")
        else:
            logger.warning("Step 2: extraction empty — check Mem0 sync")
    except Exception as e:
        logger.error("Step 2 failed: %s", e)
        return 1

    # Step 3: Reload knowledge context
    logger.info("Step 3/3 — Reloading knowledge context...")
    try:
        from book_knowledge import reload_knowledge_context
        ctx = reload_knowledge_context()
        if ctx.is_ready():
            logger.info("Step 3 complete: knowledge context ready")
        else:
            logger.warning(
                "Step 3: context loaded but bible or style is empty")
    except Exception as e:
        logger.error("Step 3 failed: %s", e)
        return 1

    logger.info("=" * 60)
    logger.info("INGEST COMPLETE")
    try:
        from config.paths import SERIES_DIR
        logger.info("  Series bible: %s", SERIES_DIR / "series_bible.json")
        logger.info("  Style profile: %s", SERIES_DIR / "style_profile.json")
    except Exception:
        logger.info("  Series bible: data/series/series_bible.json")
        logger.info("  Style profile: data/series/style_profile.json")
    logger.info("  Next episode generation will use this knowledge.")
    logger.info("=" * 60)
    return 0


def main():
    """Main entry point for the application."""
    # Display welcome message
    display_welcome_message()

    # Check environment
    logger.info("Checking environment...")
    if not check_environment():
        logger.error("Environment check failed. Please fix the issues and try again.")
        return 1

    # Create directories
    logger.info("Creating necessary directories...")
    create_default_directories()

    # Check NLTK data
    logger.info("Checking NLTK data...")
    check_nltk_data()

    # Ingest shortcut — run BEFORE init_modules() so a clean repo (no Kokoro
    # weights yet, no voices registered) can still ingest books without
    # getting tripped up by voice‑registry initialisation.
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        return _run_full_ingest(force="--force" in sys.argv)

    # Initialize modules
    logger.info("Initializing modules...")
    if not init_modules():
        logger.warning("Some modules failed to initialize. Functionality may be limited.")

    # Import CLI entrypoint and run it
    try:
        from cli_entrypoint import main as cli_main
        logger.info("Starting CLI...")
        return cli_main()
    except Exception as e:
        logger.exception(f"Error executing CLI: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())