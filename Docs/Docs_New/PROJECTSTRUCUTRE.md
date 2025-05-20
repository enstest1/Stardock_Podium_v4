# Project Structure

## Directory Layout

```
stardock_podium_04/
├── assets/
│   ├── sound_effects/    # Sound effect audio files
│   ├── music/           # Background music tracks
│   └── ambience/        # Ambient sound effects
│
├── cli/
│   ├── generate_voices.py    # Main script for generating audio
│   └── validate_voices.py    # Voice configuration validator
│
├── voices/
│   ├── samples/             # Voice reference WAV files
│   └── voice_config.json    # Voice configuration file
│
├── episodes/
│   └── <episode_id>/        # Each podcast episode's data, including script.json
│       └── script.json      # Podcast script in new format (see below)
│
├── tools/
│   └── migrate_registry.py  # Tool for migrating old voice registry
│
├── Docs/
│   ├── Docs_New/
│   │   ├── WORKFLOW.md         # Workflow documentation
│   │   ├── HOWTORUN.md         # Setup and usage guide
│   │   └── PROJECTSTRUCUTRE.md # This file
│   └── COQUIHOWTO.md          # Coqui TTS specific guide
│
├── .env                     # Environment variables
├── requirements.txt         # Python dependencies
└── README.md               # Project overview
```

## Key Components

### 1. CLI Tools
- `generate_voices.py`: Main script for generating audio from scripts
- `validate_voices.py`: Validates voice configurations and samples

### 2. Voice Management
- `voices/samples/`: Directory for voice reference files
- `voices/voice_config.json`: Configuration for voice settings

### 3. Asset Management
- `assets/sound_effects/`: Sound effect files
- `assets/music/`: Background music tracks
- `assets/ambience/`: Ambient sound effects

### 4. Podcast Episode Scripts (NEW FORMAT)
- Location: `episodes/<episode_id>/script.json`
- Format: JSON
- Structure:
  ```json
  {
    "title": "Episode Title",
    "episode_id": "ep_xxxxxxxx",
    "scenes": [
      {
        "scene_id": "scene_xxxxxxxx",
        "scene_number": 1,
        "beat": "Opening Image",
        "setting": "Bridge of the USS Example",
        "lines": [
          {"type": "description", "content": "Scene description here."},
          {"type": "sound_effect", "content": "Sound effect description."},
          {"type": "narration", "content": "Narration text."},
          {"type": "dialogue", "speaker": "CHARACTER NAME", "content": "Spoken line."},
          {"type": "description", "content": "END SCENE"}
        ]
      }
    ]
  }
  ```
- Each scene's `lines` array must use objects with a `type` field (`description`, `sound_effect`, `narration`, `dialogue`) and a `content` field. Dialogue lines must also include a `speaker` field.
- This format is required for all future podcast episodes.

### 5. Documentation
- `Docs/Docs_New/`: Main documentation directory
- `Docs/COQUIHOWTO.md`: Coqui TTS specific instructions

## File Formats

### Voice Samples
- Format: WAV
- Channels: Mono
- Sample Rate: 16kHz
- Duration: 5-10 seconds
- Location: `voices/samples/`

### Configuration Files
- Format: JSON
- Location: `voices/voice_config.json`
- Structure:
  ```json
  {
    "engine_order": ["coqui", "elevenlabs"],
    "characters": {
      "character_name": {
        "speaker_wav": "voices/samples/character_name.wav",
        "language": "en",
        "fallback_voice_id": "elevenlabs_voice_id"
      }
    }
  }
  ```

### Script Files (NEW FORMAT)
- Format: JSON
- Location: `episodes/<episode_id>/script.json`
- Structure: See above

## Dependencies

### Python Packages
- TTS==0.22.0
- torch==2.2.0+cpu
- soundfile==0.12.1
- Additional dependencies in requirements.txt

### System Requirements
- FFmpeg
- Python 3.11+
- Sufficient disk space

## Environment Variables
- `ELEVENLABS_API_KEY`: API key for ElevenLabs fallback

## Best Practices

### File Organization
1. Keep voice samples organized by character
2. Maintain consistent naming conventions
3. Regular cleanup of temporary files

### Configuration Management
1. Version control for configuration files
2. Regular backups of voice samples
3. Document any special configurations

### Documentation
1. Keep documentation up to date
2. Document any changes to structure
3. Maintain clear naming conventions
