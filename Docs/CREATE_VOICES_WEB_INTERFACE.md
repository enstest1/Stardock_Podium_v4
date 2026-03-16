# Creating Voices via ElevenLabs Web Interface

Since voice creation via API requires a paid ElevenLabs plan, use this guide to create voices manually through the ElevenLabs web interface using our improved prompts.

## Steps

1. Go to: https://elevenlabs.io/app/voice-design
2. For each character below, follow these steps:
   - Click "Add Voice" or "Create Voice"
   - Select "Voice Design" (text description method)
   - Copy the description from below
   - Paste into the description field
   - Name the voice as specified
   - Generate the voice
   - Copy the Voice ID that gets created
   - Save the Voice ID for updating `voice_config.json`

---

## Character Voices to Create

### 1. Aria T'Vel (Vulcan)

**Voice Name:** `Aria T'Vel (Improved)`

**Description to paste:**
```
A Vulcan female voice that is smooth, calm, and precisely articulated. The voice has a logical, measured quality typical of Vulcans, with perfect enunciation and clear vowel pronunciation. There is an undercurrent of warmth and emotional depth that suggests she understands emotions even while maintaining Vulcan control. The voice should sound intelligent and authoritative, with a calm confidence. The tone is steady and controlled, never hurried or emotional, but capable of subtle shifts that reveal deeper feelings. The pitch is medium to slightly lower for a female voice, conveying wisdom and maturity. Articulation is crisp and precise, with careful pronunciation of consonants.
```

**Settings to use (if available):**
- Stability: 0.65
- Similarity Boost: 0.80
- Style: 0.15

---

### 2. Jalen (Trill)

**Voice Name:** `Jalen (Improved)`

**Description to paste:**
```
A male Trill voice that is warm, enthusiastic, and carries the wisdom of multiple lifetimes through the symbiont. The voice has a natural eagerness and curiosity that can accelerate when excited about discoveries, while maintaining a foundation of ancient knowledge and experience. The tone is friendly and approachable, yet authoritative when needed. There's a slight musical quality to the voice, reflecting the Trill culture's appreciation for music and art. The voice should sound like it belongs to someone both youthful in energy and ancient in wisdom - enthusiastic but never naive. The pitch is medium, with warmth in the lower register. The voice can shift between quick, excited delivery for scientific discoveries and slower, more contemplative tones when sharing wisdom from past hosts.
```

**Settings to use (if available):**
- Stability: 0.55
- Similarity Boost: 0.75
- Style: 0.25

---

### 3. Naren (Bajoran)

**Voice Name:** `Naren (Improved)`

**Description to paste:**
```
A female Bajoran voice that is strong and confident, with the remarkable ability to shift between commanding authority and spiritual serenity. The voice carries the weight of experience and resilience, reflecting someone who has survived occupation and emerged stronger. There is a slight accent that reflects her Bajoran heritage - subtle but present, with a musical quality to the pronunciation. The voice should sound like it belongs to a leader - firm when giving orders, compassionate when comforting, and reverent when speaking of the Prophets. The tone is firm but never harsh, compassionate but never weak. The pitch is medium to slightly lower, conveying maturity and strength. When speaking of spiritual matters, the voice takes on a softer, more contemplative quality. When commanding, it becomes crisp and clear with authority.
```

**Settings to use (if available):**
- Stability: 0.60
- Similarity Boost: 0.80
- Style: 0.30

---

### 4. Elara (Caitian)

**Voice Name:** `Elara (Improved)`

**Description to paste:**
```
A female Caitian voice that is softly musical with a subtle purring undertone. The voice should be soothing and gentle, with a playful lilt that can become serious and professional when needed. The tone reflects her species' feline nature - smooth, graceful, and fluid like a cat's movement. There's a warmth to the voice that makes patients feel at ease, combined with clear, professional articulation that establishes medical authority. The voice has a slight breathy quality that adds to its gentle nature. When serious or concerned, the playful elements fade but the warmth remains. The pitch is medium to slightly higher, with smooth transitions between tones. The voice should sound like someone who is both nurturing and competent - a healer's voice.
```

**Settings to use (if available):**
- Stability: 0.50
- Similarity Boost: 0.75
- Style: 0.20

---

### 5. Sarik (El-Aurian)

**Voice Name:** `Sarik (Improved)`

**Description to paste:**
```
A male El-Aurian voice that is gentle and reflective, carrying an aura of wisdom beyond his years. The voice is deliberate and thoughtful, with a comforting, almost lyrical quality that reflects his species' long lifespan and natural empathy. The tone should sound like someone who has seen centuries pass - patient, understanding, and deeply empathetic. There's a musical quality to the voice, with smooth, flowing speech patterns. The voice should sound calming and reassuring, like a wise counselor or mentor. The pitch is medium to slightly lower, with a richness that comes from experience. The voice moves at a measured pace, never rushed, with pauses that feel natural and contemplative. When speaking, it sounds like each word is carefully chosen and meaningful.
```

**Settings to use (if available):**
- Stability: 0.70
- Similarity Boost: 0.80
- Style: 0.15

---

### 6. Narrator

**Voice Name:** `Narrator (Improved)`

**Description to paste:**
```
A versatile narrator voice that is clear, authoritative, and engaging. The voice should sound like a professional documentary narrator or audiobook reader - confident and easy to listen to for extended periods. The tone is warm but neutral, allowing the story to take center stage. The voice should be articulate with excellent pronunciation, suitable for describing complex scenes and technical concepts. There should be a sense of gravitas appropriate for Star Trek storytelling - serious when needed, but never melodramatic. The voice should be smooth and flowing, with natural pacing that guides the listener through the narrative. The pitch is medium, with good projection and clarity. The voice should feel trustworthy and reliable, like a skilled storyteller.
```

**Settings to use (if available):**
- Stability: 0.65
- Similarity Boost: 0.75
- Style: 0.10

---

## After Creating All Voices

1. **Get Voice IDs:**
   - For each voice created, copy its Voice ID
   - The Voice ID is usually visible in the voice details page
   - Format: Long string like `"HV5LQQys2FkXruuXDrZb"`

2. **Update `voice_config.json`:**
   - Replace the `eleven_id` values with the new Voice IDs
   - Keep the structure the same, just update the IDs

3. **Test each voice:**
   - Use the test generation feature in ElevenLabs web interface
   - Or use: `python cli/generate_voices.py --text "Test" --voice "character_name" --output test.wav`

4. **Update configuration:**
   - Once satisfied, update `voice_config.json` with new IDs
   - The system will automatically use the new voices

---

## Alternative: Use Existing Voices

If you prefer to use your existing voices (which are already configured), you can:
1. Skip voice creation
2. Keep current `eleven_id` values in `voice_config.json`
3. Proceed with ElevenLabs-only migration using existing voices
4. Optionally update settings only (stability, similarity_boost, style)

