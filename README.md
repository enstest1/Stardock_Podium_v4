# Stardock Podium (v4)

Stardock Podium is an AI-powered Star Trek-style podcast generator that
ingests sci-fi reference materials and generates complete episodes with
continuity, voices, and a full audio pipeline.

For full documentation, see `Docs/README.md`.

## Quick start (Windows 10)

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables (recommended via `.env` locally):

- `OPENAI_API_KEY` or `OPENROUTER_API_KEY`
- `ELEVENLABS_API_KEY`
- `MEM0_API_KEY`

3. Run help / commands:

```bash
python main.py --help
```

## What’s intentionally not versioned

This repo ignores generated/runtime artifacts like `books/`, `episodes/`,
`analysis/`, `temp/`, and media outputs (audio/video/image files). Those
are produced locally when you run the pipeline.

