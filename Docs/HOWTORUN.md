# HOWTORUN.md

> **How to Run the AI Podcast Generator (ELI5 Edition)**

This guide will walk you through every step to create your own Star Trek-style podcast episode using the AI system. No advanced knowledge required!

---

## 1. What You Need Before You Start

- **A Windows 10 computer**
- **Python 3.8 or newer** installed
- **FFmpeg** installed and added to your PATH
- **ElevenLabs account** with enough credits for voice generation
- **OpenAI or OpenRouter API key**
- **A Star Trek (or other) EPUB book** to use as reference

---

## 2. Setting Up the Project

1. **Download or clone the project folder** to your computer.
2. **Open a terminal** (Command Prompt, PowerShell, or Git Bash) and go to the project folder:
   ```
   cd C:/Users/yourname/Desktop/Cursor/stardock_podium_04
   ```
3. **Install the required Python packages:**
   ```
   pip install -r requirements.txt
   ```
4. **Create a `.env` file** in the project folder and add your API keys:
   ```env
   OPENAI_API_KEY=your_openai_key_here
   ELEVENLABS_API_KEY=your_elevenlabs_key_here
   MEM0_API_KEY=your_mem0_key_here
   ```
5. **Make sure FFmpeg is installed and in your PATH.**
   - You can check by running:
     ```
     ffmpeg -version
     ```
   - If you see version info, you're good!

---

## 3. Ingest a Book (Turn Your EPUB into AI Knowledge)

1. **Put your EPUB file** in the `books/` folder.
2. **Run the ingest command:**
   ```
   python cli_entrypoint.py ingest-book --file books/YourBook.epub
   ```
   - This will read the book, analyze it, and store its knowledge for the AI to use.

---

## 4. Generate an Episode Outline

1. **Run the outline command:**
   ```
   python cli_entrypoint.py generate-outline --book your_book_id --episode your_episode_id
   ```
   - Replace `your_book_id` with the ID or name of your book (check the `books/` folder).
   - Replace `your_episode_id` with a name for your episode (like `ep_001`).
   - This creates a plan for your episode (scenes, plot points, etc.).

---

## 5. Generate the Script

1. **Run the script command:**
   ```
   python cli_entrypoint.py generate-script --episode your_episode_id
   ```
   - This writes all the dialogue and narration for your episode, scene by scene.

---

## 6. Assign Voices to Characters

1. **Run the voice registry command:**
   ```
   python register_voices.py
   ```
   - Follow the prompts to assign ElevenLabs voices to each character.
   - You only need to do this once per character.

2. **Record Speaker Reference Audio:**
   - For each character, record a 5-10 second WAV file:
     - Use a good quality microphone
     - Speak clearly in a quiet environment
     - Save as mono WAV at 16kHz sample rate
     - Name format: `voices/samples/character_name.wav`
   - Update `voices/voice_config.json` with the paths

3. **Validate Voice Setup:**
   ```
   python cli/validate_voices.py --script episodes/your_episode_id/script.json --config voices/voice_config.json
   ```
   - This checks that all required files and settings are correct.

---

## 7. Generate the Audio

1. **Run the audio generation command:**
   ```
   python cli/generate_voices.py --script episodes/your_episode_id/script.json --config voices/voice_config.json --outdir episodes/your_episode_id/audio
   ```
   - This will use Coqui TTS first, falling back to ElevenLabs if needed.
   - The audio files will be saved in `episodes/your_episode_id/audio/`.

---

## 8. Combine the Audio into a Full Episode

1. **Run the audio concatenation script:**
   ```
   python concat_audio.py
   ```
   - This will stitch all the scene audio files together into one big episode file.
   - The final file will be in `episodes/your_episode_id/audio/partial_episode.mp3` (or `.wav` if you convert it).

---

## 9. Listen to Your Podcast!

- Open the final audio file with any media player (VLC, Windows Media Player, etc.).
- Share it with friends, upload it, or keep creating more episodes!

---

## 10. Troubleshooting

- **Audio not playing?** Try converting the file to WAV using FFmpeg:
  ```
  ffmpeg -i episodes/your_episode_id/audio/partial_episode.mp3 episodes/your_episode_id/audio/partial_episode.wav
  ```
- **API errors?** Double-check your API keys in `.env` and your internet connection.
- **Missing voices?** Make sure you assigned all characters a voice in the registry.
- **Still stuck?** Check the `logs/` folder for error messages, or ask for help!

---

## 11. Quick Reference: All-in-One Example

```bash
# 1. Ingest a book
python cli_entrypoint.py ingest-book --file books/DS9_Prophets.epub

# 2. Generate outline
python cli_entrypoint.py generate-outline --book ds9_prophets --episode ep_001

# 3. Generate script
python cli_entrypoint.py generate-script --episode ep_001

# 4. Register voices
python register_voices.py

# 5. Generate audio
python cli/generate_voices.py --script episodes/ep_001/script.json --config voices/voice_config.json --outdir episodes/ep_001/audio

# 6. Concatenate audio
python concat_audio.py

# 7. (Optional) Convert to WAV
ffmpeg -i episodes/ep_001/audio/partial_episode.mp3 episodes/ep_001/audio/partial_episode.wav
```

---

**That's it! You're now ready to create your own AI-powered Star Trek podcast episodes.**
