# Coqui TTS Setup and Usage Guide

This guide will walk you through setting up and using Coqui TTS for voice generation in your podcast episodes. We'll cover everything from installation to recording reference audio.

## 0. Project Structure

Before starting, understand our project's directory structure:
```
stardock_podium_04/
├── episodes/           # Episode scripts and audio
│   └── your_episode/   # Each episode has its own directory
│       ├── script.json
│       └── audio/      # Generated audio files
├── voices/            # Voice configuration and samples
│   ├── samples/       # Speaker reference WAV files
│   └── voice_config.json
├── assets/            # Audio assets
│   ├── sound_effects/
│   ├── music/
│   └── ambience/
└── .env               # Environment variables
```

## 1. Installation

1. **Set Up Environment Variables**
   - Create or edit `.env` file in the project root:
   ```env
   ELEVENLABS_API_KEY=your_key_here  # Required for fallback
   ```
   - The ElevenLabs API key is required even if using Coqui TTS as primary, as it serves as fallback

2. **Install Python Dependencies**
   ```bash
   pip install torch==2.2.0+cpu -f https://download.pytorch.org/whl/torch_stable.html
   pip install TTS==0.21.4
   pip install soundfile==0.12.1
   ```

3. **Verify Installation**
   ```bash
   python -c "from TTS.api import TTS; print('Coqui TTS installed successfully!')"
   ```

## 2. Setting Up Voice Samples

1. **Create Sample Directory**
   ```bash
   mkdir -p voices/samples
   ```

2. **Record Reference Audio**
   - For each character, you need a reference audio file:
     - Use a good quality microphone
     - Record in a quiet room
     - Speak clearly and naturally
     - Keep it between 5-10 seconds
     - Save as mono WAV at 16kHz

3. **Audio File Requirements**
   - Format: WAV
   - Channels: Mono (1 channel)
   - Sample Rate: 16kHz
   - Duration: 5-10 seconds
   - File Name: `character_name.wav` (e.g., `aria_tvel.wav`)

4. **Convert Existing Audio (if needed)**
   ```bash
   ffmpeg -i input.wav -ac 1 -ar 16000 -y output.wav
   ```

## 3. Voice Configuration

1. **Create Voice Config**
   - Create `voices/voice_config.json` in the project's voices directory:
   ```json
   {
     "engine_order": ["coqui", "eleven"],
     "characters": {
       "Aria T'Vel": {
         "speaker_wav": "voices/samples/aria_tvel.wav",
         "language": "en",
         "eleven_id": "your_elevenlabs_id"
       }
     }
   }
   ```
   - Note: The `eleven_id` is required for fallback to ElevenLabs
   - All paths should be relative to the project root

2. **Add Each Character**
   - For each character in your script:
     - Add their name as a key
     - Set the path to their WAV file
     - Set their language (usually "en")
     - Keep their ElevenLabs ID for fallback

## 4. Testing Your Setup

1. **Validate Configuration**
   ```bash
   python cli/validate_voices.py --script episodes/your_episode/script.json --config voices/voice_config.json
   ```

2. **Test Single Voice**
   ```bash
   python -c "
   from tts_engine import get_coqui_engine
   engine = get_coqui_engine()
   engine.synth(
       text='This is a test of the Coqui TTS system.',
       speaker_wav='voices/samples/aria_tvel.wav',
       language='en',
       output_path='test_output.wav'
   )
   "
   ```

## 5. Generating Episode Audio

1. **Basic Generation**
   ```bash
   python cli/generate_voices.py \
       --script episodes/your_episode/script.json \
       --config voices/voice_config.json \
       --outdir episodes/your_episode/audio
   ```

2. **Dry Run (Check Only)**
   ```bash
   python cli/generate_voices.py \
       --script episodes/your_episode/script.json \
       --config voices/voice_config.json \
       --outdir episodes/your_episode/audio \
       --dry-run
   ```

## 6. Troubleshooting

1. **Common Issues**
   - **Error: "ELEVENLABS_API_KEY not found"**
     - Check your `.env` file exists in the project root
     - Verify the API key is set correctly
     - Restart your terminal after setting the key

   - **Error: "Speaker WAV not found"**
     - Check the path in voice_config.json
     - Make sure the file exists in voices/samples/
     - Verify the filename matches exactly

   - **Error: "Speaker WAV must be mono"**
     - Convert your audio to mono:
     ```bash
     ffmpeg -i input.wav -ac 1 -y output.wav
     ```

   - **Error: "Speaker WAV must be 16kHz"**
     - Convert your audio to 16kHz:
     ```bash
     ffmpeg -i input.wav -ar 16000 -y output.wav
     ```

   - **Error: "Speaker WAV must be ≤10s"**
     - Trim your audio to 10 seconds or less:
     ```bash
     ffmpeg -i input.wav -t 10 -y output.wav
     ```

2. **Quality Tips**
   - Record in a quiet environment
   - Use a good quality microphone
   - Speak clearly and naturally
   - Keep background noise to a minimum
   - Avoid audio effects or processing

## 7. Best Practices

1. **Directory Organization**
   - Keep all voice samples in `voices/samples/`
   - Store episode audio in `episodes/your_episode/audio/`
   - Place sound effects in `assets/sound_effects/`
   - Keep music in `assets/music/`
   - Store ambience in `assets/ambience/`

2. **Recording Reference Audio**
   - Use a pop filter
   - Keep consistent distance from microphone
   - Speak at normal volume
   - Use natural speech patterns
   - Record multiple takes and choose the best

3. **File Management**
   - Keep original recordings
   - Use consistent naming
   - Back up your samples
   - Document any special requirements

4. **Performance**
   - Coqui TTS works best with clear, clean audio
   - Longer samples don't always mean better results
   - Keep your system cool during generation
   - Consider using a GPU if available

## 8. Advanced Usage

1. **Custom Models**
   - You can use different TTS models:
   ```python
   from TTS.api import TTS
   tts = TTS(model_name="tts_models/multilingual/multi-dataset/your_tts")
   ```

2. **Language Support**
   - Coqui supports multiple languages
   - Set the language in voice_config.json
   - Use appropriate language codes (e.g., "en", "es", "fr")

3. **Batch Processing**
   - Generate multiple lines at once
   - Use the --dry-run option to check first
   - Monitor system resources

## 9. Maintenance

1. **Regular Checks**
   - Validate configurations monthly
   - Check audio quality
   - Update dependencies
   - Backup voice samples

2. **Updates**
   - Keep TTS package updated
   - Check for new models
   - Test after updates
   - Keep documentation current

## 10. Resources

1. **Official Documentation**
   - [Coqui TTS GitHub](https://github.com/coqui-ai/TTS)
   - [YourTTS Model](https://huggingface.co/coqui/your_tts)

2. **Community**
   - [Coqui Discord](https://discord.gg/5eXr5seRrb)
   - [GitHub Issues](https://github.com/coqui-ai/TTS/issues)

3. **Tools**
   - [FFmpeg](https://ffmpeg.org/)
   - [Audacity](https://www.audacityteam.org/)

Remember: Good quality reference audio is key to getting the best results from Coqui TTS. Take your time to record and prepare your voice samples carefully!
