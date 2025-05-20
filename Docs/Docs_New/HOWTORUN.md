# How to Run the TTS System

## Prerequisites

### System Requirements
- Python 3.11 or higher
- FFmpeg installed and in system PATH
- Sufficient disk space for audio files
- Internet connection for ElevenLabs fallback

### Python Dependencies
Install required packages:
```bash
pip install torch==2.2.0+cpu -f https://download.pytorch.org/whl/torch_stable.html TTS==0.22.0 soundfile==0.12.1
pip install -r requirements.txt
```

## Quick Start

### 1. Initial Setup
1. Create necessary directories:
   ```bash
   mkdir -p voices/samples assets/sound_effects assets/music assets/ambience
   ```

2. Create `.env` file:
   ```
   ELEVENLABS_API_KEY=your_key_here
   ```

### 2. Script Preparation (NEW FORMAT)
Podcast episode scripts must now use the following JSON structure for each scene:
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

### 3. Validate Voice Setup
```bash
python cli/validate_voices.py --config voices/voice_config.json
```

### 4. Generate Audio
```bash
python cli/generate_voices.py --script path/to/your_script.json --output output_dir/
```
- The `--script` argument should point to your episode script in the new format.
- The `--output` argument specifies the directory for generated audio files.

## Common Tasks

### 1. Recording Voice Samples
- Place WAV files in `voices/samples/`
- Naming convention: `character_name.wav`
- Format: WAV, mono, 16kHz, 5-10 seconds

### 2. Updating Voice Configuration
- Edit `voices/voice_config.json`

### 3. Testing Voices
```bash
python cli/generate_voices.py --text "This is a test." --voice narrator --output test.wav
```

## Troubleshooting

### Quick Fixes
1. Missing Dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. FFmpeg Issues:
   - Verify FFmpeg installation
   - Check system PATH
3. API Key Issues:
   - Verify ElevenLabs API key in `.env`
   - Check internet connection

### Common Errors
- "Voice sample not found": Check file path and format
- "Invalid configuration": Verify JSON structure
- "API key missing": Check `.env` file

For detailed troubleshooting, see `TROUBLESHOOTING.md`

## Maintenance

### Regular Tasks
1. Update dependencies:
   ```bash
   pip install --upgrade -r requirements.txt
   ```
2. Clean up old audio files:
   ```bash
   rm -rf output/*  # Be careful with this command
   ```
3. Validate configurations:
   ```bash
   python cli/validate_voices.py --config voices/voice_config.json
   ```

### Backup
1. Regularly backup:
   - Voice samples
   - Configuration files
   - Generated audio

## Additional Resources
- `WORKFLOW.md`: Detailed TTS workflow and configuration
- `TROUBLESHOOTING.md`: Comprehensive troubleshooting guide
- `API_INTEGRATION.md`: API setup and management
- `PROJECTSTRUCUTRE.md`: Project organization and file structure
