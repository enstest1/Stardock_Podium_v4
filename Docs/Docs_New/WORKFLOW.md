# TTS Workflow Documentation

## Overview
This document outlines the complete workflow for using the Text-to-Speech (TTS) system in our project. The system uses Coqui TTS as the primary engine with ElevenLabs as a fallback option.

## Voice Setup Process

### 1. Voice Sample Recording
1. Record voice samples for each character:
   - Duration: 5-10 seconds of clear speech
   - Format: WAV file, mono channel
   - Sample rate: 16kHz
   - Location: `voices/samples/`
   - Naming: `character_name.wav`

### 2. Voice Configuration
1. Create/update voice configuration in `voices/voice_config.json`:
   (see PROJECTSTRUCUTRE.md for details)

### 3. API Configuration
1. ElevenLabs API (Fallback):
   - Create account at elevenlabs.io
   - Get API key from dashboard
   - Add to `.env`:
     ```
     ELEVENLABS_API_KEY=your_key_here
     ```
   - Configure voice IDs in `voice_config.json`
2. Coqui TTS (Primary):
   - No API key required
   - Uses local model: "tts_models/multilingual/multi-dataset/your_tts"
   - Requires torch==2.2.0+cpu

### 4. Validation
1. Run voice validation:
   ```bash
   python cli/validate_voices.py --config voices/voice_config.json
   ```
2. Check for any validation errors and fix them

## Script Preparation (NEW FORMAT)

### 1. Script Format
Podcast episode scripts must use the following JSON structure for each scene:
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

### 2. Script Placement
- Place scripts in `episodes/<episode_id>/script.json`

### 3. Validation
- Use the CLI validation tool to check script and voice configuration before generating audio.

## Audio Generation Process

### 1. Generate Audio for a Script
```bash
python cli/generate_voices.py --script path/to/your_script.json --output output_dir/
```
- The `--script` argument should point to your episode script in the new format.
- The `--output` argument specifies the directory for generated audio files.

### 2. Quality Control
1. Review generated audio files
2. Check for any issues:
   - Audio quality
   - Voice consistency
   - Timing and pacing
3. Regenerate if necessary

## Troubleshooting

### Common Issues
1. Voice Sample Issues:
   - Wrong format: Convert to WAV, mono, 16kHz
   - Poor quality: Re-record with better conditions
   - Wrong duration: Keep between 5-10 seconds
2. Generation Issues:
   - Coqui TTS fails: System will automatically fall back to ElevenLabs
   - ElevenLabs fails: Check API key and internet connection

### Fallback Process
1. If Coqui TTS fails:
   - System automatically switches to ElevenLabs
   - Uses configured fallback voice ID
   - Logs the failure for review

## Best Practices

### Script Writing
- Use the new line-based format for all scenes
- Use clear, concise descriptions and dialogue
- Place sound effects and narration as separate lines
- End each scene with a description line: `{ "type": "description", "content": "END SCENE" }`
- Validate script structure before audio generation

### Voice Recording
- Use a quiet environment
- Maintain consistent distance from microphone
- Speak clearly and naturally
- Avoid background noise

### Configuration
- Keep voice configurations organized
- Document any special requirements
- Regular validation of configurations

### Maintenance
- Regular testing of voice samples
- Update configurations as needed
- Monitor system performance
- Keep dependencies updated

### API Usage
- Monitor ElevenLabs API usage
- Implement proper error handling
- Use appropriate fallback settings
- Regular API key rotation
