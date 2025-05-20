# Kokoro TTS Integration

This document outlines the integration of Kokoro TTS as the primary text-to-speech engine in Stardock Podium, with ElevenLabs as a fallback option.

## Overview

Kokoro TTS is an open-source text-to-speech engine that provides high-quality voice synthesis with speaker adaptation capabilities. It is now the primary TTS engine in Stardock Podium, replacing the previous Coqui TTS implementation.

## Dependencies

The following dependencies are required for Kokoro TTS:

```txt
torch==2.2.0+cpu -f https://download.pytorch.org/whl/torch_stable.html
git+https://github.com/hexgrad/Kokoro-TTS.git@main
librosa==0.10.2
soundfile==0.12.1
```

## Voice Configuration

Voice configurations are stored in `voices/voice_config.json` with the following structure:

```json
{
  "engine_order": ["kokoro", "eleven"],
  "characters": {
    "Character Name": {
      "speaker_wav": "voices/samples/character_name.wav",
      "language": "en",
      "eleven_id": "elevenlabs-voice-id"
    }
  }
}
```

### Configuration Fields

- `engine_order`: List of TTS engines to try in order
- `characters`: Map of character names to their voice configurations
  - `speaker_wav`: Path to reference audio file (5-10 seconds, 16kHz mono WAV)
  - `language`: Language code (default: "en")
  - `eleven_id`: ElevenLabs voice ID for fallback

## Voice Samples

Voice samples should be:
- 5-10 seconds of clear speech
- 16kHz mono WAV format
- Stored in `voices/samples/` directory
- Named according to character name (e.g., `character_name.wav`)

## Migration

To migrate from the old voice registry:

1. Run the migration script:
   ```bash
   python tools/migrate_registry.py
   ```

2. Follow the TODO list to:
   - Record voice samples for each character
   - Save samples in the correct format
   - Update the voice configuration

3. Validate your setup:
   ```bash
   python cli/validate_voices.py
   ```

## Usage

The TTS engine can be used in two ways:

1. Through the CLI:
   ```bash
   python cli/generate_voices.py --script path/to/script.json
   ```

2. Programmatically:
   ```python
   from tts_engine import get_kokoro_engine
   
   engine = get_kokoro_engine()
   engine.synth("Text to synthesize", "output.wav", speaker_wav="reference.wav")
   ```

## Troubleshooting

Common issues and solutions:

1. **Audio Quality Issues**
   - Ensure voice samples are clear and free of background noise
   - Check that samples are in the correct format (16kHz mono WAV)
   - Verify sample duration is between 5-10 seconds

2. **Engine Initialization Failures**
   - Verify all dependencies are installed correctly
   - Check PyTorch installation (CPU version recommended)
   - Ensure sufficient system resources are available

3. **Fallback to ElevenLabs**
   - Check ElevenLabs API key is set in `.env`
   - Verify voice IDs in configuration
   - Check network connectivity

## Performance Considerations

- Kokoro TTS requires more system resources than Coqui TTS
- CPU-only PyTorch is recommended for most systems
- Voice generation may take longer than with previous engines
- Consider batch processing for large scripts

## Future Improvements

Planned enhancements:
- Support for more languages
- Improved voice quality
- Better error handling and recovery
- Caching of generated audio
- Batch processing optimizations 