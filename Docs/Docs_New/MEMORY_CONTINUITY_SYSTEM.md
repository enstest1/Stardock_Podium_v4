# Complete Memory Extraction & Continuity System

## Overview

This document outlines a comprehensive multi-stage memory extraction system that captures episode information at key points in the generation workflow and uses it to maintain narrative continuity across episodes. This ensures that each new episode is a true continuation of the story, referencing previous events, maintaining character consistency, and resolving story threads properly.

---

## 1. Memory Extraction Timing & Strategy

### Three-Stage Extraction Approach

#### **Stage 1: Structure-Level Extraction** (After Structure Generation)
- **When:** After `generate_episode_structure()` completes
- **What:** Basic episode metadata
  - Episode title, number, series
  - Theme and target duration
  - Story beat structure
  - Initial character cast (if generated)
- **Purpose:** Establish episode identity in memory early

#### **Stage 2: Script-Level Extraction** (After Script Generation) ⭐ **PRIMARY EXTRACTION**
- **When:** After `generate_episode_script()` completes and script is saved
- **What:** Detailed narrative content
  - Plot points (what events happened)
  - Character development (how characters grew/changed)
  - World-building (what locations/technologies/rules were established)
  - Continuity markers (references to past/future)
  - Relationships (character interactions and dynamics)
  - Unresolved threads (plot points that need continuation)
- **Purpose:** Capture all story details for future reference

#### **Stage 3: Post-Production Extraction** (Optional, After Audio Generation)
- **When:** After audio is generated (if script was manually edited)
- **What:** Validation and updates
  - Verify extracted memories match final script
  - Capture any script edits made after generation
  - Update memory if discrepancies found
- **Purpose:** Ensure memory accuracy after manual edits

---

## 2. Memory Storage Structure

### Dual Storage System

#### **A. Human-Readable JSON File** (Local)
**Location:** `episodes/<episode_id>/memories.json`

**Structure:**
```json
{
  "episode_id": "ep_988afb7c",
  "episode_number": 1,
  "series": "Main Series",
  "extraction_version": "1.0",
  "extracted_at": 1234567890.0,
  "extraction_status": "complete",
  "categories": {
    "plot_points": [
      {
        "id": "plot_001",
        "content": "The crew receives a mysterious signal from an unknown source...",
        "scene_number": 1,
        "beat": "Catalyst",
        "importance": "major",
        "unresolved": false
      }
    ],
    "character_states": [
      {
        "character": "Aria T'Vel",
        "current_state": "Captain investigating mysterious signal",
        "location": "Bridge of the Celestial Temple",
        "knowledge": ["Knows about the signal", "Suspicious of its origin"],
        "emotional_state": "focused and determined",
        "character_development": "Shows strong leadership in crisis"
      }
    ],
    "world_building": [
      {
        "element": "Location: Bridge of the Celestial Temple",
        "description": "The main bridge where the crew operates...",
        "first_mentioned": 1,
        "established_rules": []
      }
    ],
    "relationships": [
      {
        "characters": ["Aria T'Vel", "Jalen"],
        "relationship_type": "command",
        "current_dynamic": "Professional, respectful",
        "interactions": ["Aria commands, Jalen responds professionally"]
      }
    ],
    "unresolved_threads": [
      {
        "thread_id": "thread_001",
        "description": "The mysterious signal's origin and purpose",
        "introduced_in_scene": 1,
        "current_status": "investigating",
        "needs_resolution": true
      }
    ],
    "continuity_markers": [
      {
        "type": "reference_to_past",
        "content": "Character mentions previous mission",
        "scene": 5,
        "referenced_episode": null
      }
    ]
  }
}
```

**Purpose:** Human-readable backup, debugging, manual review

#### **B. Vector Database** (Mem0)
**Location:** Mem0 vector database (searchable, semantic)

**What Gets Stored:**
- All content from JSON, but as searchable vector embeddings
- Categorized by memory type (plot_point, character_development, etc.)
- Metadata for filtering (episode_id, character name, scene number, etc.)

**Purpose:** Fast semantic search during generation

---

## 3. Enhanced Memory Categories

### Current Categories (Enhanced with More Detail):
1. **Plot Points** - Major events, key decisions, plot progression
2. **Character Development** - Growth, realizations, changes
3. **World Building** - Locations, technologies, rules
4. **Continuity** - References and connections
5. **Relationships** - Character interactions and dynamics

### New Categories to Add:
6. **Character States** - Current location, knowledge, emotional state, goals
7. **Unresolved Threads** - Open plot points, mysteries, questions needing answers
8. **Timeline Markers** - Temporal information, sequence of events
9. **Character Arcs** - Multi-episode character progression tracks
10. **Series Arc** - Overarching plot threads spanning multiple episodes

---

## 4. Memory Usage During Generation

### Integration Points in Generation Workflow

#### **A. Episode Structure Generation**
**When:** `generate_episode_structure()`
**Action:**
- Search for previous episodes in same series
- Get latest episode number, unresolved threads
- Retrieve series arc information
- Include in episode initialization prompt

#### **B. Character Generation**
**When:** `generate_character_cast()`
**Action:**
- Search for existing characters from previous episodes
- Retrieve character states, arcs, relationships
- Include in character generation prompt:
  - "Continue using existing characters X, Y, Z with their current states..."
  - "Introduce new characters that complement existing cast..."
  - "Maintain relationship dynamics established in previous episodes..."

#### **C. Scene Outline Generation**
**When:** `generate_scenes()` / `_generate_scene_outline()`
**Action:**
- Search for relevant plot points from previous episodes
- Get unresolved threads that should be addressed
- Retrieve character states relevant to scene
- Include in scene generation prompt:
  ```
  PREVIOUS EPISODE CONTEXT:
  - Episode 1 ended with: [summary of ending]
  - Unresolved threads: [list of open plot points]
  - Character states: [where characters are, what they know]
  - This episode should: [continue/address/resolve...]
  ```

#### **D. Script Generation**
**When:** `_generate_scene_script()`
**Action:**
- Search for specific character memories for each character in scene
- Retrieve relevant plot points and world-building details
- Get relationship dynamics between characters in scene
- Include in script generation prompt:
  ```
  CHARACTER CONTEXT:
  [Character Name] - Current state: [state], Knows: [knowledge],
  Previously: [relevant past events], Relationship with [other character]: [dynamic]
  
  CONTINUITY NOTES:
  - Must reference: [specific plot point from previous episode]
  - Character should remember: [specific event]
  - Should not contradict: [established fact]
  ```

---

## 5. File Structure & Workflow

### Recommended File Structure:
```
episodes/
  ep_988afb7c/          # Episode 1
    structure.json       # Episode structure and beats
    script.json          # Full script
    memories.json        # ✨ NEW: Extracted memories (human-readable)
    audio/               # Generated audio files
    metadata.json        # Episode metadata
  
  ep_xxxxx/             # Episode 2
    structure.json
    script.json
    memories.json        # ✨ NEW
    audio/
    metadata.json
```

### Workflow with Memory Extraction:

```
1. Generate Episode Structure
   └─> Stage 1: Extract basic structure memories
   
2. Generate Characters
   └─> (No extraction - characters are part of structure)
   
3. Generate Scenes
   └─> (No extraction - scenes are outlines, not detailed)
   
4. Generate Script
   └─> Stage 2: Extract detailed script memories ✨ PRIMARY EXTRACTION
       ├─> Save to memories.json (local)
       └─> Store in Mem0 (vector database)
   
5. [Optional] Generate Audio
   └─> Stage 3: Validate memories match final script
       └─> Update if script was manually edited
```

---

## 6. Implementation Strategy

### Phase 1: Memory Extraction Infrastructure
1. **Enhance `episode_memory.py`:**
   - Add `extract_character_states()` method
   - Add `extract_unresolved_threads()` method
   - Add `extract_timeline_markers()` method
   - Create `save_memories_json()` method (save to local JSON file)

2. **Add Automatic Extraction Trigger:**
   - Modify `generate_episode_script()` in `story_structure.py`
   - After script is saved, automatically call memory extraction
   - Save to both JSON file and Mem0

### Phase 2: Memory Retrieval During Generation
1. **Enhance `story_structure.py`:**
   - Add `_get_previous_episode_context()` method
   - Add `_get_character_memories()` method
   - Add `_get_unresolved_threads()` method
   - Integrate into scene generation prompts
   - Integrate into script generation prompts

2. **Update Generation Prompts:**
   - Include previous episode summaries
   - Include character states and arcs
   - Include unresolved threads
   - Include relationship dynamics

### Phase 3: CLI Commands for Memory Management
1. **Add New CLI Commands:**
   ```bash
   # Extract memories from an episode
   python main.py extract-memories <episode_id>
   
   # View memories for an episode
   python main.py view-memories <episode_id>
   
   # Search memories across episodes
   python main.py search-memories "<query>"
   
   # Get continuity report for next episode
   python main.py continuity-report --series "Main Series"
   ```

### Phase 4: Validation & Quality Checks
1. **Add Memory Validation:**
   - Check if memories were extracted
   - Validate memory completeness
   - Verify memories are in Mem0
   - Warn if previous episode has no memories

2. **Add Continuity Checking:**
   - Before generating new episode, check if previous episode has memories
   - Provide warnings if continuity might be broken
   - Suggest extracting memories if missing

---

## 7. Enhanced Extraction Logic

### Character State Extraction (NEW)
Extract for each character:
- Current location/status
- Knowledge/awareness (what they know)
- Emotional state
- Current goals/motivations
- Character arc progression
- Relationships with other characters

### Unresolved Thread Extraction (NEW)
Extract:
- Open plot questions introduced
- Mysteries not solved
- Character conflicts not resolved
- Events that need follow-up
- Foreshadowing that needs payoff

### Timeline Extraction (NEW)
Extract:
- Sequence of events
- Temporal relationships
- "Before/after" markers
- Duration/time passing information

---

## 8. Example: Complete Workflow

### Episode 1 (Complete):
```bash
# 1. Generate structure
python main.py generate-episode --series "Main Series" --theme "Mysterious Signal"

# 2. Generate characters
python main.py generate-characters ep_988afb7c

# 3. Generate scenes
python main.py generate-scenes ep_988afb7c

# 4. Generate script (automatically extracts memories)
python main.py generate-script ep_988afb7c
# └─> Creates: episodes/ep_988afb7c/memories.json
# └─> Stores in: Mem0 vector database

# 5. Generate audio
python main.py generate-audio ep_988afb7c
```

### Episode 2 (With Continuity):
```bash
# 1. Generate structure (automatically searches previous episodes)
python main.py generate-episode --series "Main Series" --theme "Investigation Continues"
# └─> System automatically:
#     - Finds Episode 1
#     - Retrieves unresolved threads
#     - Sets episode_number = 2
#     - Includes context in generation

# 2. Generate characters (uses existing characters + adds new ones)
python main.py generate-characters ep_xxxxx
# └─> System automatically:
#     - Retrieves character states from Episode 1
#     - Suggests reusing existing characters
#     - Maintains character arcs

# 3. Generate scenes (uses previous episode context)
python main.py generate-scenes ep_xxxxx
# └─> System automatically:
#     - Includes Episode 1 summary in prompts
#     - Addresses unresolved threads
#     - Continues character arcs

# 4. Generate script (uses character memories)
python main.py generate-script ep_xxxxx
# └─> System automatically:
#     - Retrieves character-specific memories
#     - Includes relationship dynamics
#     - References previous events appropriately
#     - Maintains continuity
```

---

## 9. Prompt Enhancement Examples

### Scene Generation Prompt (Enhanced):
```
Create a scene outline for a Star Trek podcast episode.

EPISODE INFORMATION:
Title: [New Episode Title]
Theme: [Theme]
Episode Number: 2 (continuation of Episode 1)

PREVIOUS EPISODE SUMMARY:
Episode 1 "[Previous Title]" ended with:
- [Major plot point 1]
- [Major plot point 2]
- [Character state changes]

UNRESOLVED THREADS FROM PREVIOUS EPISODE:
- [Thread 1: Description, introduced in scene X]
- [Thread 2: Description, introduced in scene Y]

CHARACTER STATES:
[Character Name]: Currently [location/status], Knows [knowledge],
Feels [emotion], Wants [goal]

CURRENT STORY BEAT: [Beat Name]
Progress: [X]% through story

REFERENCE MATERIAL FROM BOOKS:
[Relevant book content]

Create a scene that:
1. Continues the narrative from Episode 1
2. Addresses relevant unresolved threads
3. Maintains character consistency
4. Advances the story appropriately for this beat
```

### Script Generation Prompt (Enhanced):
```
Generate a detailed script for a Star Trek audio drama scene.

CONTEXT:
Title: [Episode Title]
Theme: [Theme]
Beat: [Beat Name]
Setting: [Setting]
Scene Number: [X] of [Y]

PREVIOUS EPISODE CONTEXT:
Episode [N-1] "[Previous Title]" ended with [ending summary].
This episode continues that story.

CHARACTERS IN THIS SCENE:
[Character 1 Name]:
- Current state: [location/status]
- Knows: [knowledge from previous episodes]
- Previously: [relevant past events]
- Relationship with [Other Character]: [dynamic]

[Character 2 Name]:
- Current state: [location/status]
- Knows: [knowledge from previous episodes]
- Relationship with [Other Character]: [dynamic]

CONTINUITY REQUIREMENTS:
- Must reference: [specific plot point from previous episode]
- Character should remember: [specific event]
- Should not contradict: [established fact]
- Should address: [unresolved thread] if relevant

REFERENCE MATERIAL FROM BOOKS:
[Relevant book content]

Generate a scene that:
1. Maintains character consistency with previous episodes
2. References past events appropriately
3. Advances character arcs
4. Includes scene description, dialogue, sound effects, and narration
```

---

## 10. Benefits of This System

1. **Automatic Continuity** - Memories extracted and used without manual steps
2. **Human-Readable** - JSON file for review and debugging
3. **Searchable** - Mem0 enables semantic search during generation
4. **Comprehensive** - Captures plot, characters, world, relationships, threads
5. **Scalable** - Works across multiple episodes and series
6. **Validation** - Checks ensure memories exist before generating new episodes
7. **Flexible** - Can extract manually or automatically

---

## 11. Memory JSON Schema Reference

### Complete Schema:
```json
{
  "episode_id": "string",
  "episode_number": "integer",
  "series": "string",
  "extraction_version": "string",
  "extracted_at": "float (timestamp)",
  "extraction_status": "complete|partial|failed",
  "categories": {
    "plot_points": [
      {
        "id": "string",
        "content": "string",
        "scene_number": "integer",
        "beat": "string",
        "importance": "major|minor",
        "unresolved": "boolean"
      }
    ],
    "character_states": [
      {
        "character": "string",
        "current_state": "string",
        "location": "string",
        "knowledge": ["string"],
        "emotional_state": "string",
        "goals": ["string"],
        "character_development": "string"
      }
    ],
    "character_development": [
      {
        "character": "string",
        "content": "string",
        "scene_number": "integer",
        "type": "growth|realization|change"
      }
    ],
    "world_building": [
      {
        "element": "string",
        "type": "location|technology|rule|culture",
        "description": "string",
        "first_mentioned": "integer (scene)",
        "established_rules": ["string"]
      }
    ],
    "relationships": [
      {
        "characters": ["string"],
        "relationship_type": "string",
        "current_dynamic": "string",
        "interactions": ["string"],
        "history": "string"
      }
    ],
    "unresolved_threads": [
      {
        "thread_id": "string",
        "description": "string",
        "introduced_in_scene": "integer",
        "current_status": "string",
        "needs_resolution": "boolean",
        "importance": "major|minor"
      }
    ],
    "continuity_markers": [
      {
        "type": "reference_to_past|foreshadowing|callback",
        "content": "string",
        "scene": "integer",
        "referenced_episode": "string|null",
        "referenced_element": "string"
      }
    ],
    "timeline_markers": [
      {
        "event": "string",
        "scene_number": "integer",
        "temporal_relationship": "before|after|during",
        "related_event": "string"
      }
    ]
  }
}
```

---

## 12. Integration Checklist

### Required Code Changes:

#### `episode_memory.py`:
- [ ] Add `extract_character_states()` method
- [ ] Add `extract_unresolved_threads()` method
- [ ] Add `extract_timeline_markers()` method
- [ ] Add `save_memories_json()` method
- [ ] Enhance existing extraction methods with more detail
- [ ] Add validation for extraction completeness

#### `story_structure.py`:
- [ ] Add `_get_previous_episode_context()` method
- [ ] Add `_get_character_memories()` method
- [ ] Add `_get_unresolved_threads()` method
- [ ] Modify `generate_episode_structure()` to search previous episodes
- [ ] Modify `generate_character_cast()` to use character memories
- [ ] Modify `generate_scenes()` to include previous episode context
- [ ] Modify `_generate_scene_outline()` to include continuity context
- [ ] Modify `generate_episode_script()` to trigger memory extraction
- [ ] Modify `_generate_scene_script()` to include character memories and continuity

#### `cli_entrypoint.py`:
- [ ] Add `extract-memories` command
- [ ] Add `view-memories` command
- [ ] Add `search-memories` command
- [ ] Add `continuity-report` command

#### `mem0_client.py`:
- [ ] Verify `search_episode_memories()` method works correctly
- [ ] Add method to search for unresolved threads
- [ ] Add method to get character states

---

## 13. Testing Strategy

### Test Cases:
1. **Memory Extraction:**
   - Extract memories from Episode 1
   - Verify JSON file is created correctly
   - Verify memories are stored in Mem0
   - Verify all categories are populated

2. **Memory Retrieval:**
   - Generate Episode 2 structure
   - Verify previous episode context is retrieved
   - Verify unresolved threads are found
   - Verify character states are retrieved

3. **Continuity in Generation:**
   - Generate Episode 2 script
   - Verify it references Episode 1 events
   - Verify character consistency
   - Verify unresolved threads are addressed

4. **Edge Cases:**
   - Generate Episode 2 without Episode 1 memories (should warn)
   - Extract memories from episode without script (should handle gracefully)
   - Generate episode with no previous episodes (should work normally)

---

## 14. Future Enhancements

### Potential Additions:
1. **Memory Conflict Detection:**
   - Detect contradictions between episodes
   - Flag inconsistencies
   - Suggest resolutions

2. **Automatic Thread Resolution:**
   - Track which threads are resolved in which episodes
   - Mark threads as resolved automatically
   - Generate reports on thread resolution status

3. **Character Arc Visualization:**
   - Track character development across episodes
   - Generate character arc summaries
   - Identify character development patterns

4. **Series Arc Planning:**
   - Plan multi-episode arcs
   - Track series-wide plot threads
   - Generate series arc summaries

5. **Memory Refinement:**
   - Use LLM to summarize and refine extracted memories
   - Extract higher-level themes and patterns
   - Generate episode summaries automatically

---

## Summary

This comprehensive memory extraction and continuity system ensures that:

1. **Episode 2 (and future episodes) will be true narrative continuations** - referencing previous events, maintaining character consistency, and resolving story threads properly
2. **Memories are automatically extracted** after script generation
3. **Memories are automatically used** during new episode generation
4. **Both human-readable and searchable formats** are maintained
5. **The system is scalable** across multiple episodes and series

The system captures the full narrative context at each stage and makes it available for future generation, creating a cohesive, continuous story across all episodes.

