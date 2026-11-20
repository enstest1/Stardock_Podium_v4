# 16 — Universal Scope Correction and Creative Reference Control (Delta)

**Date:** 2026-11-11 (same research day as documents 00–15). **Audited commit unchanged:** `c32a965…`.

This document is a correction and extension of the existing handoff, not a second plan. It records what changed and holds the one new design (Creative Reference Control). The executable items live where they already lived:

- change specifications → `11_EXACT_CHANGE_SPECIFICATIONS.md` (8 new specs appended, existing ones amended)
- roadmap → `10_CURSOR_IMPLEMENTATION_ROADMAP.md` (updated in place, with status marks)
- tests → `12_TEST_PLAN_AND_ACCEPTANCE_CRITERIA.md` (tests A–H added as T15–T22)
- Cursor prompt → `14_CURSOR_MASTER_EXECUTION_PROMPT.md` (updated in place)

Labels as before: OBSERVED, VERIFIED-EXTERNAL, INFERENCE, PROPOSED, UNVERIFIED.

**Additional research done for this delta:** a source read of the four ingestion modules I had only outlined before (`epub_processor.py`, `book_style_analysis.py`, `reference_memory_sync.py`, `ingest_all.py`), the Mem0 namespace constants, `episode_metadata.py`, and a full franchise-term scan. No new external research: nothing in the corrected scope needed it. **Still not done:** LLM generation, audio synthesis, any nonfiction script generation.

---

# A. Corrections to previous research

## A1. Assumptions in my own deliverables

| # | Assumption | Where it was | Correction | Code or data-model change? | Cursor task |
|---|---|---|---|---|---|
| 1 | Every project is fiction with a season-long plot | Doc 04 §2 (nine levels presented as universal), doc 06 (roadmap required), `STORYOS-002`, `PLAN-001` | The nine levels are the **serialized-fiction** configuration. A project has a production mode; each mode switches levels on or off through a capability table | Yes: `ProjectConfig`, `MODE_CAPABILITIES` | `GEN-001` (new); `STORYOS-002`, `PLAN-001`, `PLAN-002` modified to read the mode |
| 2 | Every show has a permanent ensemble | `STORYOS-001` (IDs for `main_cast`), `CHAR-001`, doc 05 §5 | Cast style is a mode capability: `ensemble`, `recurring`, `per_episode`, `per_story`, `hosts`. Hosts and narrators get profiles with dialogue and voice fields but no want/need/arc | Yes: `cast_style`; profile fields optional by role | `CHAR-001` modified |
| 3 | Every episode uses a dramatic framework | `NARRATIVE-002` registry (ten fiction frameworks), doc 03 §2.1 | Registry gains nonfiction, educational and conversational formats; selection is filtered by the mode's `frameworks` capability | Yes: registry rows and a `family` field | `NARRATIVE-002` modified |
| 4 | Every episode is outlined as scene cards with goal/opposition/turn | `NARRATIVE-001` | Unchanged for fiction modes. Nonfiction modes outline with **segment cards** (purpose, key points, claims, takeaway) | Yes: `SegmentCard`, a second card prompt and validator | `NARRATIVE-001` unchanged; `GEN-002` new |
| 5 | One editorial process | Doc 07 §3 (lint rows such as "narration ≤ 15%", "turn happens on the page"), `QUALITY-001`, `QUALITY-004` | Editorial profile per mode: `fiction` or `factual`. Factual editorial checks citations, uncertainty flags, invented quotes, learning progression; fiction-only rules are skipped | Yes: rule sets keyed by mode | `QUALITY-001`, `QUALITY-004` modified; `REF-003`, `GEN-002` new |
| 6 | Reference books define canon | `BASE-003` reduced this to a boolean `use_book_rag`; doc 07 §1 treated books only as a leakage risk | Replaced by reference **purposes**. A source contributes style, facts, world or story only for the purposes the user selected, and world/adaptation need recorded rights | Yes: `ReferenceSource`, bindings | `BASE-003` modified (flag superseded); `REF-001…005` new |
| 7 | One memory namespace per installation | `CANON-005` kept Mem0's existing namespaces; doc 05 scoped the ledger by show but not Mem0, voices or metadata | Every store is keyed by `project_id`. Mem0 `user_id` becomes `<project_id>:<kind>` | Yes | `GEN-003` new; `CANON-005`, `AUDIO-006`, `AUDIO-008` modified |
| 8 | Ship-and-space examples in universal places | Doc 08 §6–§9 used engine hum, alarms and hull impacts as if generic; `reference/scene_cards.py` system prompt said "serialized audio drama"; fixtures are one SF show | Examples stay as examples. Sound categories are generic and registries are per show. The card prompt string is now "an audio drama" (re-tested, 21 passed). Two more fixture projects are added | Small | `AUDIO-005`, `AUDIO-008` modified; tests T15–T22 |
| 9 | Feed is always `itunes:type = serial` | Doc 09 §5.3 | Taken from the mode (`feed_type`) | Yes (one field) | `PUB-002` modified |
| 10 | Narration is suspect | Doc 07 §3.1, doc 03 §3.5 | True for drama; documentary, educational and conversational formats are narration- or host-led | Rule gating | `QUALITY-004` modified |
| 11 | `ShowProfile` fields `universe_name`, `log_term`, `date_term` | `BASE-003` schema | Fiction-centric names. Replaced by a generic `format` block; the old keys remain readable for the legacy show | Yes | `BASE-003` modified |
| 12 | Publishing description rule "no spoilers" and chapter titles from scene goals | `PUB-001` | For nonfiction: description lists topics and **sources**; chapters from segment purposes; show notes carry citations | Yes | `PUB-001` modified |

## A2. Corrections to my audit (errors and omissions)

| # | Earlier statement | Correction (OBSERVED now) | Effect |
|---|---|---|---|
| 1 | Doc 01 §1 listed "Publishing, RSS … MISSING" | `episode_metadata.generate_episode_feed(format="rss")` exists (`episode_metadata.py:604–662`): a minimal RSS 2.0 string with a hard-coded channel title, the description "AI generated Star Trek-style podcast episodes" (`:633`), a relative enclosure URL, and no owner, artwork, dates or namespace tags. It also keeps a **third** series registry under `data/metadata`. Classification: **PARTIAL**, not missing | `PUB-002` now extends that function instead of adding a separate feed builder; `STORYOS-001` migration notes the third registry |
| 2 | Ingestion modules were outlined, not read | Read now; findings in A3 | `REF-001…004` reuse them |
| 3 | Franchise scan covered five terms | Widened scan: 17 non-test files (table in A4) | `BASE-003` file list extended |

## A3. What the existing ingestion code does (OBSERVED)

| Module | Does | Limits relevant to the new scope | Reuse decision |
|---|---|---|---|
| `epub_processor.py` (551 lines) | EPUB → metadata, chapters, sections; stored per `book_id`; listing and accessors | EPUB only; no project scope; no rights or purpose fields | **Extend**: add loaders for txt, md, docx, pdf, html that emit the same chapter/section structure; keep `book_id` as `legacy_book_id` |
| `reference_memory_sync.py` (418) | Pushes every section of every book to Mem0 through `add_reference_material`; `search_references(query)` | All books go to one namespace: `user_id="reference_materials"` (`mem0_client.py:270, 341`). Metadata has `book_id`, title, author — no project, purpose or enabled flag | **Extend**: namespace by project, add `source_id`, `purpose`; filter by enabled sources at query time |
| `book_knowledge.py` (458) | Samples chunks with eight fixed Star Trek queries (`:203–210`), asks an LLM for **one global bible** (`universe`, factions, characters, technology …) and one style profile; injects bible, style and raw chunks into prompts | Any ingested book automatically defines world facts for every show. Style prompt includes `recurring_motifs` (expressive content). Raw chunks reach scene prompts | **Split by purpose**: the bible extractor becomes the world-building extractor, run per source and only for sources with that purpose and rights; the style prompt becomes the technique extractor with a closed vocabulary; raw-chunk injection is limited to research and authorised adaptation |
| `book_style_analysis.py` (1,135) | NLTK statistics: sentence and word statistics, writing style, dialogue ratio, vocabulary; **and** character names, settings, themes, plot elements, relationships, narrative arc | Mixes technique with content in one "style" analysis | **Reuse selectively**: `_compute_text_statistics`, `_analyze_writing_style`, `_analyze_dialogue` feed measurable technique traits. `_identify_characters` is reused as the **name-leak guard** (list of names that must not appear in a technique profile or its prompts). The content analyses run only for world-building/adaptation |
| `ingest_all.py` (42) | Ingests every `.epub` in `books/` | No project argument | **Extend**: `--project`, `--purpose`, `--rights` |
| `mem0_client.py` | Three fixed namespaces: `reference_materials`, `episodes`, `characters` (`:270–387`) | Shared across all shows; episode memory is separated only by a `series` string filter | `GEN-003` |

Conclusion: a second ingestion system is **not** needed. Every gap is a missing field or a missing filter on the existing path.

## A4. Repository generalization — franchise-specific code and the exact change

All OBSERVED at the audited commit. Changes are carried by `BASE-003` (modified) unless another task is named.

| File:line | What is there | Change |
|---|---|---|
| `story_structure.py:358, 376, 388` | "Star Trek-style podcast episode title"; system "professional sci-fi writer specializing in St…" | `format.title_prompt_noun`, `format.writer_persona` from the project |
| `story_structure.py:492` | RAG query "Star Trek character archetypes" | Query built from project genre; skipped with no world-building reference |
| `story_structure.py:557, 574, 725` | "Star Trek universe expert and character creator/designer" | `format.cast_designer_persona` |
| `story_structure.py:1009, 1047, 1060` | "scene outline for a Star Trek-style podcast episode"; "screenwriter specializing in science…" | Mode-specific outline prompt (scene or segment) |
| `story_structure.py:1341` | "script for a Star Trek audio drama scene" | `format.script_noun` |
| `story_structure.py:1436` | Parser docstring example "Captain's log, stardate…" | Neutral example |
| `story_structure.py` cast fields `species`, `role` (`:1265–1269`, `_parse_characters`) | Every character has a species | `species` optional; omitted from prompts when empty |
| `script_editor.py:328` | "regenerating a scene for a Star Trek-style podcast episode" | As above |
| `quality_checker.py:687` | "Star Trek-style podcast episode script" | Mode-specific editor prompt (`QUALITY-001`) |
| `book_knowledge.py:51–59, 86–88, 203–210, 397–403` | Lore-archivist and style prompts, eight sampling queries, default query "Star Trek scene" | `REF-002`, `REF-004` |
| `show_os/new_show.py:22` and `:124–130` | Usage example; refusal to create a show without ingested books | Neutral example; prompt-only creation (`GEN-001`) |
| `show_os/seasons.py` `ARC_BEATS_PROMPT` | Fiction arc for every show | Per-mode season planner (`PLAN-001`) |
| `audio_pipeline.py:80` | Comment "Trek-style stems" | Neutral |
| `audio_pipeline.py:159–165` | `role_to_character` with five named crew roles | Delete (unused) |
| `audio_pipeline.py:237–240, 988–997` | Stardate extraction; "Captain's log, Starship Celestial Temple … Gamma Quadrant" | Intro from `format.intro_template`; no stardate |
| `audio_pipeline.py:1036–1039` | Outro naming the Celestial Temple | `format.outro_template` |
| `audio_pipeline.py:660–693` | Ambience keyword table: bridge, engine room, shuttlecraft, transporter, … | Replaced by per-show location registry with generic categories (`AUDIO-005`, `AUDIO-008`) |
| `tts_pronunciation.py:51–87, 102–149` | Bajoran/Vulcan/Klingon lexicon; stardate expansion; `normalize_trek_tts_text` | Generic `normalize_tts_text(text, lexicon)`; the lexicon and the stardate rule move to the legacy show's `pronunciation_lexicon` and an optional per-show number rule |
| `tts_engine.py:20, 268, 417` | Imports and calls the Trek normaliser | Calls the generic one with the show lexicon |
| `generate_theme_music.py:64, 73` | "Epic space sci-fi theme … Star Trek style" | Prompt built from project genre and tone (`AUDIO-007`) |
| `episode_metadata.py:632–633` | Channel title and description constants | From the project (`PUB-002`) |
| `main.py:3, 9, 211`; `cli_entrypoint.py:5, 1017` | Docstrings and banner "AI Star Trek Podcast Generator" | "AI podcast studio" |
| `register_voices.py`, `register_voices_improved.py`, `cli/*.py` | Voice names and samples for one crew | Legacy scripts; leave, mark as examples in their docstrings |
| `book_style_analysis.py` setting classes (`space`, `far_future`, `futuristic` among others) | Fixed setting taxonomy | Not used for technique profiles; unchanged |
| `voices/voice_config.json` | One global character→voice map (9 entries, 35 aliases) | Per-show voice namespaces (`AUDIO-006`, `GEN-003`) |
| `data/shows/star_trek_horizon/` | The only committed show | Stays as a private legacy fixture with `original: false` |

Not franchise-specific but fiction-specific, and now gated by mode: `StoryStructure.BEAT_SHEET`, `story_os/planner.py`, `episode_memory` categories, `quality_checker._check_script_structure`.

---

# B. Existing findings that remain valid

Unchanged and not repeated here:

- The whole repository audit (doc 01) apart from the two corrections in A2.
- All external repository and model reviews, licences and decisions (doc 02).
- Storytelling research (doc 03) — every method stays, now scoped to the fiction modes; the level rule and the planning/editorial split apply to all modes.
- Canon ledger, beliefs, relationships, promises, character state (doc 05) — retained in full for serialized fiction, available in reduced form to the other fiction modes, replaced by a claim ledger for nonfiction.
- Roadmap with commitment levels, rolling replanning, the replanning experiment (doc 06) — retained for serialized fiction without weakening.
- Writers' room, pairwise judging, ablation and originality protocols (doc 07) — retained; the originality test applies to every mode, the fiction lint only to fiction.
- TTS matrix and benchmark, timeline mixer, alignment, DSP, mastering, QA, asset library and providers (doc 08) — retained; only the examples and the ambience/identity registries are generalised.
- Jobs and resume, deployment, host interface, Spotify-by-feed, rights gate (doc 09).
- ADRs 001–015. ADR-001 is refined (a project layer above shows), not reversed.
- Already universal in the first handoff, explicitly **retained**: `BASE-003` step 5 (create a show without books), `original` flag and rights gate, book RAG off for original shows, role-based model config, evidence-cited extraction, deterministic-first selection rules, flags and rollback discipline.

---

# C. New architecture requirements

## C1. Product scope

Stardock Podium is a universal AI podcast studio. One sentence creates a project. Star Trek was the development example and survives only as a private legacy fixture. No universe, EPUB, character database or reference library is required; references are optional inputs with explicit purposes.

## C2. Projects, shows and isolation

```
data/projects/<project_id>/
  project.json                 # ProjectConfig (mode, idea, genre, audience, …)
  references/
    sources/<source_id>.json   # ReferenceSource
    profiles/<source_id>.v<N>.json   # StyleProfile versions
    bindings.json              # ReferenceBinding[]
    claims.jsonl               # FactClaim (research purpose)
    audit.jsonl                # append-only provenance log; never deleted
data/shows/<show_id>/          # unchanged layout from doc 04 §3, plus "project_id" in the bible
```

- By default `project_id == show_id` (one show per project). A project may hold several shows that share a reference library.
- Every stored thing carries `project_id`: episodes, ledger, claims, references, Mem0 entries, voices, sound identities, metrics, jobs.
- Nothing crosses a project boundary unless `ProjectConfig.shared_reference_projects` names the other project. Sharing applies to references only, never to canon.
- `data/active_show.json` (doc 04) stays as a CLI convenience; no generation code may depend on "the active show" when an episode or command names a project.

## C3. Production modes

`MODE_CAPABILITIES` in `reference/reference_models.py` is the single switchboard. Code reads capabilities, not mode names.

| Capability | serialized_fiction | episodic_fiction | anthology | standalone_drama | documentary | educational | conversational |
|---|---|---|---|---|---|---|---|
| `season_plan` | `arc`: full roadmap, locked commitments, replanning | `slate`: list of episode premises; optional runner threads | `slate` around a theme | `none` (one outline; parts if long) | `slate` of topics | `curriculum`: ordered learning objectives with prerequisites | `slate` of topics/guests |
| `continuity` | `canon_full` | `canon_light`: persistent facts about recurring characters and places | `per_episode`: ledger used inside an episode; only host/frame persists | `per_story` | `claims` | `claims` + taught-concepts list | `claims` + callbacks list |
| `beliefs` (who knows what) | yes | yes | yes, within episode | yes | no | no | no |
| `promises_horizon` | series | episode | episode | episode | none | none | none |
| `cast` | ensemble | recurring | per episode (+ optional host) | per story | hosts/narrator | hosts | hosts + guest personas |
| `outline` | scene cards | scene cards | scene cards | scene cards | segment cards | segment cards | segment cards |
| `frameworks` family | fiction | fiction | fiction | fiction | nonfiction | educational | conversational |
| `editorial` | fiction | fiction | fiction | fiction | factual | factual | factual |
| `claims` ledger | no | no | no | no | yes | yes | yes |
| `feed_type` | serial | episodic | episodic | serial | episodic | serial | episodic |

Fiction genre (horror, comedy, historical, fantasy …) is **not** a mode. It is `ProjectConfig.genre`, free text, which drives prompts, framework preferences, sound palette and music prompts. Experimental formats are a custom row in the table.

**Mode proposal.** `propose_project(idea)` makes one planner call returning `{mode, rationale, genre, audience, episode_minutes, cast_style_hint, title_options[]}`, validated against the schema; a keyword fallback (for example "explain", "lesson", "history of" → educational/documentary; "interview", "talk show" → conversational; "anthology", "tales" → anthology) is used when no model is available. The user sees the proposal and can override with `--mode`. `mode_source` records which happened.

**What nonfiction uses instead of the fiction machinery** (`GEN-002`):

| Fiction component | Nonfiction counterpart |
|---|---|
| Season roadmap with dramatic question | Topic slate or curriculum (objectives, prerequisites, what each episode adds) |
| Scene card (goal, opposition, turn, value shift) | Segment card (purpose, key points, claim IDs, listener takeaway, transition) |
| Canon ledger | Claim ledger: every factual statement with citations and support level |
| Promise ledger | "Told you we'd come back to it" list — optional, episode horizon only |
| Character psychology | Host persona: voice, register, stance, what they never claim to know |
| Fiction frameworks | Nonfiction: cold open → question → context → evidence → complication → answer; chronological; case study. Educational: hook → objective → explain → worked example → check → recap. Conversational: cold open → intro → 2–4 segments → listener takeaway → sign-off |
| Fiction editor checklist | Factual editor: every claim cited; uncertainty spoken; no invented quotes or people; definitions before use; one idea per segment; recap matches objectives |
| Omniscience check | Unsupported-claim check |

Two rules specific to nonfiction and conversational formats: (1) hosts and guests are synthetic personas and must be presented as such — no impersonation of real people, and no words attributed to a real person unless quoted from a cited source; (2) with no research sources supplied, the script may use only general knowledge, every non-trivial claim is marked `unsupported` and flagged for human verification before publishing. Whether the model's general knowledge is accurate is **not** something this system can guarantee.

## C4. The five reference situations

| Situation | What the user supplies | What Stardock does |
|---|---|---|
| A. Idea only | One sentence | `create-podcast`: propose mode → identity → cast or hosts → default voices → season plan per mode. No ingestion code runs |
| B. Idea + references | Files, each with a purpose | Ingest into the project library; purposes decide what is extracted and where it may be used (section D) |
| C. Existing user-owned universe | Their lore, characters, earlier writing; rights = owned | World-building mode: entities and events enter the ledger with `origin: "source"`; everything Stardock adds is `origin: "generated"` |
| D. Continue an existing podcast | A show ID | Normal path: `produce-episode --show <id>`; canon, roadmap and references of that project only |
| E. Nonfiction research | Documents as evidence | Research mode: claims with citations; conflicts kept; uncertainty flagged |

---

# D. Creative Reference Control design

Schemas: `reference/reference_models.py` (executed; `OK reference_models`).

## D1. Five kinds of reference content, four user-facing modes

| Kind of content | User-facing mode | May supply | May **not** supply | Rights needed |
|---|---|---|---|---|
| Style | 1 — Writing techniques | Abstract traits from a closed vocabulary; measured statistics | Names, places, plot events, quotations, motifs, the author's identity in any prompt | None beyond lawful access; the output is abstract |
| Knowledge (facts) | 2 — Factual research | Claims with citations and support level | Uncited assertions; fictional canon | Lawful access; quotes kept short and attributed |
| World | 3 — Authorised world building | Characters, places, rules, history as source-established canon | Anything when rights are `unspecified` or `fair_reference` | `owned`, `licensed` or `public_domain` |
| Story | 4 — Authorised adaptation | Plot, scenes, dialogue to adapt | As above | `owned`, `licensed` or `public_domain`, with attribution text |
| Research for fiction (period detail for a historical drama) | 2, used by a fiction project | Facts that constrain invention | Canon about invented characters | As mode 2 |

A source may carry several purposes (the user's own novel can be style + world + story). Each purpose is extracted and stored separately, and each can be disabled separately. A source uploaded only for techniques never reaches the world or story extractors: `REF-002` does not call them, and the name-leak guard (D4) checks the result.

`unspecified` rights are never treated as permission: the model validator refuses to create a world-building or adaptation source without a qualifying status (tested).

## D2. Reference record (all required provenance fields)

`ReferenceSource`: `source_id` (stable, from the content hash), `project_id`, `show_id` (optional), `source_format`, `title`, `author`, `purposes[]`, `rights{status, holder, evidence, attribution_text, recorded_at}`, `ingested_at`, `content_sha256`, `extraction_model`, `extraction_version`, `style_profile_version`, `knowledge_classes[]`, `enabled`, `removed_at`, `purged_at`, `legacy_book_id`. Influence configuration lives in `bindings.json` (one `ReferenceBinding` per source × scope). Citation data lives on each `FactClaim` / `CanonEvent`.

```json
{
  "source_id": "SRC-9f2c41d07ab3",
  "project_id": "example_horror",
  "show_id": "the_last_station",
  "source_format": "epub",
  "title": "(user's reference title)",
  "author": "(author)",
  "purposes": ["writing_techniques"],
  "rights": {"status": "fair_reference", "holder": "", "evidence": "user owns a copy", "attribution_text": "", "recorded_at": 1794355200.0},
  "ingested_at": 1794355200.0,
  "content_sha256": "9f2c41d07ab3…",
  "extraction_model": "<extractor model>",
  "extraction_version": "technique_extractor@1",
  "style_profile_version": 2,
  "knowledge_classes": ["style"],
  "enabled": true, "removed_at": null, "purged_at": null,
  "legacy_book_id": "book_1a2b3c"
}
```

## D3. Influence control — interpretable parameters, not a percentage in a prompt

**Traits.** Nine numeric traits on defined 0–1 scales and four categorical traits with closed value lists (`NUMERIC_TRAITS`, `CATEGORICAL_TRAITS`): pacing, atmosphere, dialogue density, descriptive density, suspense, emotional rhythm, narrative complexity, sentence length, formality; narrative perspective, scene transitions, structural method, tone.

**Three numbers per source, all user-editable:**

1. `StyleProfile.numeric[trait]` — where the reference sits on the trait's scale (extracted, previewable, editable).
2. `ReferenceBinding.selected_traits[trait]` — how much this trait is taken from this source (0 = not selected).
3. `ReferenceBinding.influence` — the 0–100% slider for the source as a whole.

**Baseline.** Each show has its own `StyleProfile` (`source_id: "BASE"`), created from the idea and genre at show creation and editable. With no references, the baseline is the style.

**Resolution (`resolve_style`, executed and tested):**

```
weight_i   = influence_i × selected_traits_i[trait]
numeric    = base + Σ weight_i × (profile_i − base) / max(1, Σ weight_i)
categorical: the applicable binding with the most specific scope (episode > show > project),
             then the largest weight, then the smallest source_id; it replaces the baseline
             only when its weight ≥ 0.5
```

Properties (asserted in the reference file): order-independent; influence 0, a disabled binding, a disabled or removed source, or another project's binding all yield exactly the baseline; a trait nobody selected is untouched; two sources pulling one trait in opposite directions meet at the weighted point rather than one silently winning; weights above 1 in total are normalised.

Worked example from the test: baseline pacing 0.5; source A (pacing 0.9, influence 0.5, trait weight 1.0) and source B (pacing 0.1, influence 1.0, trait weight 0.25) → `0.5 + (0.5×0.4 + 0.25×(−0.4)) / 1 = 0.6`.

**What 0 / 25 / 50 / 75 / 100% mean.** The slider scales every selected trait's pull toward the reference: at 0 the baseline stands; at 100 a fully selected trait lands on the reference's value. It is a design control. It does not measure "how much of the style" is present, and no such measurement is claimed.

**From numbers to the prompt (`render_directives`).** Each resolved numeric value falls in one of five bands, and each band has a fixed plain-language instruction per trait, for example pacing 0.6 → "Brisk; enter scenes late, leave early." Categorical values are stated directly. The prompt never contains a percentage, a source title, an author name, or source text (asserted). This is the only route by which a technique reference reaches a writer prompt.

**Measured targets (optional, advisory).** For traits that can be counted — sentence length, dialogue density — the extractor stores raw statistics from `BookStyleAnalyzer._compute_text_statistics` / `_analyze_dialogue` in `StyleProfile.measured`. After a draft is written the same functions run on the script and a "style adherence" note reports the difference. It informs the user; it gates nothing.

**Scope and combination.** Bindings carry `scope{project_id, show_id?, episode_id?}`. A show-level binding applies to all its episodes; an episode-level binding applies to that episode and, for categorical traits, outranks show-level ones. Multiple sources blend as above. Factual sources are never blended (D5).

**User operations and what each does:**

| Operation | Command (new, under `reference`) | Effect |
|---|---|---|
| Add with purpose and rights | `reference add <file> --project P --purpose … --rights …` | Ingest; extract only for the chosen purposes |
| Preview extracted characteristics | `reference show <source_id>` | Prints the profile, bands and measured statistics; for research, the claim count and contested claims |
| Edit the profile | `reference edit-profile <source_id>` | New profile version; `edited_by_user: true` |
| Set influence / traits / scope | `reference bind <source_id> --influence 0.4 --trait pacing=0.7 … [--show S] [--episode E]` | Writes `bindings.json` |
| Enable / disable | `reference enable|disable <source_id>` | Toggles `enabled`; nothing deleted |
| See the result | `reference resolve --show S [--episode E]` | Prints resolved style **with the trace** (which source moved which trait by how much) |
| Reset to no references | `reference reset --show S` | Disables all bindings for the scope; baseline stands |
| Remove from future generation | `reference remove <source_id>` | Sets `removed_at`; see D6 |
| Delete extracted information | `reference purge <source_id>` | See D6 |
| Share a library | `project share-references --from P1 --to P2` | Adds to `shared_reference_projects`; explicit, logged |

A graphical interface is out of scope for this repository (it has none); the commands and JSON files are the interface, and their shapes are what a later UI would call.

## D4. Technique extraction and the isolation guard

```
reference add (purpose: writing_techniques)
  → existing loader (epub_processor or new format loader) → chapters/sections
  → sample sections (existing BookStyleAnalyzer._sample_sections)
  → measured statistics (existing _compute_text_statistics, _analyze_writing_style, _analyze_dialogue)
  → one extractor call: "place this text on each scale; choose one allowed value per categorical trait"
       input: sampled text.  output: StyleProfile JSON only (closed vocabulary; no free text)
  → Pydantic validation rejects unknown traits, out-of-range numbers and any value outside the allowed lists
  → name-leak guard: collect proper nouns from the source (existing _identify_characters + capitalised
       n-grams); assert none occurs anywhere in the stored profile, the binding, or a rendered directive
  → store profile vN, source record, audit line
NOT run for this purpose: world/bible extraction, character or plot extraction, Mem0 sync of raw sections
```

Because the profile type has no free-text field, a name or plot event has nowhere to be stored; the guard is a second line of defence and the basis of test T16. The existing style prompt's `recurring_motifs` and `what_to_avoid` free-text fields are dropped for technique references (motifs are expressive content).

On imitation of an identifiable author: the design passes only coarse, shared craft parameters, and never the author's name or text. At 100% it still cannot request "write like X". That reduces the risk of close imitation; it cannot prove the absence of resemblance, and the editor checklist gains one item ("reads as pastiche of a recognisable author") for projects with technique references.

## D5. Factual research flow and conflict rule

```
reference add (purpose: factual_research)
  → loader → sections with locators (chapter/section index; page where the format has pages)
  → optional Mem0 sync in the project namespace, infer=False (for retrieval only)
  → claim extraction per section (extractor role): text, kind, locator, verbatim quote
  → Python: quote must occur in the cited section (same normalisation as CANON-002)
  → conflict detection: candidate pairs by similarity → single-claim judge "do these disagree?" →
       both claims kept, each lists the other in conflicts_with, support = "contested"
  → claims.jsonl
planning: the topic/segment planner retrieves claims; each segment card lists claim_ids
writing:  the writer receives the claims' text and support level; contested and unsupported claims
          carry the instruction to say so aloud and attribute ("one account says … another …")
editorial: extractor lists factual statements in the script → each must map to a claim_id;
          unmapped → "unsupported claim" (error for documentary/educational, warning for conversational);
          a figure or date differing from its claim → error; a quotation not matching a cited quote → error
publishing: show notes list sources; transcript keeps claim markers; rights report lists research sources
```

**Contradictory factual sources are never averaged or silently resolved.** Options are: present both with attribution, prefer one with the reason stated in the script, or leave the point out. The choice is recorded on the segment card. A human can mark a claim `verified_by: human`.

External verification ("verify important claims where appropriate") is optional and explicit: `reference verify --claim CL-…` may run a web search through whatever search tool the deployment has and attach further citations; without it, support stays at what the supplied sources give.

## D6. Removal, deletion and history

| User action | References library | Derived data | Published / approved canon | Provenance |
|---|---|---|---|---|
| Disable | `enabled: false` | Kept | Untouched | Audit line |
| Change influence | Binding updated | Kept | Untouched; only **unpublished** scenes regenerate with the new style | Audit line with old and new values |
| Remove from future generation | `removed_at` set | Kept but excluded from every query | Untouched | Audit line |
| Purge extracted information | `purged_at` set | Deleted: profiles, unreferenced claims, Mem0 entries for the source, cached text | Untouched. Canon events with `origin: "source"` and claims cited by an approved episode are **kept**, marked `source_purged: true` | Source record (title, hash, rights, attribution) and audit log are kept |
| Delete project | Whole project folder archived then deleted on confirmation | Deleted | Published episodes remain on the host; the rights report archive is kept if anything was published | Archive manifest |

Approved and published episodes store the **resolved style and the binding snapshot** they were generated with (`episodes/<id>/reference_snapshot.json`), so later changes cannot alter the record of how they were made, and regenerating an unpublished scene uses the current configuration while everything approved stays as it is (test T19).

## D7. World-building and adaptation

- World extraction reuses `SeriesBibleExtractor` with a generic prompt, per source, sampling by the source's own headings rather than fixed queries. Output: entities (characters with profile stubs, places, rules) and events.
- Source-established facts enter the ledger as `CanonEvent(origin="source", source_id=…, status="canon")` with `evidence.episode_id = "REF:<source_id>"` and locators as `line_ids`; quotes are verified against the source text. Everything extracted from generated episodes is `origin="generated"`. `canon show --origin source|generated` separates them. A generated event may not contradict a source event without an explicit correction.
- Adaptation: the planner receives the source's chapter summaries as the *story to adapt*; each scene card records `adapts: {source_id, locator}`; raw source passages may be shown to the writer for the scene being adapted. `attribution_text` is carried into show notes and the rights report.
- With `unspecified` rights neither mode can be created. `PUB-003` blocks publishing when any enabled world/adaptation source lacks `owned`, `licensed` or `public_domain`.

## D8. Integration points

| Existing or planned component | Integration |
|---|---|
| `epub_processor.process_epub` | Called by `reference add` for EPUB; new sibling loaders for other formats |
| `reference_memory_sync.sync_book` | Gains `project_id`, `source_id`, `purpose`; skipped for technique-only sources |
| `book_knowledge.KnowledgeContext` | Constructed per project; `build_system_prompt` emits rendered directives; `get_rag_context` returns claims (research) or adaptation passages, never chunks from technique sources |
| `book_style_analysis.BookStyleAnalyzer` | Statistics and name list reused |
| Context assembler (`STORYOS-003`) | New sections: "style directives" (all modes), "claims for this segment" (claims modes), "source-established canon" (world mode) |
| Scene/segment writer prompts | Receive directives; never bindings or source metadata |
| Canon store (`CANON-001`) | `origin`, `source_id` fields (added to `reference/canon_models.py`) |
| Editorial (`QUALITY-001`) | Factual checks; pastiche item |
| Job runner (`AUTO-001`) | Stage hashes include the resolved style and binding snapshot, so a changed influence invalidates only unpublished writing stages |
| Rights gate (`PUB-003`) | Reads source rights and purposes |

---

# E. Cursor roadmap changes

Summary; the roadmap file is updated in place.

| Task | Status | What changed |
|---|---|---|
| BASE-001, BASE-002 | UNCHANGED | — |
| BASE-003 | MODIFIED | Wider file list (A4); `show_profile` → generic `format` block; `use_book_rag` superseded by reference purposes; `species` optional |
| GEN-001 Project config, production modes, one-sentence creation | NEW | Phase 1, before STORYOS-001 |
| STORYOS-001 | MODIFIED | Adds the project layer and `project_id` on everything; notes the third series registry |
| GEN-003 Project isolation for Mem0, voices, metadata | NEW | Phase 1 |
| STORYOS-002 | MODIFIED | Roadmap type by `season_plan` capability; arc roadmap unchanged for serialized fiction |
| STORYOS-003 | MODIFIED | Assembler sections by capability; style directives section |
| REF-001 Reference registry on the existing ingestion path | NEW | Phase 1b |
| REF-002 Technique profiles and influence control | NEW | Phase 1b |
| REF-003 Factual research: claims, citations, conflicts | NEW | Phase 2 |
| REF-004 Authorised world building and adaptation | NEW | Phase 2 (after CANON-001) |
| REF-005 Reference lifecycle and snapshots | NEW | Phase 2 |
| CANON-001 | MODIFIED | `origin`, `source_id`; store created only when the mode's continuity needs it |
| CANON-002, CANON-003, CANON-004 | UNCHANGED (mode-gated by GEN-001) | Run only for capabilities that need them |
| CANON-005 | MODIFIED | Namespaces per project (with GEN-003) |
| PLAN-001 | MODIFIED | Planner per `season_plan` type: arc (as specified), slate, curriculum, none |
| PLAN-002, PLAN-003 | UNCHANGED (serialized fiction only) | — |
| NARRATIVE-001 | UNCHANGED | One prompt string neutralised in the reference file; fiction modes only |
| GEN-002 Nonfiction pipeline: segment cards, factual editorial | NEW | Phase 4 |
| NARRATIVE-002 | MODIFIED | Registry gains three families |
| NARRATIVE-003 | MODIFIED | Writer prompt takes rendered style directives |
| CHAR-001 | MODIFIED | Cast styles; host personas |
| QUALITY-001, QUALITY-004 | MODIFIED | Rule sets by editorial profile |
| QUALITY-002, QUALITY-003, WRITERS-001 | UNCHANGED | — |
| AUDIO-001, 002, 003, 004, 007 | UNCHANGED | — |
| AUDIO-005 | MODIFIED | Generic sound categories |
| AUDIO-006 | MODIFIED | Voices namespaced by show |
| AUDIO-008 | MODIFIED | Identities and location registry per show, any setting |
| AUTO-001 | MODIFIED | Stage list from the mode; `create-podcast` front end is in GEN-001 |
| PUB-001 | MODIFIED | Sources in show notes; chapters from segments |
| PUB-002 | MODIFIED | Extends `episode_metadata.generate_episode_feed`; `itunes:type` from the mode |
| PUB-003 | MODIFIED | Checks reference rights and purposes |
| `use_book_rag` (flag inside BASE-003) | SUPERSEDED | By REF-001/002 |

New dependencies: `GEN-001 → STORYOS-001 → GEN-003`; `GEN-001 → REF-001 → REF-002`; `REF-001 → REF-003 → GEN-002`; `CANON-001 → REF-004`; `REF-001 → REF-005`; `GEN-001 → {STORYOS-002, PLAN-001, NARRATIVE-002, CHAR-001, QUALITY-001, AUTO-001}`.

No existing serialized-fiction capability is removed or reduced. With `mode = serialized_fiction` the plan is the first handoff's plan plus project scoping.

---

# F. New tests

Added to doc 12 as T15–T22 with fixtures and pass/fail examples:

| Brief | ID | Proves |
|---|---|---|
| A | T15 | Prompt-only creation with empty `books/`, no Mem0, no references |
| B | T16 | Technique reference imports no names, places or plot |
| C | T17 | Two references, deterministic precedence, full trace |
| D | T18 | Three unrelated projects stay isolated in every store |
| E | T19 | Influence change regenerates only unpublished work; canon intact |
| F | T20 | All references disabled → baseline path works |
| G | T21 | Educational script: every claim cited, uncertainty flagged |
| H | T22 | Continuing original fiction keeps character and season continuity (composition of T02–T08 on an original, non-SF project) |

Existing T01–T14 are unchanged.

---

# G. Updated Cursor master handoff

`14_CURSOR_MASTER_EXECUTION_PROMPT.md` has been updated in place: product statement, reading order (this document added), order of work (`GEN-001` after Phase 0), new rules (project isolation, reference purposes, no technique-source text in prompts, mode capabilities instead of mode-name tests), and revised phase prompts. It remains a single prompt; nothing from the earlier version was dropped.

## Verification status of this delta

| Item | Status |
|---|---|
| `reference/reference_models.py` — schemas, rights gate, blending, isolation, directive rendering, claim support levels | **Executed**: `OK reference_models` |
| `reference/canon_models.py` with `origin`, `source_id` | **Executed**: `OK canon_models`; earlier JSON examples still validate |
| `reference/scene_cards.py` with the neutral prompt string | **Executed** in the scratch copy: 21 passed |
| Ingestion findings and franchise table | **OBSERVED** in source |
| Mode proposal, nonfiction pipeline, technique extraction quality, claim extraction accuracy | **Proposed; not run** — no LLM in the research environment |
| Whether closed-vocabulary directives produce an audible stylistic difference | **Unverified** — test T19 checks that configuration is applied, not that listeners perceive it |
