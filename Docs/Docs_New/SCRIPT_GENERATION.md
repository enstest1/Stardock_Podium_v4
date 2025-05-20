# Script Generation Guide

## Overview
This guide covers the script generation process, including structure, character development, and quality control.

## Save the Cat Structure

### 1. Story Beats
- **Opening Image**: Episode hook
- **Theme Stated**: Core message
- **Setup**: Character introduction
- **Catalyst**: Inciting incident
- **Debate**: Character reaction
- **Break into Two**: New direction
- **B Story**: Subplot
- **Fun and Games**: Promise of premise
- **Midpoint**: False victory/defeat
- **Bad Guys Close In**: Rising tension
- **All Is Lost**: Dark moment
- **Dark Night of the Soul**: Character reflection
- **Break into Three**: Solution
- **Finale**: Resolution
- **Final Image**: Changed world

### 2. Implementation
```python
# Example: Beat generation
def generate_beats(theme, characters):
    beats = []
    for beat in SAVE_THE_CAT_BEATS:
        content = generate_beat_content(beat, theme, characters)
        beats.append({
            "beat": beat,
            "content": content
        })
    return beats
```

## Character Development

### 1. Character Creation
- **Traits**: Personality, background
- **Goals**: Personal objectives
- **Conflict**: Internal/external
- **Arc**: Development path

### 2. Character Interaction
- **Relationships**: Character dynamics
- **Dialogue**: Voice consistency
- **Conflict**: Tension points
- **Resolution**: Character growth

## Scene Structure (NEW FORMAT)

### 1. Scene Elements
- **Setting**: Location, time
- **Beat**: Story beat (see above)
- **Scene Number**: Sequential
- **Lines**: Array of line objects (see below)

### 2. Scene Line Format (REQUIRED)
Each scene's `lines` array must use objects with a `type` field and a `content` field. Dialogue lines must also include a `speaker` field.

```json
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
```
- Allowed `type` values: `description`, `sound_effect`, `narration`, `dialogue`
- `dialogue` lines must include a `speaker` field
- This format is required for all future podcast episodes

## Script File Structure (NEW FORMAT)

```json
{
  "title": "Episode Title",
  "episode_id": "ep_xxxxxxxx",
  "scenes": [
    { ...scene objects as above... }
  ]
}
```

## Best Practices
- Use consistent character names
- Use clear, concise descriptions
- Place sound effects and narration as separate lines
- End each scene with a description line: `{ "type": "description", "content": "END SCENE" }`
- Validate script structure before audio generation

## Quality Control
- Ensure all scenes follow the new format
- Check for missing `type`, `content`, or `speaker` fields
- Maintain logical story flow and beat structure
- Use the CLI validation tools before generating audio

## Integration
- Scripts in the new format are compatible with the TTS and audio pipeline
- Place scripts in `episodes/<episode_id>/script.json`
- Use the CLI tools to generate and validate audio

## Development

### 1. Testing
- Structure validation
- Character consistency
- Dialogue quality
- Story flow

### 2. Debugging
- Log issues
- Track changes
- Verify fixes
- Monitor quality

### 3. Deployment
- Version control
- Quality gates
- Documentation
- User feedback 