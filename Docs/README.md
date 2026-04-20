# Stardock Podium

An AI-powered Star Trek podcast generator that creates original episodes in the style of classic Star Trek series.

## Overview

Stardock Podium ingests sci-fi reference materials and generates complete, Star Trek-style podcast episodes with consistent characters, continuity, and professional voice acting. The system uses advanced AI technologies to create original content that maintains the spirit and style of Star Trek while telling new stories.

## Features

- **Reference Ingestion**: Process EPUB sci-fi books to understand writing styles, character archetypes, and thematic elements
- **Vector Memory**: Store and retrieve reference materials using Mem0 vector database
- **Save-the-Cat Story Structure**: Generate well-structured episodes following proven storytelling beats
- **Character Continuity**: Maintain consistent characters across episodes with memory of prior developments
- **Voice Synthesis**: Local **Kokoro** TTS with `voices/samples/` reference WAVs
- **Audio Production**: Complete audio pipeline with music, sound effects, and post-processing
- **Quality Checking**: Automated script and audio quality verification
- **Windows 10 Native**: Designed to run natively on Windows 10 without Docker or WSL

## Installation

### Prerequisites

- Windows 10
- Python 3.8+
- FFmpeg (added to PATH)
- API keys for:
  - OpenAI or OpenRouter
  - Mem0 (optional for local Mem0 config)
  - ElevenLabs (optional; legacy voice-registry features only)

### Setup

1. Clone this repository:
   ```
   git clone https://github.com/your-username/stardock-podium.git
   cd stardock-podium
   ```

2. Install required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```
   set OPENAI_API_KEY=your_openai_key
   set OPENROUTER_API_KEY=your_openrouter_key
   set ELEVENLABS_API_KEY=your_elevenlabs_key
   set MEM0_API_KEY=your_mem0_key
   ```
   
   For permanent setup, add these to your Windows environment variables.

## Usage

### Quick Start

1. Ingest a reference book:
   ```
   python main.py ingest path/to/scifi_book.epub --analyze
   ```

2. Sync the book to vector memory:
   ```
   python main.py sync-memory --all
   ```

3. Register character voices:
   ```
   python main.py register-voice "Captain Kirk" elevenlabs_voice_id --description "Commanding, charismatic"
   ```

4. Generate an episode:
   ```
   python main.py generate-episode --title "The Quantum Paradox" --theme "time travel" --duration 30
   ```

5. Generate audio for the episode:
   ```
   python main.py generate-audio episode_id
   ```

### Available Commands

- `ingest`: Process an EPUB file and extract content
- `analyze`: Analyze writing style and themes of ingested books
- `sync-memory`: Synchronize reference materials with vector memory
- `generate-episode`: Create a new podcast episode script
- `edit-script`: Edit an episode script
- `regenerate-scene`: Regenerate a specific scene in an episode
- `register-voice`: Add a new voice to the voice registry
- `list-voices`: Show all registered voices
- `generate-audio`: Create audio for an episode
- `check-quality`: Verify the quality of an episode's script and/or audio
- `list-episodes`: Display all generated episodes with filters

Run `python main.py --help` to see all available commands and options.

## Project Structure

- `main.py`: Main entry point and environment initialization
- `cli_entrypoint.py`: Command-line interface for all functionality
- `mem0_client.py`: Interface to Mem0 vector database
- `epub_processor.py`: EPUB file processing and content extraction
- `book_style_analysis.py`: Analysis of writing styles and themes
- `reference_memory_sync.py`: Sync reference materials to vector memory
- `story_structure.py`: Episode generation using Save-the-Cat structure
- `episode_memory.py`: Management of episode continuity and character development
- `voice_registry.py`: Voice management for characters
- `episode_metadata.py`: Episode tagging and organization
- `script_editor.py`: Script editing and scene regeneration
- `audio_pipeline.py`: Audio generation and assembly
- `quality_checker.py`: Script and audio quality verification

## Configuration

The system creates several directories for storing data:
- `books/`: Ingested reference materials
- `analysis/`: Style analysis results
- `episodes/`: Generated episode data
- `audio/`: Generated audio files
- `voices/`: Voice registry data
- `temp/`: Temporary files
- `data/`: Application data
- `logs/`: Log files

## Development

### Running Tests

```
python -m unittest discover -s tests
```

### Adding New Features

1. Extend the appropriate module based on the feature type
2. Register new commands in `cli_entrypoint.py` if needed
3. Update documentation

## Acknowledgments

- ElevenLabs for voice synthesis technology
- OpenAI and OpenRouter for text generation capabilities
- Mem0 for vector database functionality
- FFmpeg for audio processing

## License

This project is licensed under the MIT License - see the LICENSE file for details.