# 11 — Exact Change Specifications

Line numbers refer to commit `c32a96570512a5b56af96e05eb8b13ce95bb1eec`. Re-locate by function name if the file has moved on.

**Conventions**

- Every change is behind a flag or is behaviour-preserving, so the legacy path stays runnable.
- Code marked **VERIFIED** was executed in a scratch copy of the repository on 2026-11-11. Code marked **SKETCH** is realistic but was not run. Pseudocode is labelled.
- "Existing function" names were checked against the source. New names are marked *(new)*.
- Test command prefix everywhere: `STARDOCK_DISABLE_MEM0=1 python -m pytest`.
- Verification status vocabulary: `proposed` → `implemented` → `tested`. Everything here is `proposed` unless a field says otherwise.
- All new JSON writes go through one helper, `story_os.store.atomic_write_json(path, obj)` *(new, STORYOS-001)*: write to `path.tmp`, `os.replace`.

**Index**

| ID | Title | Priority | Phase | Delta status |
|---|---|---|---|---|
| BASE-001 | Repair the failing test module | P0 | 0 | UNCHANGED |
| BASE-002 | LLM client and role-based model config | P0 | 0 | UNCHANGED |
| BASE-003 | Remove franchise text from code; make book knowledge optional | P0 | 0 | MODIFIED |
| STORYOS-001 | Single show store keyed by `show_id`; stable character IDs | P0 | 1 | MODIFIED |
| STORYOS-002 | Unified season roadmap | P0 | 1 | MODIFIED |
| STORYOS-003 | Context assembler; flag clean-up | P1 | 1 | MODIFIED |
| CANON-001 | Canon models, ledger store, SQLite index | P0 | 2 | MODIFIED |
| CANON-002 | Evidence-cited extraction with verification | P0 | 2 | UNCHANGED |
| CANON-003 | Beliefs and the omniscience check | P1 | 2 | UNCHANGED |
| CANON-004 | Promises with horizons and judged closure | P1 | 2 | UNCHANGED |
| CANON-005 | Mem0 as a derived index (`infer=False`) | P1 | 2 | MODIFIED |
| PLAN-001 | Season creation with commitments, mystery solutions, validation | P1 | 3 | MODIFIED |
| PLAN-002 | Rolling episode planner and replanning | P1 | 3 | UNCHANGED |
| PLAN-003 | Series plan | P3 | 3 | UNCHANGED |
| NARRATIVE-001 | Scene cards and sequential causal writing (**Example 8**) | P0 | 4 | UNCHANGED |
| NARRATIVE-002 | Framework registry and selection | P1 | 4 | MODIFIED |
| NARRATIVE-003 | Per-character briefs and cue syntax in the writer prompt | P1 | 4 | MODIFIED |
| CHAR-001 | Character profiles, derived state, arc steps | P1 | 4 | MODIFIED |
| QUALITY-001 | Lint, editor pass, bounded revision | P1 | 5 | MODIFIED |
| QUALITY-002 | Originality metrics | P2 | 5 | UNCHANGED |
| QUALITY-003 | Pairwise judge | P1 | 5 | UNCHANGED |
| QUALITY-004 | Audio-first clarity lint | P2 | 5 | MODIFIED |
| WRITERS-001 | Candidate premises | P2 | 5 | UNCHANGED |
| AUDIO-001 | Per-line cache and word alignment | P0 | 8 | UNCHANGED |
| AUDIO-002 | Cue syntax, timeline model, resolver | P0 | 6/8 | UNCHANGED |
| AUDIO-003 | Multitrack mixer | P0 | 8 | UNCHANGED |
| AUDIO-004 | Mastering and audio QA | P1 | 8 | UNCHANGED |
| AUDIO-005 | Asset library and cue resolution | P1 | 8 | MODIFIED |
| AUDIO-006 | TTS provider registry, `voice_id`, licence gate, benchmark | P1 | 7 | MODIFIED |
| AUDIO-007 | SFX and music providers | P2 | 7 | UNCHANGED |
| AUDIO-008 | Sound identities tied to canon | P2 | 6 | MODIFIED |
| AUTO-001 | Job runner, `produce-episode`, resume | P1 | 9 | MODIFIED |
| PUB-001 | Publish assets | P2 | 10 | MODIFIED |
| PUB-002 | Host interface, dry run, Transistor adapter | P2 | 10 | MODIFIED |
| PUB-003 | Rights gate | P1 | 10 | MODIFIED |
| GEN-001 | Project config, production modes, one-sentence creation | P0 | 1 | NEW |
| GEN-003 | Project isolation: memory, voices, metadata | P0 | 1 | NEW |
| REF-001 | Reference registry on the existing ingestion path | P1 | 1 | NEW |
| REF-002 | Technique profiles and influence control | P1 | 1 | NEW |
| REF-003 | Factual research: claims, citations, conflicts | P1 | 2 | NEW |
| REF-004 | Authorised world building and adaptation | P2 | 2 | NEW |
| REF-005 | Reference lifecycle and generation snapshots | P1 | 2 | NEW |
| GEN-002 | Nonfiction pipeline: segment cards and factual editorial | P1 | 4 | NEW |

**Delta status** refers to the universal-scope correction (doc 16). MODIFIED specs must be read together with their amendment in the section "Amendments for universal scope" near the end of this file; where an amendment and the original text disagree, the amendment wins. NEW specs follow the amendments.

---

## BASE-001 — Repair the failing test module

**Priority:** P0
**Current behavior:** `pytest tests` → 6 failed, 6 passed (OBSERVED).
**Source evidence:** `tests/test_story_structure.py:48` patches `story_structure.search_references`; `story_structure.py:28` imports `get_knowledge_context` instead.
**Problem:** No trustworthy baseline; every later change would be judged against a red suite.
**Root cause:** The module was refactored to three-tier knowledge; the test mock was not updated.
**Desired behavior:** 12 pass.
**Proposed architecture:** Patch `get_knowledge_context` and give the mock the four attributes `StoryStructure` uses.
**Files to change:** `tests/test_story_structure.py`. **Files to create:** `pytest.ini`.
**Dependencies:** `pytest`, `pytest-asyncio` (already in `requirements.txt`).
**Database/schema changes:** None.
**Implementation instructions:**
1. Apply `reference/patches/BASE-001_fix_story_structure_tests.patch` (`git apply`).
2. Create `pytest.ini`: `[pytest]` / `testpaths = tests` / `asyncio_default_fixture_loop_scope = function` / `python_files = test_*.py`.
3. Run the suite; record the result in `Docs/handoff/PROGRESS.md`.

**Code example (VERIFIED — suite went 6/6 → 12/0 with exactly this):**
```python
self.knowledge_patcher = patch('story_structure.get_knowledge_context')
...
self.mock_knowledge = self.knowledge_patcher.start()
self.mock_knowledge.return_value.series_bible = {}
self.mock_knowledge.return_value.is_ready.return_value = True
self.mock_knowledge.return_value.get_rag_context.return_value = ''
self.mock_knowledge.return_value.build_system_prompt.side_effect = lambda base: base
...
self.knowledge_patcher.stop()
```
**Existing-system compatibility:** Test-only. **Migration:** None.
**Test procedure:** `STARDOCK_DISABLE_MEM0=1 python -m pytest tests -q`
**Expected output:** `12 passed`. **Failure conditions:** any failure or error; any test skipped.
**Rollback:** `git revert`. **Dependencies on other changes:** None.
**Acceptance criteria:** 12 pass on a clean checkout with only `requirements.txt` test dependencies plus `pydantic`, `openai`, `mem0ai`, `python-dotenv` installed.
**Verification status:** patch **tested** in a scratch copy; **proposed** for the repository.

---

## BASE-002 — LLM client and role-based model config

**Priority:** P0
**Current behavior:** Model names are literals: `anthropic/claude-opus-4.5` and `gpt-4o` in `story_structure.py` (`:191, :206, :374, :386, :552, :569, :1045, :1058, :1362, :1385`), `quality_checker.py:715`, `script_editor.py:351`, `show_os/seasons.py:91, :94`, and in `book_knowledge.py`, `show_os/new_show.py`, `story_pipeline_agent.py`.
**Source evidence:** `grep -rn "claude-opus\|gpt-4o" --include=*.py .` (7 files). `StoryStructure.complete_text` (`:181–217`) is the only shared helper.
**Problem:** Writer, editor, extractor and judge cannot be different models by design; changing a model is a 7-file edit; the judge needs an OpenAI key even when generation uses OpenRouter.
**Root cause:** Each module builds its own client.
**Desired behavior:** One call site: `llm.complete(role, system, user, *, json=False, max_tokens=None, temperature=None) -> str`. Roles map to provider/model in `data/llm_config.json`. Defaults reproduce today's behaviour.
**Proposed architecture:** `story_os/llm.py` *(new)* with a lazy singleton; providers `openrouter` and `openai` through the existing `openai` SDK (`base_url` switch as today); retries (3, exponential), per-call trace through `generation_trace.log_step`; token usage returned on `llm.last_usage`.
**Files to change:** `story_structure.py` (`complete_text` delegates), `quality_checker.py`, `script_editor.py`, `book_knowledge.py`, `show_os/new_show.py`, `show_os/seasons.py`, `story_pipeline_agent.py`. **Files to create:** `story_os/llm.py`, `data/llm_config.json`, `tests/test_llm_config.py`.
**Dependencies:** None new.
**Database/schema changes:** `data/llm_config.json` (shape in doc 04 §6). Missing file → built-in defaults: every role = today's models (`openrouter: anthropic/claude-opus-4.5`, fallback `openai: gpt-4o`).
**Implementation instructions:**
1. Create `story_os/llm.py` with `load_config()`, `complete()`, `acomplete()`, `set_test_backend(fn)` (lets tests inject a function `(role, system, user, **kw) -> str`).
2. Make `StoryStructure.complete_text(system, user, max_tokens)` call `llm.complete('writer', …)`; keep its signature (the agentic pipeline and the scene-card patch call it).
3. Replace each inline `self.client.chat.completions.create(…)` in `story_structure.py` one function at a time (`_generate_title` → `planner`, `generate_character_cast` → `planner`, `_generate_scene_outline` → `planner`, `_generate_scene_script` → `writer`). Keep `self.client` and `self.async_client` attributes until the last call site is gone, because tests patch them.
4. `quality_checker._evaluate_script_with_ai` → role `editor`; `script_editor.regenerate_scene` → role `writer`; `show_os` and `book_knowledge` → role `planner` / `extractor`.
5. Read the config path through `config.paths.DATA_DIR`.

**Code example (SKETCH):**
```python
# story_os/llm.py
_DEFAULTS = {'roles': {r: {'provider': 'openrouter', 'model': 'anthropic/claude-opus-4.5',
                           'temperature': t}
                       for r, t in [('planner', .7), ('writer', .8), ('editor', .3),
                                    ('extractor', 0.), ('judge_a', 0.), ('judge_b', 0.)]},
             'fallback': {'provider': 'openai', 'model': 'gpt-4o'}}
_test_backend = None

def complete(role, system, user, *, json=False, max_tokens=None, temperature=None) -> str:
    if _test_backend is not None:
        return _test_backend(role, system, user, json=json, max_tokens=max_tokens)
    spec = _resolve(role)                    # falls back when the provider's key is missing
    client = _client_for(spec['provider'])   # OpenAI(base_url=…) as in story_structure.py:158–166
    kwargs = {'model': spec['model'], 'temperature': temperature if temperature is not None
              else spec.get('temperature', 0.7),
              'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    if max_tokens: kwargs['max_tokens'] = max_tokens
    if json and spec['provider'] == 'openai': kwargs['response_format'] = {'type': 'json_object'}
    return _with_retries(lambda: client.chat.completions.create(**kwargs)).choices[0].message.content or ''
```
**Existing-system compatibility:** With no config file the same models are called with the same parameters.
**Migration:** None; optionally write the default config with `python main.py llm-config --init` *(new command)*.
**Test procedure:** `pytest tests/test_llm_config.py tests -q`; `grep -rn "claude-opus\|gpt-4o" --include=*.py . | grep -v story_os/llm.py` → empty.
**Expected output:** all pass; grep empty.
**Failure conditions:** any module still constructing its own model string; a role missing from defaults; behaviour change with no config file (assert in a test that the resolved model for `writer` equals today's literal).
**Rollback:** revert; delete `data/llm_config.json`.
**Dependencies on other changes:** BASE-001.
**Acceptance criteria:** editor and judge roles can be pointed at a different model family by editing one JSON file, with no code change.
**Verification status:** proposed.

---

## BASE-003 — Remove franchise text from code; make book knowledge optional

**Priority:** P0
**Current behavior:** Prompts and narration contain Star Trek wording: `story_structure.py:358` ("Star Trek-style podcast episode title"), `:492`, `:557`, `:574`, `:725`, `:1009`, `:1341` ("Star Trek audio drama scene"); `quality_checker.py:687`; `book_knowledge.py:50–108, 202–211`; `audio_pipeline.py:992–997` (intro narration naming a ship and quadrant), `:1036–1039`; `tts_engine.py:268, 417` (`normalize_trek_tts_text`). `new_show.py:124–130` raises without ingested books.
**Source evidence:** `grep -rnic "star trek\|starfleet\|stardate\|Celestial Temple\|Gamma Quadrant" --include=*.py .`
**Problem:** Original shows are steered toward one franchise; an original show cannot be created without source novels; raw novel chunks enter every scene prompt.
**Root cause:** The project began as a single-franchise tool.
**Desired behavior:** Code contains no franchise terms. Each show carries a `show_profile` used to fill prompts. Book knowledge is optional and, for shows marked `original: true`, contributes style descriptors only.
**Proposed architecture:** `show_profile` block inside the show's `series_bible.json`; `story_os/profile.py` *(new)* with `get_profile(show_id) -> ShowProfile` and `render(template, profile)`.
**Files to change:** all files listed above; `tts_pronunciation.py` (rename function, lexicon from the profile). **Files to create:** `story_os/profile.py`, `tests/test_profile_prompts.py`.
**Dependencies:** BASE-002 helps but is not required.
**Database/schema changes:**
```json
"format": {
  "original": true,
  "writer_persona": "an expert audio scriptwriter",
  "cast_designer_persona": "a character designer for audio productions",
  "title_prompt_noun": "episode title for this podcast",
  "outline_noun": "scene outline",
  "script_noun": "script for an audio scene",
  "genre_phrase": "an original gothic-horror audio drama",
  "intro_template": "{show_name}. Season {season}, episode {episode}: {title}.",
  "outro_template": "You have been listening to {show_name}.",
  "pronunciation_lexicon": {"Oyelaran": "oh-yeh-LAH-ran"},
  "number_rules": []
}
```
(Amended for universal scope: the block is named `format`, has no universe- or log-specific keys, and no `use_book_rag` — reference use is decided by reference purposes, REF-001/002. `genre_phrase` is generated from `ProjectConfig.genre` and `mode`. The loader also accepts the earlier name `show_profile`.)
For the existing `star_trek_horizon` show the migration writes a `format` block whose values reproduce today's strings exactly (`genre_phrase: "a Star Trek-style podcast episode"`, the Captain's-log intro template with a stardate `number_rules` entry, the Trek pronunciation lexicon, `original: false`), and registers its ingested books as legacy references with purposes `writing_techniques` + `world_building` and rights `unspecified` — which keeps them usable privately and blocks publishing.
**Implementation instructions:**
1. Add `ShowProfile` (Pydantic) and loader; default profile = neutral wording when a show has none.
2. Replace each literal with `profile.<field>`; one commit per file.
3. `audio_pipeline._generate_intro_narration` / `_generate_outro_narration`: build text from the templates; write the intro narration under the episode's audio folder, not `assets/music/intro_narration.wav`.
4. `KnowledgeContext.get_rag_context`: return `''` when `use_book_rag` is false; `build_system_prompt` keeps style descriptors only.
5. `ShowCreator.create_show`: when no book-derived bible exists, start from an empty bible plus the user's concept instead of raising.
6. Rename `normalize_trek_tts_text` → `normalize_tts_text(text, lexicon)`; keep the old name as an alias.

**Code example (SKETCH):** `user_prompt = f"Generate {profile.genre_phrase} title."`
**Existing-system compatibility:** Golden test: for the migrated Star Trek profile, the rendered title, scene and script prompts equal the pre-change strings byte for byte (capture them before editing).
**Migration:** part of `migrate-shows` (STORYOS-001); until then the default profile is the Star Trek one, so nothing changes.
**Test procedure:** `pytest tests/test_profile_prompts.py -q`; the grep above excluding `tests/` and `story_os/migrate.py`.
**Expected output:** golden prompts equal; grep empty; `new-show` succeeds in an empty data directory with the LLM stubbed.
**Failure conditions:** any franchise word in non-test code; golden mismatch; `new-show` still requiring books.
**Rollback:** revert; profiles are additive.
**Dependencies on other changes:** BASE-001.
**Acceptance criteria:** creating a show named "Meridian Drift" produces prompts with no franchise wording and no book chunks.
**Verification status:** proposed.

---

## STORYOS-001 — Single show store keyed by `show_id`; stable character IDs

**Priority:** P0
**Current behavior:** Three locations hold show state (doc 01 §3B). The prompt-injected bible is a global file. Story OS folders are keyed by the slug of the episode's `series` string. Character IDs are regenerated per episode (`story_structure.py:613–616`). `StoryStructure` defaults to `Path("episodes")` (`:134–141`); flags, Mem0 config, trace logs and voice config use working-directory-relative paths.
**Source evidence:** `book_knowledge.py:41, 308–309`; `show_os/new_show.py:164–165`; `story_os/io.py:22–26`; `story_os/flags.py:10`; `mem0_client.py:55`; `generation_trace.py:21`.
**Problem:** Two shows cannot coexist; planners cannot find each other; nothing can be joined on character.
**Root cause:** Show OS and Story OS were added separately on top of a single-show global.
**Desired behavior:** `data/shows/<show_id>/` owns the show. Episodes store `show_id`, `season_number`, `episode_number`. Characters have permanent IDs `C01…`. All paths honour `STARDOCK_*_DIR`.
**Proposed architecture:** `story_os/store.py` *(new)*: `ShowStore(show_id)` with `bible()`, `save_bible()`, `profile()`, `characters()`, `character(cid)`, `show_state()`, `season_dir(n)`, `canon_dir()`, `resolve_show_id(episode) -> str`; module functions `active_show_id()`, `set_active_show(show_id)`, `atomic_write_json()`. `story_os/io.py` functions keep their signatures and delegate (the `series_id` argument is resolved to a `show_id` through a `slug → show_id` map in `data/shows/index.json`).
**Files to change:** `story_os/io.py`, `story_os/context.py`, `story_os/flags.py`, `show_os/new_show.py`, `show_os/seasons.py`, `story_structure.py` (`__init__`, `generate_episode_structure`, `_load_bible_cast`, `_load_past_guests`, `_save_guests_to_show_state`), `book_knowledge.py` (`KnowledgeContext.__init__` takes `show_id`), `mem0_client.py`, `generation_trace.py`, `dialogue_engine.py`, `cli_entrypoint.py`. **Files to create:** `story_os/store.py`, `story_os/migrate.py`, `tests/test_show_store.py`, `tests/test_migrate_shows.py`.
**Dependencies:** None new.
**Database/schema changes:**
- `data/active_show.json`: `{"show_id": "…"}`.
- `data/shows/index.json`: `{"slugs": {"main_series": "star_trek_horizon", "star_trek_horizon": "star_trek_horizon"}}`.
- `main_cast[i].character_id` added to the bible (assigned in order: `C01`, `C02`, …); `characters/C01.json` created from each cast entry (minimal `CharacterProfile`; richer fields come in CHAR-001).
- `structure.json` gains `show_id`, `season_number`.
**Implementation instructions:**
1. Write `store.py` and tests (round-trip, atomic write, slug resolution, unknown show error).
2. `ShowCreator.create_show`: write only under `data/shows/<id>/`; then `set_active_show`; still write `data/series/series_bible.json` as a mirror (compatibility).
3. `KnowledgeContext`: load the bible via `ShowStore(active or given show_id)`; fall back to the global file.
4. `StoryStructure.__init__`: default `episodes_dir` to `config.paths.EPISODES_DIR`; `mkdir(parents=True, exist_ok=True)`.
5. `generate_episode_structure`: resolve `show_id` (explicit arg → `series` via index → active show), store it; stop creating new IDs for permanent cast in `_load_bible_cast` — use `character_id` from the bible.
6. Point `FLAGS_PATH`, Mem0 config, trace dir and `voice_config.json` at `config.paths`.
7. Write `migrate.py` (see Migration) and the CLI command `migrate-shows [--dry-run] [--rollback <manifest>]`.

**Code example (SKETCH):**
```python
def atomic_write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, path)

def resolve_show_id(episode: dict) -> str:
    if episode.get('show_id'):
        return episode['show_id']
    idx = _load_index()
    slug = slugify_series(episode.get('series') or '')      # existing: story_os.io.slugify_series
    return idx['slugs'].get(slug) or active_show_id()
```
**Existing-system compatibility:** Old episodes without `show_id` resolve through the slug index, then the active show. `data/series/<slug>/` is read if the show folder lacks a file. The global bible mirror keeps any external script working.
**Migration (`migrate-shows`):**
1. Dry run prints the plan and conflicts; writes nothing.
2. Back up `data/shows`, `data/series` to `backups/migrate-<timestamp>.tar.gz`; write a manifest of every file created or changed.
3. For each show folder: assign `character_id`s; write `characters/`; add `show_profile` (BASE-003).
4. For each `data/series/<slug>/` folder: map the slug to a show (same slug → same show; otherwise ask, or `--map slug=show_id`); copy `show_state.json` fields that the show lacks into `show_state.json` under a `legacy_story_os` key; copy `episode_slots/` and `season_plan.json` to `seasons/legacy/`. Leave originals in place.
5. For each episode: add `show_id`, `season_number` (from `arc_slot` if present, else 1); rewrite permanent-cast `character_id`s to the stable ones by name match; keep the old ID in `legacy_character_id`.
6. Write `data/active_show.json` and `data/shows/index.json`.
**Test procedure:** `pytest tests/test_show_store.py tests/test_migrate_shows.py -q`; `python main.py migrate-shows --dry-run`.
**Expected output:** dry run on the committed data lists `star_trek_horizon` (8 cast → `C01–C08`) and `test_series` with no conflicts; second run after migration reports "nothing to do".
**Failure conditions:** migration not idempotent; a character matched to two IDs; any write outside the manifest; legacy episode fails to load.
**Rollback:** `migrate-shows --rollback <manifest>` restores from the tarball; code revert.
**Dependencies on other changes:** BASE-001; BASE-003 for the profile step.
**Acceptance criteria:** two shows exist side by side and each episode's prompts use its own bible (test with two stub shows).
**Verification status:** proposed.

---

## STORYOS-002 — Unified season roadmap

**Priority:** P0
**Current behavior:** Two unrelated plans (doc 01 §3A). `arc_slot` is copied into the episode at creation (`story_structure.py:265–295`) and reaches only the script prompt (`:1300–1311`). `story_os/planner.py:43–44` samples beat indices.
**Source evidence:** as cited; probe output doc 01 §4.2.
**Problem:** Outlining never sees the season's needs; plan edits do not propagate; beat sampling drops Catalyst/Finale.
**Root cause:** Parallel implementations.
**Desired behavior:** One `SeasonRoadmap` per season (`reference/canon_models.py`), read live at planning time.
**Proposed architecture:** `story_os/roadmap.py` *(new)*: `load_roadmap(show_id, season)`, `save_roadmap(roadmap, reason)` (bumps `version`, writes history), `import_season_plan(show_id, season)`, `milestone_for(show_id, season, episode)`, `validate_roadmap(roadmap, cast_ids) -> list[str]`.
**Files to change:** `show_os/seasons.py` (`create_season` also writes the roadmap; `get_episode_slot` reads it first), `story_structure.py` (`generate_episode_structure` stores coordinates, not a copy; `_generate_scene_outline`, `_generate_scenes_from_cards`, `_generate_scene_script` call `milestone_for`), `story_os/context.py`, `story_os/planner.py` (deprecation warning), `cli_entrypoint.py` (`roadmap show|diff|lock|restore`). **Files to create:** `story_os/roadmap.py`, `tests/test_roadmap.py`.
**Dependencies:** STORYOS-001.
**Database/schema changes:** `seasons/<N>/roadmap.json`, `roadmap_history/v0001.json`. `EpisodeMilestone` adds to the reference model: `structural_role: Literal['inciting','midpoint_reversal','low_point','climax','none'] = 'none'`, `obstacle_type: Optional[str]`.
**Implementation instructions:**
1. Copy `SeasonRoadmap`, `EpisodeMilestone`, `RoadmapChange` from the reference file into `story_os/canon_models.py` (or `roadmap.py` until CANON-001 lands); add the two fields.
2. `import_season_plan`: map `episode_beats[i]` → milestone (`purpose=''`, `commitment='guided'`, `status='planned'`); `dramatic_question=''`.
3. `validate_roadmap` rules (doc 06 §4 step 4); rules needing fields that are empty on imported plans are reported as warnings, not errors.
4. `get_episode_slot` returns the same dict keys as today (`arc_beat`, `tension_level`, `arc_importance`, `arc_title`, `arc_summary`) plus the new ones, so existing readers work.
5. In `story_structure.py`, replace reads of `episode.get('arc_slot')` with a helper `_milestone(episode)` that calls `milestone_for` and falls back to the stored `arc_slot`.
6. Pass the milestone into the outline prompts (legacy and cards).

**Code example (SKETCH):**
```python
def save_roadmap(rm: SeasonRoadmap, changes: list[RoadmapChange]) -> SeasonRoadmap:
    old = load_roadmap(rm.show_id, rm.season)
    if old:
        frozen = old.frozen_through()
        for a, b in zip(old.episodes, rm.episodes):
            if a.episode_number <= frozen and a != b:
                raise ValueError(f'episode {a.episode_number} is frozen')
            if a.commitment == 'locked' and (a.arc_beat, a.purpose) != (b.arc_beat, b.purpose):
                raise ValueError(f'episode {a.episode_number} is locked')
        rm.version = old.version + 1
    rm.revision_log.extend(changes)
    atomic_write_json(path, rm.model_dump()); atomic_write_json(history_path(rm), rm.model_dump())
    return rm
```
**Existing-system compatibility:** `season_plan.json` remains and is still written; episodes with a stored `arc_slot` and no roadmap behave as today.
**Migration:** `roadmap import --show <id> --season N` (also run by `migrate-shows`). The committed 10-episode plan imports to 10 guided milestones.
**Test procedure:** `pytest tests/test_roadmap.py -q` — import of the committed plan; frozen/locked guards; validator on three seeded bad roadmaps (no midpoint; duplicate episode numbers; clue scheduled after its payoff).
**Expected output:** pass; import produces `version == 1`, 10 milestones.
**Failure conditions:** a frozen or locked milestone can be changed; old keys missing from `get_episode_slot`.
**Rollback:** delete `roadmap.json` → code falls back to `season_plan.json`.
**Dependencies on other changes:** STORYOS-001.
**Acceptance criteria:** editing a future milestone changes the next outline prompt for that episode without touching the episode file.
**Verification status:** proposed.

---

## STORYOS-003 — Context assembler; flag clean-up

**Priority:** P1
**Current behavior:** Three context paths: `get_previous_episode_context` (`episode_memory.py:737–804`), `build_prompt_enrichment` (`story_os/context.py:18–95`, re-reading files per scene), `arc_slot`. Flags `USE_DIA2_DIALOGUE`, `USE_BARK_SFX` have no readers.
**Source evidence:** as cited; grep for `feature_enabled(`.
**Problem:** Duplicated, unbudgeted context; opaque `Primary beat id: stc_N`.
**Root cause:** Incremental additions.
**Desired behavior:** `assemble_context(show_id, season, episode, purpose, scene=None) -> Context` with sections and token budgets (doc 04 §5), cached per episode.
**Proposed architecture:** `story_os/assembler.py` *(new)*; `Context.render(order, budget)`; a rough token estimate (`len(text) // 4`) is enough for budgeting.
**Files to change:** `story_os/context.py` (`build_prompt_enrichment` becomes a thin wrapper), `story_structure.py` (callers), `data/feature_flags.json` (remove two dead flags; add the new ones from doc 04 §8, all false), `Docs/Docs_New/WORKFLOW.md`. **Files to create:** `story_os/assembler.py`, `tests/test_assembler.py`.
**Dependencies:** STORYOS-002. Ledger-backed sections return empty until CANON-001/002.
**Database/schema changes:** None.
**Implementation instructions:** 1. Implement sections as functions returning `(title, text)`. 2. Truncate each to its budget at sentence boundaries. 3. Never include `mystery_solutions.json` unless `purpose == 'plan'`. 4. Cache by `(episode_id, purpose, roadmap.version, ledger mtime)`. 5. Replace the `stc_N` line with the milestone text.
**Code example (pseudocode):** `ctx = assemble_context(...); prompt = ctx.render(['identity','season','milestone','previous','characters','knowledge','promises','repetition'], budget=3500)`
**Existing-system compatibility:** With all new flags off, `build_prompt_enrichment` returns the same string as before (golden test).
**Migration:** None.
**Test procedure:** `pytest tests/test_assembler.py -q` (budget respected; solutions excluded for `purpose='write'`; golden legacy string).
**Expected output:** pass. **Failure conditions:** budget exceeded by > 10%; solution text present in a writer context.
**Rollback:** revert. **Dependencies on other changes:** STORYOS-001, STORYOS-002.
**Acceptance criteria:** one function builds all story prompts' context.
**Verification status:** proposed.

---

## CANON-001 — Canon models, ledger store, SQLite index

**Priority:** P0
**Current behavior:** No event record. `ShowState.world_facts`/`active_threads` are never written (`story_os/show_state.py`).
**Source evidence:** doc 01 §3C.
**Problem:** Nothing authoritative to check a new script against.
**Root cause:** Memory was designed as free-text snippets in a semantic store.
**Desired behavior:** Append-only JSONL ledger + rebuildable index + derived state (doc 05 §2–3).
**Proposed architecture:** `story_os/canon_models.py` *(new; copy of `reference/canon_models.py`)*; `story_os/canon_store.py` *(new)*: `CanonStore(show_id)` with `append_events/beliefs/deltas/promises(records)`, `set_status(episode_id, status)`, `correct(event_id, new_event, reason)`, `rebuild_index()`, `query_*` helpers (doc 05 §3 table), `rebuild_character_state(as_of_episode)`.
**Files to change:** `cli_entrypoint.py` (`canon rebuild|show|lint`). **Files to create:** the two modules, `tests/test_canon_store.py`, `tests/fixtures/meridian_drift/canon/*.jsonl`.
**Dependencies:** `sqlite3` (standard library), `pydantic>=2` (already required).
**Database/schema changes:** doc 05 §3 (JSONL files and SQL DDL).
**Implementation instructions:**
1. Copy the models; keep `schema_version`.
2. `append_*`: validate, serialise with `model_dump_json()`, append one line, `flush` + `os.fsync`; take a file lock (`msvcrt.locking` on Windows / `fcntl.flock` elsewhere) for the append.
3. Status changes and corrections are appended as lines `{"op": "status", "episode_id": …, "status": "canon", "at": …}` / `{"op": "supersede", "event_id": …, "by": …, "reason": …}` in `corrections.jsonl`; never rewrite earlier lines.
4. `rebuild_index`: drop and recreate tables; replay `events.jsonl` etc. in order; apply ops; for `promises.jsonl` keep the latest line per `promise_id`.
5. Query helpers return models, filtered to `status='canon'` unless `include_draft_episode=<id>`.
6. `rebuild_character_state`: steps 1–4 of doc 05 §5.4 (5–6 arrive with CHAR-001).
7. Add a test that greps the repository for `events.jsonl` writers outside `canon_store.py`.

**Code example (SKETCH):**
```python
def knows_as_of(self, holder_id: str, ordinal: int) -> list[Belief]:
    rows = self.db.execute(
        "SELECT belief_id FROM beliefs WHERE holder_id=? AND acquired_ordinal<=? "
        "AND (ended_ordinal IS NULL OR ended_ordinal>?)", (holder_id, ordinal, ordinal))
    return [self._beliefs[r[0]] for r in rows]
```
**Existing-system compatibility:** Additive; nothing reads the ledger until CANON-002.
**Migration:** None (empty ledger is valid).
**Test procedure:** `pytest tests/test_canon_store.py -q`: append/rebuild round-trip; byte-identical rebuild twice; status flip; supersede; each query in doc 05 §3 against the fixture; validator rejects a `canon` event with no verification.
**Expected output:** pass. **Failure conditions:** rebuild non-deterministic; a line rewritten in place (compare file prefix hashes before/after).
**Rollback:** delete `canon/`; revert.
**Dependencies on other changes:** STORYOS-001.
**Acceptance criteria:** doc 05 examples 1 and 2 load, index and answer "who is mistaken about EV-s01e02-007?" with `C01`.
**Verification status:** models **tested** standalone; store proposed.

---

## CANON-002 — Evidence-cited extraction with verification

**Priority:** P0
**Current behavior:** Keyword heuristics (`episode_memory.py:118–487`); measured output in doc 01 §3C.
**Source evidence:** `:130–139, 189–190, 411–412, 462–481`.
**Problem:** Memory is noise; real facts are missed; nothing can be verified.
**Root cause:** No model reads the script; no evidence requirement.
**Desired behavior:** Pipeline of doc 05 §4. Draft records with `line_id` evidence; Python quote check; one re-ask; single-claim judges for irreversible changes.
**Proposed architecture:** `story_os/canon_extract.py` *(new)*: `number_lines(script) -> (text, short_to_uuid)`, `extract_scene(scene, cast, known_entities) -> RawExtraction`, `verify(raw, scene_lines) -> (accepted, rejected)`, `judge_claim(claim, lines) -> bool`, `extract_episode(episode_id) -> ExtractionReport`. `EpisodeMemory.extract_memories_from_episode` calls it when `USE_CANON_LEDGER` is on and still writes `memories.json` in the legacy shape.
**Files to change:** `episode_memory.py`, `story_structure.py` (the existing hook at `:1219–1226` needs no change), `script_editor.py` (`regenerate_scene` must mark the episode's draft records stale and trigger re-extraction of that scene; preserve `line_id`s of unchanged lines by matching `(character, content)`), `cli_entrypoint.py` (`canon extract|backfill`). **Files to create:** `story_os/canon_extract.py`, `tests/test_canon_extract.py`, fixture scripts with annotations.
**Dependencies:** CANON-001, BASE-002 (roles `extractor`, `judge_a`).
**Database/schema changes:** `episodes/<id>/quality/extraction_report.json`: counts accepted/rejected by reason, entity proposals, judge decisions.
**Implementation instructions:**
1. `number_lines`: assign `L0001…` per episode; keep the map in the report.
2. Prompt (Stardock's own wording; do not copy NovelGenerator's): rules of doc 05 §4 step 2; output schema = lists of events, state changes, relationship deltas, beliefs, promises, each with `line_ids` and `quote`.
3. `verify`: the checks of step 3; normalise with `unicodedata.normalize('NFKC')`, collapse whitespace, straighten quotes, lower-case; quote must be a substring of one cited line and ≥ 3 words.
4. Re-ask once with the rejected records and reasons.
5. Judges for: `condition` changes to dead/destroyed/gone; promise `paid` claims (CANON-004); contradictions found against canon.
6. Assign IDs `EV-s{season:02d}e{episode:02d}-{n:03d}`; write as `draft`.
7. `approve-episode` → `CanonStore.set_status(episode_id, 'canon')`, rebuild state.

**Code example (SKETCH):**
```python
def _quote_ok(quote: str, line_text: str) -> bool:
    norm = lambda s: re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s)
                            .replace('’', "'").replace('“', '"').replace('”', '"')).strip().lower()
    q = norm(quote)
    return len(q.split()) >= 3 and q in norm(line_text)
```
**Existing-system compatibility:** Flag off → legacy heuristics unchanged. Flag on → `memories.json` still produced (categories mapped: events → `plot_point`, deltas → `relationship`, promises → `unresolved_thread`, state → `character_state`).
**Migration:** `canon backfill --episode <id>` for existing scripts (draft; needs approval).
**Test procedure:** `pytest tests/test_canon_extract.py -q` with a stub LLM returning (a) a correct extraction, (b) one with a fabricated quote, (c) one citing a line from another scene, (d) an unknown character → assert accept/reject and one re-ask. Live accuracy: doc 12 T03–T05.
**Expected output:** (b), (c) rejected with reasons; (d) becomes an entity proposal; no record without evidence reaches the ledger.
**Failure conditions:** any ledger record whose quote is absent from its cited line; more than one re-ask; legacy `memories.json` missing.
**Rollback:** flag off.
**Dependencies on other changes:** CANON-001, BASE-002.
**Acceptance criteria:** on the four-line probe scene of doc 01 §3C, the ledger contains "Ilen says he never opened the log" as a **belief/claim by Ilen**, not as a fact, and contains zero template "plot points".
**Verification status:** proposed.

---

## CANON-003 — Beliefs and the omniscience check

**Priority:** P1
**Current behavior:** No per-character knowledge.
**Source evidence:** `story_os/models.py` `CharacterState` has `status_notes` only.
**Problem:** Characters can refer to anything; deception and irony cannot be planned.
**Root cause:** No model of who witnessed what.
**Desired behavior:** doc 05 §4 step 6 and §4.1.
**Proposed architecture:** `story_os/beliefs.py` *(new)*: `derive_beliefs(events, scene_presence) -> list[Belief]`, `set_truth(belief, store)`, `available_ironies(store, present_ids, ordinal)`, `omniscience_check(script, store) -> list[Issue]`.
**Files to change:** `story_os/canon_extract.py` (call derive), `quality_checker.py` (add check), `story_os/assembler.py` (knowledge section). **Files to create:** `story_os/beliefs.py`, `tests/test_beliefs.py`.
**Dependencies:** CANON-002.
**Database/schema changes:** `beliefs.jsonl`; reserved holder `AUDIENCE`.
**Implementation instructions:** 1. Witness → `knows`. 2. Told → `believes` with `told_by`; `truth` by matching `about_event_id` then proposition similarity against canon; unmatched → `unknown`. 3. `omniscience_check`: one extractor call per scene asking "which earlier facts does each speaker's dialogue presuppose (cite the line)"; compare with the speaker's belief set; missing → `error`. 4. Expose `available_ironies` to the planner and scene-card prompt.
**Code example (pseudocode):** `for ev in events: for w in ev.witnesses: emit Belief(holder=w, stance='knows', source='witnessed', truth='true', about_event_id=ev.event_id, …)`
**Existing-system compatibility:** Additive. **Migration:** beliefs are derived during backfill.
**Test procedure:** `pytest tests/test_beliefs.py -q` using doc 05 Example 2 as the fixture; a script line where C03 states Ilen sent the reply must raise an omniscience error; the same line from C04 must not.
**Expected output:** as stated. **Failure conditions:** absent character receives a belief; `truth` taken from the character's own claim.
**Rollback:** disable the check in `quality_checker`. **Dependencies on other changes:** CANON-002.
**Acceptance criteria:** T03 passes.
**Verification status:** proposed.

---

## CANON-004 — Promises with horizons and judged closure

**Priority:** P1
**Current behavior:** Every question is an "unresolved thread" (`episode_memory.py:462–481`); hooks by keyword (`show_state.py:16–43`); `EpisodeSlot.must_plant/must_payoff` always empty (`planner.py:73–74`).
**Source evidence:** as cited.
**Problem:** No real obligations; nothing closes.
**Root cause:** No promise object.
**Desired behavior:** doc 03 §1.3, §5.1; doc 06 §9.
**Proposed architecture:** `story_os/promises.py` *(new)*: `register(promise)`, `develop(promise_id, event_id)`, `nominate_closures(scene_handoff) -> list[promise_id]`, `judge_closure(promise, lines) -> (bool, reason)`, `due(season, episode)`, `ageing(episode, k)`, `fair_play_audit(mystery_id)`, `season_end_audit(season)`.
**Files to change:** `story_os/canon_extract.py`, `story_os/assembler.py`, `quality_checker.py`, `story_os/show_state.py` (fill `unresolved_hooks`/`active_threads` from the ledger for old readers). **Files to create:** `story_os/promises.py`, `tests/test_promises.py`.
**Dependencies:** CANON-002.
**Database/schema changes:** `promises.jsonl`; `seasons/<N>/mystery_solutions.json` (`[{promise_id, solution, required_clues[], red_herrings[]}]`).
**Implementation instructions:** 1. Extractor proposes promises with `kind` and `horizon`; scene/episode-horizon promises are stored but create no obligation. 2. Closure: only promises *nominated* by a scene are judged, one call each, question: "Do these lines use or answer the planted item so that it no longer needs development? yes/no + quoted line". 3. Audits per doc 03 §5.1 step 8 and doc 12 T08. 4. Feed `due` and `ageing` to milestones' `must_*` and the assembler.
**Code example (pseudocode):** `if judge_closure(p, cited_lines)[0]: append(p.copy(status='paid', payoff_event_id=ev))`
**Existing-system compatibility:** Legacy thread list still produced for `view-memories`. **Migration:** none.
**Test procedure:** `pytest tests/test_promises.py -q` with doc 06 Example 4 as the fixture: plant → develop → pay ordering; closure refused when the stub judge says no; season-end audit flags an unpaid season promise and ignores a scene-horizon one.
**Expected output:** as stated. **Failure conditions:** promise closed without a judge decision; payoff recorded before plant.
**Rollback:** flag off. **Dependencies on other changes:** CANON-002.
**Acceptance criteria:** T08 passes.
**Verification status:** proposed.

---

## CANON-005 — Mem0 as a derived index (`infer=False`)

**Priority:** P1
**Current behavior:** `mem0_client.add_memory` (`:120–155`) calls `client.add(content, **add_kwargs)` with no `infer`; `add_story_structure` (`:441–467`) sends a whole structure JSON as a memory; `get_previous_episode_context` returns nothing when Mem0 is disabled.
**Source evidence:** as cited; Mem0 2.2.1 `Memory.add(..., infer=True)` default (doc 02 B3).
**Problem:** An LLM inside Mem0 may merge, update or delete stored story facts.
**Root cause:** Default mode is designed for chat memory, not canon.
**Desired behavior:** Mem0 holds verbatim copies of ledger summaries for semantic recall only.
**Proposed architecture:** `add_memory(..., infer: bool = False)` passes `infer=infer` to both client types; `CanonStore.sync_semantic_index()` writes one memory per canon event with metadata `{show_id, event_id, episode_number, status}`; retrieval returns event IDs that are then loaded from the ledger.
**Files to change:** `mem0_client.py`, `episode_memory.py`, `story_structure.py` (`_add_episode_to_memory` becomes a no-op when the ledger flag is on), `requirements.txt` (pin `mem0ai>=2.2,<3` after confirming the `infer` keyword on the managed client in the installed version). **Files to create:** `tests/test_mem0_infer.py`.
**Dependencies:** CANON-001.
**Database/schema changes:** None.
**Implementation instructions:** 1. Add the parameter and pass it through; if the installed client rejects `infer`, catch `TypeError`, log once, and refuse to write (do not fall back to inference). 2. Implement sync and `canon rebuild --semantic`. 3. Make `get_previous_episode_context` ledger-first.
**Code example (SKETCH):** `self.client.add(content, infer=False, **add_kwargs)`
**Existing-system compatibility:** Existing Mem0 contents are left alone; reference-book memories are unaffected.
**Migration:** optional `canon rebuild --semantic` after backfill.
**Test procedure:** `pytest tests/test_mem0_infer.py -q` (mock client asserts `infer=False` in every call originating from story code).
**Expected output:** pass. **Failure conditions:** any story-memory write with `infer` unset or true.
**Rollback:** revert. **Dependencies on other changes:** CANON-001.
**Acceptance criteria:** continuity context is identical with Mem0 enabled and disabled, except for the optional "older related events" section.
**Verification status:** proposed.

---

## PLAN-001 — Season creation with commitments, mystery solutions, validation

**Priority:** P1
**Current behavior:** `SeasonPlanner.create_season` (`show_os/seasons.py:98–163`) makes one LLM call and saves whatever parses; no validation, no retry, no commitments.
**Source evidence:** `ARC_BEATS_PROMPT` `:34–74`; `_generate_arc_beats`.
**Problem:** Milestones describe events only; no question, no locked ending, no planted clues; a malformed reply aborts.
**Root cause:** Single unvalidated generation.
**Desired behavior:** doc 06 §4.
**Proposed architecture:** Two planner calls (season frame; milestones) + `validate_roadmap` + one re-ask; outputs `roadmap.json` v1, `mystery_solutions.json`, legacy `season_plan.json`.
**Files to change:** `show_os/seasons.py`, `story_os/roadmap.py`, `cli_entrypoint.py` (`new-season` gains `--episodes`, `--lock "<text>"` repeatable, `--yes`). **Files to create:** `tests/test_season_creation.py`, seeded bad roadmaps under `tests/fixtures/roadmaps/`.
**Dependencies:** STORYOS-002, BASE-002; CANON-004 for clue scheduling checks.
**Database/schema changes:** fields on `EpisodeMilestone` (STORYOS-002); `mystery_solutions.json`.
**Implementation instructions:** 1. Extend the prompt's JSON schema with `purpose`, `structural_role`, `obstacle_type`, `character_focus` (IDs), `must_plant`, `must_develop`, `must_payoff`, `commitment`. 2. Generate the season frame first (question, opposition, 2–4 locked commitments, mysteries with solutions and required clues). 3. Validate; on failure append the failed rules to the prompt and retry once; on second failure exit non-zero and print the report. 4. Show the user the locked commitments for confirmation unless `--yes`.
**Code example (pseudocode):** `issues = validate_roadmap(rm, cast_ids); if issues: rm = regenerate(feedback=issues); if validate_roadmap(rm, cast_ids): raise SeasonPlanError(issues)`
**Existing-system compatibility:** `season_plan.json` still written with the five legacy keys.
**Migration:** existing seasons are imported, not regenerated.
**Test procedure:** `pytest tests/test_season_creation.py -q` with a stub LLM: valid reply accepted; reply missing a midpoint rejected then accepted on retry; reply scheduling a clue after its payoff rejected.
**Expected output:** pass; T01. **Failure conditions:** roadmap saved with validation errors; solution text present in any writer-role prompt (assembler test).
**Rollback:** `new-season --legacy` runs the old single-call path.
**Dependencies on other changes:** STORYOS-002.
**Acceptance criteria:** T01.
**Verification status:** proposed.

---

## PLAN-002 — Rolling episode planner and replanning

**Priority:** P1
**Current behavior:** No per-episode planning step and no replanning; `arc_slot` snapshot.
**Source evidence:** `cli_entrypoint.py:297–309`; doc 01 §3A.
**Problem:** Episodes neither read history properly nor feed back into the plan.
**Root cause:** No planner module.
**Desired behavior:** doc 06 §5–6.
**Proposed architecture:** `story_os/episode_planner.py` *(new)*: `plan_episode(show_id, season, n) -> EpisodeOutline`, `forecast_impact(outline)`, `replan_season(show_id, season, approved_n, *, max_changed=0.4, force=None)`. Approval commands in the CLI.
**Files to change:** `cli_entrypoint.py` (`plan-episode`, `approve-episode`, `unapprove-episode`, `replan-season`), `story_os/roadmap.py`. **Files to create:** `story_os/episode_planner.py`, `tests/test_replan.py`, copy `fixtures/replan_experiment.json` and `reference/replan_check.py` into `tests/fixtures/` and `tools/`.
**Dependencies:** STORYOS-002, CANON-002, CANON-004, QUALITY-003 (premise selection; without it, take the first premise passing the Python screen), NARRATIVE-001 (outline).
**Database/schema changes:** `episodes/<id>/outline.json`: `{premise, candidates[], judge_votes[], framework, cards[], forecast_impact[]}`; `RoadmapChange` entries.
**Implementation instructions:** 1. Implement `plan_episode` steps 1–7 through the assembler. 2. Steps 8–10 (WRITERS-001) behind `USE_WRITERS_ROOM`; otherwise a single premise. 3. Step 11 calls NARRATIVE-001/002. 4. `replan_season` exactly as doc 06 §6: precondition listing by the extractor role, comparison in Python, proposal by the planner role, validation, `save_roadmap`. 5. A locked conflict raises `LockedCommitmentConflict` and writes `seasons/<N>/blocked.json`. 6. `approve-episode` = set canon status → rebuild state → `replan_season`.
**Code example (pseudocode):** see doc 06 §6.
**Existing-system compatibility:** Flag `USE_ROLLING_PLAN` off → `approve-episode` only flips status.
**Migration:** none.
**Test procedure:** `pytest tests/test_replan.py -q`: property test — for random proposals from a stub planner, frozen and locked fields never change and every change has `reason` and `triggered_by_event_id`; `python tools/replan_check.py tests/fixtures/replan_experiment.json` prints the table in doc 06 §7.2.
**Expected output:** A: 3/1/3/0; B: 0/0/0/3; C: 0/0/0/6.
**Failure conditions:** version bump with empty delta; change to an approved episode; unpaid new promise without payoff or explicit abandonment.
**Rollback:** `roadmap restore --version K`; flag off.
**Dependencies on other changes:** as listed.
**Acceptance criteria:** T07; `EXP-REPLAN` report produced.
**Verification status:** scorer and fixture **tested**; planner proposed.

---

## PLAN-003 — Series plan

**Priority:** P3
**Current behavior:** `story_os.models.SeriesArc` and its I/O exist; nothing produces or reads it.
**Source evidence:** `story_os/io.py:76–88`.
**Problem:** No multi-season direction. **Root cause:** Unimplemented.
**Desired behavior:** doc 03 §1.7: 2–4 candidate directions, each listing the series-horizon promises it would pay and the canon it requires.
**Proposed architecture:** `series_plan.json` under the show; `roadmap.propose_next_season(show_id)` filters directions whose `requires_canon` holds.
**Files to change:** `story_os/roadmap.py`, `show_os/seasons.py`, `cli_entrypoint.py` (`series-plan show|propose|choose`). **Files to create:** `tests/test_series_plan.py`.
**Dependencies:** CANON-004. **Database/schema changes:** `{"directions": [{"id", "premise", "pays": [promise_id], "requires_canon": [proposition]}], "chosen": {"season": 2, "id": "…"}}`.
**Implementation instructions:** 1. Generate at show creation and at each season end. 2. Check `requires_canon` against the ledger by event lookup. 3. `new-season` defaults its arc prompt to the chosen direction.
**Code example:** none needed beyond the schema.
**Existing-system compatibility:** Optional file. **Migration:** none.
**Test procedure:** stub ledger where one direction's requirement is false → it is filtered out.
**Expected output:** pass. **Failure conditions:** a direction offered whose requirement canon contradicts.
**Rollback:** delete the file. **Dependencies on other changes:** CANON-004, PLAN-001.
**Acceptance criteria:** season 2 of the fixture show can be planned with season 1 canon in context and every series-horizon promise listed.
**Verification status:** proposed.

---

## NARRATIVE-001 — Scene cards and sequential causal writing

*This is the fully worked coding task required as Example 8. The code below was applied to a scratch copy of the repository at the audited commit and its tests were run: 21 passed (12 existing after BASE-001 + 9 new).*

**Priority:** P0

**Current behavior:**
- `StoryStructure.generate_scenes` builds one prompt per scene and runs them with `asyncio.gather` (`story_structure.py:948–968`). Each prompt contains the episode title and theme, one beat's name and description, "Scene N of M", a cast list, book RAG text and previous-episode memory (`:1008–1040`). No scene sees another.
- `scenes_per_beat` gives each of the 15 beats at least one scene (`:893–897`), so a 30-minute episode always has 17.
- `generate_episode_script` loops over scenes (`:1188–1194`) and calls `_generate_scene_script`, whose context is title, theme, beat, setting, scene number and `name: species - role` (`:1287–1294`). The scene outline's `plot` is not passed. The previous scene's script is not passed.

**Source evidence:** `story_structure.py` — `generate_scenes` `:863–979`; `_generate_scene_outline` `:981–1083`; `generate_episode_script` `:1147–1244`; `_generate_scene_script` `:1246–1423`.

**Problem:** An episode is a set of unrelated scenes. Causality, setups and payoffs inside an episode are impossible; the fixed scene count pads the story.

**Root cause:** Parallel generation was chosen for speed, with the beat sheet as the only shared structure, and the script stage was never given the outline.

**Desired behavior:** With `USE_SCENE_CARDS` on: one call plans the whole episode as 5–14 ordered scene cards; Python validates them (every scene changes a value; every scene after the first is caused by an earlier one; known characters only); one re-ask on failure; scenes are then written in order, each prompt carrying its card, the previous scene's hand-off and last 12 spoken lines, and the next scene's goal as "do not resolve". On double failure the legacy path runs.

**Proposed architecture:**
```
generate_scenes ──flag──► _generate_scenes_from_cards ──► complete_text (1 call, JSON)
                                   │                         parse_cards → validate_cards → (re-ask once)
                                   ▼
                          episode['scenes'][i] = legacy keys + 'card'
generate_episode_script ─► for each scene: _generate_scene_script(…, previous_scene_script, next_scene)
                                   └─ preamble += render_card_block(scene, previous, next)
                          scene_script['card'] = card   (so the next scene and later stages can read it)
```

**Files to change:** `story_structure.py`, `data/feature_flags.json` (add `"USE_SCENE_CARDS": false`).
**Files to create:** `story_os/scene_cards.py`, `tests/test_scene_cards.py`.
Both new files are supplied complete: `reference/scene_cards.py` (221 lines) and `reference/test_scene_cards.py` (159 lines). The `story_structure.py` change is supplied as `reference/patches/NARRATIVE-001_story_structure.patch` (applies cleanly to the audited commit).

**Dependencies:** `pydantic>=2` (already in `requirements.txt`). No new packages.

**Database/schema changes:** `episode['scenes'][i]['card']` and `script['scenes'][i]['card']` (a `SceneCard` dict); `episode['metadata']['outline_mode'] = 'cards'`.

```json
{"scene_number": 3, "kind": "scene", "setting": "Array bay, Meridian",
 "present": ["Dace", "Ilen"], "focus": "Ilen",
 "goal": "Ilen wants Dace to rest her burned hand",
 "opposition": "Dace insists on doing the EVA herself",
 "turn": "Ilen volunteers to go outside in her place",
 "outcome": "yes_but", "value_shift": "guilt: hidden -> acted on",
 "audience_learns": "Ilen cannot bring himself to say why he feels responsible",
 "caused_by": [2], "hands_off": "Ilen is now alone outside with the array he misused",
 "sound_design": ["array bay hum", "suit seals"]}
```

**Implementation instructions:**
1. Complete BASE-001 first (the new tests reuse its mock pattern).
2. Copy `reference/scene_cards.py` to `story_os/scene_cards.py`.
3. Apply the patch: `git apply reference/patches/NARRATIVE-001_story_structure.patch`. If it no longer applies, make these six edits by hand:
   a. At the top of the `try:` in `generate_scenes` (before "Calculate number of scenes"), add the flag check that calls `self._generate_scenes_from_cards(episode)` and returns its result when non-empty.
   b. Add the method `_generate_scenes_from_cards` immediately before `_generate_scene_outline`.
   c. In `generate_episode_script`, pass `previous_scene_script` and `next_scene` to `_generate_scene_script`.
   d. Add those two optional parameters to `_generate_scene_script`.
   e. After the `story_os_block` preamble part, append `render_card_block(scene, previous_scene_script, next_scene)` when `scene.get('card')`.
   f. After building `scene_script`, copy `scene['card']` into it.
4. Copy `reference/test_scene_cards.py` to `tests/test_scene_cards.py`.
5. Add `"USE_SCENE_CARDS": false` to `data/feature_flags.json`.
6. Run the tests.
7. Manual check with a real key: `USE_SCENE_CARDS=1 python main.py generate-scenes <episode_id>` then `generate-script`; open `structure.json` and confirm `metadata.outline_mode` and the cards.

**Code examples (VERIFIED):**

Card model and validation (excerpt of `story_os/scene_cards.py`):
```python
class SceneCard(BaseModel):
    scene_number: int
    kind: Literal['scene', 'sequel'] = 'scene'
    setting: str
    present: List[str] = Field(min_length=1)
    focus: str
    goal: str
    opposition: str
    turn: str
    outcome: Literal['yes', 'no', 'yes_but', 'no_and']
    value_shift: str
    audience_learns: str = ''
    caused_by: List[int] = Field(default_factory=list)
    hands_off: str
    sound_design: List[str] = Field(default_factory=list)


def validate_cards(cards: List[SceneCard], cast_names: List[str]) -> List[str]:
    issues: List[str] = []
    if not MIN_CARDS <= len(cards) <= MAX_CARDS:
        issues.append(f'{len(cards)} scenes; expected {MIN_CARDS}-{MAX_CARDS}')
    known = {n.strip().lower() for n in cast_names if n and n.strip()}
    for idx, card in enumerate(cards, 1):
        tag = f'scene {idx}'
        if card.scene_number != idx:
            issues.append(f'{tag}: scene_number is {card.scene_number}')
        for field in ('goal', 'opposition', 'turn', 'value_shift', 'hands_off'):
            if not getattr(card, field).strip():
                issues.append(f'{tag}: empty {field}')
        if idx > 1 and not card.caused_by:
            issues.append(f'{tag}: caused_by is empty')
        for c in card.caused_by:
            if not 1 <= c < idx:
                issues.append(f'{tag}: caused_by {c} is not an earlier scene')
        if known:
            for name in card.present:
                if name.strip().lower() not in known:
                    issues.append(f'{tag}: unknown character {name!r}')
        if idx > 1 and (card.value_shift.strip().lower()
                        == cards[idx - 2].value_shift.strip().lower()):
            issues.append(f'{tag}: same value_shift as the previous scene')
    if cards and len({c.outcome for c in cards}) == 1:
        issues.append('every scene has the same outcome')
    return issues
```

New method in `StoryStructure` (from the patch):
```python
def _generate_scenes_from_cards(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
    from story_os import scene_cards as sc
    continuity = ''
    try:
        number = episode.get('episode_number', 0)
        if number > 1:
            ctx = get_episode_memory().get_previous_episode_context(
                current_episode_number=number, series=episode.get('series'), limit=15)
            continuity = '\n'.join((ctx.get('plot_points') or [])[:5]
                                   + (ctx.get('unresolved_threads') or [])[:3])
    except Exception as e:
        logger.warning('Card continuity context skipped: %s', e)
    cast_names = [(c.get('name') or '').strip() for c in episode.get('characters') or []]
    prompt = sc.build_cards_prompt(episode, continuity)
    feedback = ''
    for attempt in (1, 2):
        raw = self.complete_text(sc.CARDS_SYSTEM, prompt + feedback, max_tokens=4000)
        cards, problems = sc.parse_cards(raw)
        if not problems:
            problems = sc.validate_cards(cards, cast_names)
        if not problems:
            scenes = sc.cards_to_scenes(cards, episode.get('target_duration_minutes', 30) * 60)
            episode['scenes'] = scenes
            episode.setdefault('metadata', {})['outline_mode'] = 'cards'
            self._save_episode(episode)
            return scenes
        logger.warning('Scene cards attempt %s rejected: %s', attempt, problems[:6])
        feedback = ('\n\nYOUR PREVIOUS ANSWER WAS REJECTED. Fix these problems '
                    'and return the full JSON again:\n- ' + '\n- '.join(problems[:12]))
    return []
```

Loop change in `generate_episode_script`:
```python
all_scenes = episode.get("scenes", [])
for i, scene in enumerate(all_scenes, 1):
    scene_script = self._generate_scene_script(
        episode, scene, extra_preamble=extra_preamble,
        previous_scene_script=(script["scenes"][-1] if script["scenes"] else None),
        next_scene=(all_scenes[i] if i < len(all_scenes) else None),
    )
    script["scenes"].append(scene_script)
```

What scene 2's writer now receives ahead of the existing prompt (actual `render_card_block` output from the test fixture):
```
SCENE CARD (write exactly this scene; the turn must happen on the page)
Setting: Bridge
Present: Mara, Ilen
Focus character: Mara
Goal: goal 2
Opposition: opposition 2
Turn: turn 2
Outcome: no   Value shift: trust step 2
The audience learns: (nothing new)
Leave unresolved for the next scene: left open 2
Sounds: engine hum
Do NOT resolve this (it belongs to the next scene): goal 3

PREVIOUS SCENE (already written; continue from it, do not repeat it)
It left unresolved: left open 1
MARA: Seal it.
```

**Existing-system compatibility:** Flag off (the default): identical behaviour — `test_legacy_scene_prompt_unchanged_without_card` asserts no card text reaches a legacy prompt. Flag on: `episode['scenes']` keeps every key other code reads (`scene_id`, `scene_number`, `beat`, `setting`, `characters`, `plot`, `duration_seconds`), so `audio_pipeline`, `quality_checker`, `script_editor`, `export_timeline` and `episode_memory` work unchanged. `beat` now holds `scene`/`sequel` rather than a Save the Cat name; `quality_checker._check_script_structure` compares against `episode['beats']` and may warn — acceptable until NARRATIVE-002 replaces the beat list with the chosen framework's steps.

**Migration:** None. Existing episodes keep their scenes. To re-outline one: `USE_SCENE_CARDS=1 python main.py generate-scenes <id>` overwrites `scenes` (the previous structure is recoverable from git or a manual copy; AUTO-001 adds automatic snapshots).

**Test procedure:**
```bash
STARDOCK_DISABLE_MEM0=1 python -m pytest tests/test_scene_cards.py -q
STARDOCK_DISABLE_MEM0=1 python -m pytest tests -q
```

**Expected output:** `9 passed`, then `21 passed`.

The nine tests: good cards parse and validate; uncaused scene and unknown character rejected; forward cause and empty value shift rejected; bad JSON and missing field reported; rendered block carries hand-off and spoken tail but not description lines; a rejected first answer triggers exactly one re-ask containing the problems, then acceptance; two failures return `[]` after exactly two calls; six scene prompts are sequential (prompt *i* contains card *i*, hand-off *i−1* and scene *i−1*'s line; the first has no "PREVIOUS SCENE"; every line has a `line_id`; cards are saved on the script); the legacy prompt is unchanged without a card.

**Failure conditions:** any test fails; a scene prompt after the first lacks "PREVIOUS SCENE"; more than two card calls per episode; with the flag off, any difference in generated prompts; `asyncio.gather` used on the card path.

**Rollback:** set the flag to false (instant); or `git apply -R` the patch and delete the two new files.

**Dependencies on other changes:** BASE-001. (BASE-002 is not required: the patch uses the existing `complete_text`.)

**Acceptance criteria:**
1. The test commands above print the expected counts.
2. A real generated episode with the flag on has between 5 and 14 scenes and `metadata.outline_mode == "cards"`.
3. In that episode's trace or logs, card planning is one call (two at most).
4. A human reading scenes 1–3 can state why scene 2 follows from scene 1.

**Known limits, to be closed by later changes:** the hand-off is the *planned* `hands_off` plus the last 12 lines, not an extraction of what was actually written (CANON-002 adds that); continuity context still comes from the legacy extractor (CANON-002); the season milestone enters only through `arc_slot` (STORYOS-002); no framework choice (NARRATIVE-002); character briefs are minimal (NARRATIVE-003); `max_tokens=2000` per scene still applies (raise it through `llm_config` in BASE-002).

**Verification status:** new module, patch and tests **tested** against a scratch copy with a stubbed LLM. **Not tested** with a real model: card JSON reliability and prose quality. Proposed for the repository.

---

## NARRATIVE-002 — Framework registry and selection

**Priority:** P1
**Current behavior:** `BEAT_SHEET` (`story_structure.py:41–132`) is applied to every episode (`:257`).
**Source evidence:** as cited; `_calculate_beat_durations` `:305–341`.
**Problem:** Every episode has the same contour. **Root cause:** One hard-coded structure.
**Desired behavior:** doc 03 §2.1 — ten frameworks, deterministic selection rule, rotation guard.
**Proposed architecture:** `story_os/frameworks.py` *(new)*: `Framework`, `REGISTRY`, `select_framework(milestone, history) -> (framework_id, reason)`; the card prompt receives the chosen framework's steps as "functions this episode must contain", not as scenes.
**Files to change:** `story_structure.py` (`generate_episode_structure` stores `framework`; `BEAT_SHEET` kept as the data for `save_the_cat`), `story_os/scene_cards.py` (`build_cards_prompt` gains a `framework` argument; `validate_cards` checks each required step is mapped via a new card field `step`), `quality_checker.py` (`_check_script_structure` uses the framework's steps). **Files to create:** `story_os/frameworks.py`, `tests/test_frameworks.py`.
**Dependencies:** NARRATIVE-001, STORYOS-002.
**Database/schema changes:** `Framework{id, name, steps[{id, function, share}], fits{arc_importance[], tension_level[], focus_count, tags[]}, audio_notes}`; `SceneCard.step: str = ''`; `metrics/episodes.jsonl` records the framework.
**Implementation instructions:** 1. Encode the ten frameworks of doc 03 §2.1. 2. Implement the rule exactly as written there; the LLM is asked only when ≥ 2 candidates remain. 3. Unit-test rotation over a simulated 10-episode season. 4. Legacy path keeps Save the Cat.
**Code example (SKETCH):**
```python
def select_framework(m, history):
    c = [f for f in REGISTRY.values() if _fits(f, m)]
    c = [f for f in c if not history or f.id != history[-1]]
    cap = math.ceil(m.season_length / 3)
    c = [f for f in c if history.count(f.id) < cap] or list(REGISTRY.values())
    for pref in _preferences(m):               # mystery payoff, focus count, breather
        hit = [f for f in c if f.id in pref]
        if hit: return hit[0].id, f'rule:{pref}'
    return (c[0].id, 'only candidate') if len(c) == 1 else _ask_planner(c[:3], m)
```
**Existing-system compatibility:** Episodes without `framework` are treated as `save_the_cat`. **Migration:** none.
**Test procedure:** `pytest tests/test_frameworks.py -q`: no framework twice running; ≥ 3 distinct in 8 simulated episodes; a milestone with a mystery payoff selects `mystery_fairplay`; each framework's `share`s sum to 1.
**Expected output:** pass. **Failure conditions:** same framework in adjacent episodes; a required step unmapped yet accepted.
**Rollback:** force `save_the_cat` via config `frameworks.force`. **Dependencies on other changes:** NARRATIVE-001.
**Acceptance criteria:** doc 06 Example 6 can be reproduced: three episodes of one season with three frameworks and different scene counts.
**Verification status:** proposed.

---

## NARRATIVE-003 — Per-character briefs and cue syntax in the writer prompt

**Priority:** P1
**Current behavior:** Writer sees `name: species - role` (`story_structure.py:1265–1269`); sound cues are free parentheticals.
**Source evidence:** `:1340–1354`.
**Problem:** Identical voices; on-the-nose dialogue; unanchored cues. **Root cause:** No character data or cue contract in the prompt.
**Desired behavior:** doc 07 §4.
**Proposed architecture:** `story_os/scene_cards.render_character_briefs(card, profiles, beliefs)`; cue syntax block from `audio_timeline.CUE_GUIDE`.
**Files to change:** `story_structure.py` (`_generate_scene_script`), `story_os/scene_cards.py`. **Files to create:** `tests/test_writer_prompt.py`.
**Dependencies:** NARRATIVE-001; CHAR-001 for profiles; CANON-003 for beliefs (briefs degrade to profile-only without it); AUDIO-002 for the cue grammar.
**Database/schema changes:** `SceneCard.objectives: Dict[str, str]`, `SceneCard.withheld: Dict[str, str]` (per character name).
**Implementation instructions:** 1. Add the two card fields to the card prompt. 2. Render a brief per present character: objective, withheld, knows (≤ 3 relevant beliefs), dialogue profile. 3. Add available ironies. 4. Add the cue guide and require registered sound IDs or a quoted description. 5. Remove the raw book RAG block for shows with `use_book_rag=false` (BASE-003).
**Code example (pseudocode):** `preamble_parts.append(render_character_briefs(card, profiles, beliefs))`
**Existing-system compatibility:** Only on the card path. **Migration:** none.
**Test procedure:** prompt contains each present character's `never_says` and objective; contains no belief of an absent character; contains the cue guide.
**Expected output:** pass. **Failure conditions:** mystery solution or an absent character's secret in a writer prompt.
**Rollback:** config switch `writer.briefs=false`. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T09b (voice attribution) improves over the NARRATIVE-001-only arm in `EXP-ABLATE`, or the change is disabled.
**Verification status:** proposed.

---

## CHAR-001 — Character profiles, derived state, arc steps

**Priority:** P1
**Current behavior:** Cast entries are free text (`name, species, role, personality, backstory, voice_description`); IDs unstable; no state.
**Source evidence:** `show_os/new_show.py:40` (`CAST_PROPOSAL_PROMPT`); `story_structure.py:599–635`.
**Problem:** Personality is an adjective list; change has no cause. **Root cause:** No model.
**Desired behavior:** doc 05 §5.
**Proposed architecture:** `story_os/characters.py` *(new)*: `load_profile`, `save_profile(profile, reason)` (logged to `characters/changes.jsonl`), `enrich_profile_from_cast(cast_entry)` (one planner call fills want/need/wound/false belief/dialogue profile for human review), `rebuild_state` (delegates to `CanonStore`), `propose_arc_step` + judge.
**Files to change:** `show_os/new_show.py` (cast proposal schema), `story_os/canon_store.py`, `story_os/assembler.py`, `cli_entrypoint.py` (`character show|edit|enrich`). **Files to create:** `story_os/characters.py`, `tests/test_characters.py`.
**Dependencies:** STORYOS-001, CANON-001/002.
**Database/schema changes:** `characters/C*.json` (`CharacterProfile`), `canon/state/characters/C*.json` (`CharacterState`).
**Implementation instructions:** 1. Extend the `CAST_PROPOSAL_PROMPT` JSON keys with the profile fields. 2. `enrich` for existing shows, never overwriting a non-empty field. 3. Name-similarity check at cast creation (shared first syllable or edit distance ≤ 2 → warn). 4. State rebuild steps 5–6 of doc 05 §5.4. 5. Antagonists and recurring guests get profiles too.
**Code example:** schemas in `reference/canon_models.py`; example profile doc 05 §5.3.
**Existing-system compatibility:** Bible `main_cast` stays; profiles are additive. **Migration:** `character enrich --show <id> --all` (review before saving).
**Test procedure:** state rebuild from the fixture ledger equals the expected JSON; an arc step proposed without evidence is refused; doc 05 Example 5 fixture yields five steps with no skipped position.
**Expected output:** pass. **Failure conditions:** profile changed by an automatic process; state not reproducible from the ledger.
**Rollback:** delete `characters/` and `state/`. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T06.
**Verification status:** schemas **tested**; rest proposed.

---

## QUALITY-003 — Pairwise judge

**Priority:** P1
**Current behavior:** One absolute 0–10 score from one model (`quality_checker.py:665–743`).
**Source evidence:** as cited.
**Problem:** Absolute scores are unanchored; the judge may be the writer. **Root cause:** Single-call design.
**Desired behavior:** doc 02 A4: `compare(a, b, question, context) -> Verdict` using two judge roles, each seeing A/B and B/A.
**Proposed architecture:** `story_os/judge.py` *(new)*: `compare`, `rank(items, question)` (round-robin for ≤ 4 items), `claim(question, evidence) -> (bool, reason)` for single-claim checks. Result: `{wins_a, wins_b, ties, by_judge, order_flips}`; a judge that flips with order counts as a tie.
**Files to change:** none required (new callers). **Files to create:** `story_os/judge.py`, `tests/test_judge.py`.
**Dependencies:** BASE-002.
**Database/schema changes:** verdict records appended to `episodes/<id>/quality/judgments.jsonl`.
**Implementation instructions:** 1. Fixed prompt: the question, shared context, "Text 1", "Text 2", answer JSON `{"winner": 1|2|0, "reason": "…"}`. 2. Four calls per comparison. 3. Decision requires a strict majority of non-tie votes; otherwise `undecided` (callers keep the incumbent or first item). 4. Log judge models and versions.
**Code example (SKETCH):**
```python
def compare(a, b, question, context=''):
    votes = []
    for role in ('judge_a', 'judge_b'):
        v1 = _ask(role, question, context, a, b)        # 1 → a
        v2 = _ask(role, question, context, b, a)        # 1 → b
        votes.append('a' if (v1, v2) == (1, 2) else 'b' if (v1, v2) == (2, 1) else 'tie')
    return Verdict(votes)
```
**Existing-system compatibility:** `_evaluate_script_with_ai` remains as a trend number. **Migration:** none.
**Test procedure:** stub judge that always answers "1" → every comparison is a tie (order bias neutralised); stub that prefers the longer text → that text wins; malformed JSON → tie, logged.
**Expected output:** pass. **Failure conditions:** a decision from a single order; writer model used as both judges without a warning.
**Rollback:** not applicable (unused until called). **Dependencies on other changes:** BASE-002.
**Acceptance criteria:** used by WRITERS-001, `EXP-ABLATE`, `EXP-REPLAN`.
**Verification status:** proposed.

---

## QUALITY-001 — Lint, editor pass, bounded revision

**Priority:** P1
**Current behavior:** `check_episode_quality` reports heuristics and one LLM score; nothing is revised. Continuity branch is dead (`quality_checker.py:357–362` reads a key that does not exist).
**Source evidence:** `quality_checker.py:310–419, 665–743`; `story_pipeline_agent.py:89–118`.
**Problem:** Problems are recorded, not fixed. **Root cause:** No loop.
**Desired behavior:** doc 07 §3.
**Proposed architecture:** `story_os/writers_room.py` *(new)*: `lint(script, cards, store) -> list[Finding]`, `editor_review(script, findings, cards) -> list[Patch]`, `apply_patches(episode_id, patches)` (calls `script_editor.regenerate_scene` with card, hand-off and instruction), `run_edit_round(episode_id)`. `story_pipeline_agent.run_agentic_episode_script` orchestrates.
**Files to change:** `quality_checker.py` (replace `_check_continuity` body with ledger checks; keep the name), `story_pipeline_agent.py`, `script_editor.py` (`regenerate_scene(episode_id, scene_number, *, card=None, handoff=None, instruction='', keep_line_ids=True)`). **Files to create:** `story_os/writers_room.py`, `tests/test_writers_room.py`.
**Dependencies:** NARRATIVE-001, CANON-002/003/004, BASE-002.
**Database/schema changes:** `Finding{check, severity, scene, line_ids, message}`, `Patch{scene, line_ids, problem, instruction}`; `quality/lint.json`, `quality/editor.json`.
**Implementation instructions:** 1. Implement each lint row of doc 07 §3.1 as a function. 2. Editor prompt = checklist of §3.2, must cite line IDs, ≤ 12 patches, no rewritten text. 3. Caps: one round; ≤ 30% of scenes; beyond that return `needs_reoutline`. 4. Snapshot drafts before and after (`draft_store.save_script_draft`). 5. Preserve `line_id`s of unchanged lines. 6. Ending and escalation checks from doc 03 §1.5, §2.3.
**Code example (pseudocode):** `findings = lint(...); patches = editor_review(...); if len({p.scene for p in patches}) > 0.3 * n: return 'needs_reoutline'; apply_patches(...); errors = [f for f in lint(...) if f.severity == 'error']`
**Existing-system compatibility:** `check-quality` CLI output keeps its keys and gains new ones. **Migration:** none.
**Test procedure:** each lint rule has a passing and failing fixture line; the 30% cap; line IDs outside a regenerated span unchanged; the dead continuity branch replaced (test that a contradiction with a ledger fact is reported).
**Expected output:** pass. **Failure conditions:** editor output containing replacement dialogue is applied verbatim; more than one automatic round.
**Rollback:** `USE_WRITERS_ROOM=false`. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T02, T05.
**Verification status:** proposed.

---

## QUALITY-004 — Audio-first clarity lint

**Priority:** P2
**Current behavior:** None. `description` lines are skipped by audio (`audio_pipeline.py:498–500`).
**Source evidence:** as cited.
**Problem:** Scripts can depend on things the listener never hears. **Root cause:** Screen-style scripts.
**Desired behavior:** doc 03 §3.5 rules. **Proposed architecture:** functions in `writers_room.lint`.
**Files to change:** `story_os/writers_room.py`. **Files to create:** tests in `tests/test_writers_room.py`.
**Dependencies:** QUALITY-001. **Database/schema changes:** none.
**Implementation instructions:** implement the five rules; the read-aloud checks of doc 07 §3.3 (line length, repeated initial consonants, numerals/abbreviations).
**Code example (pseudocode):** `if noun in description_only_nouns and noun in later_dialogue: error`
**Existing-system compatibility:** warnings only by default. **Migration:** none.
**Test procedure:** fixture scene with a prop introduced only in a description → error; scene with five speakers → warning.
**Expected output:** pass. **Failure conditions:** false errors on framed/narrated episodes (must be exempt).
**Rollback:** disable rule IDs in config. **Dependencies on other changes:** QUALITY-001.
**Acceptance criteria:** rules run in `check-quality`.
**Verification status:** proposed.

---

## WRITERS-001 — Candidate premises

**Priority:** P2
**Current behavior:** Theme comes from `--theme` or nothing.
**Source evidence:** `cli_entrypoint.py:297–309`.
**Problem:** The first idea is the only idea. **Root cause:** No exploration step.
**Desired behavior:** doc 06 §5 steps 8–10.
**Proposed architecture:** `writers_room.propose_premises(context, n=3)`, `screen(premises, store, roadmap)`, `choose(premises)` via `judge.rank`.
**Files to change:** `story_os/episode_planner.py`. **Files to create:** tests.
**Dependencies:** PLAN-002, QUALITY-003. **Database/schema changes:** `outline.json.candidates[]`, `judge_votes[]`.
**Implementation instructions:** 1. One call returns three premises differing in protagonist, obstacle type and ending type (validated in Python; re-ask once). 2. Python screen. 3. Rank. 4. Optional graft, recorded. 5. `--premise-review` pauses for the human.
**Code example:** none beyond the above.
**Existing-system compatibility:** flag off → single premise. **Migration:** none.
**Test procedure:** premises identical in protagonist rejected; a premise contradicting canon screened out; undecided ranking keeps the first surviving premise.
**Expected output:** pass. **Failure conditions:** a screened-out premise selected.
**Rollback:** flag off. **Dependencies on other changes:** as listed.
**Acceptance criteria:** kept or cut by `EXP-ABLATE` (arm C vs A).
**Verification status:** proposed.

---

## QUALITY-002 — Originality metrics

**Priority:** P2
**Current behavior:** None. **Source evidence:** —
**Problem:** Sameness across episodes is unmeasured. **Root cause:** No cross-episode view.
**Desired behavior:** doc 07 §8. **Proposed architecture:** `story_os/originality.py` *(new)*, `story_os/metrics.py` *(new; append-only `metrics/episodes.jsonl`, last record per episode wins)*.
**Files to change:** `cli_entrypoint.py` (`originality-report --show --season`). **Files to create:** the two modules, `tests/test_originality.py`.
**Dependencies:** NARRATIVE-002 for structural fingerprints; an embedding model for two rows (optional; rows are skipped without it).
**Database/schema changes:** metrics record `{episode_id, framework, opening_type, ending_type, obstacle_type, scene_count, value_shift_signs, calls, tokens, cost}`.
**Implementation instructions:** implement each row of the table; mask character names before n-gram work; thresholds in config, marked uncalibrated.
**Code example (SKETCH):** `jaccard = len(a & b) / max(1, len(a | b))` over 4-gram sets.
**Existing-system compatibility:** read-only. **Migration:** none.
**Test procedure:** two identical scripts → every similarity flag raised; two unrelated public-domain scripts → none.
**Expected output:** pass. **Failure conditions:** names inflating similarity.
**Rollback:** n/a. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T09; `EXP-ORIG` report.
**Verification status:** proposed.

---

## AUDIO-001 — Per-line cache and word alignment

**Priority:** P0 (audio)
**Current behavior:** Every line is synthesised on every run into `scene_dir/line_XXX_<name>.<ext>` (`audio_pipeline.py:510–559`); no timings exist.
**Source evidence:** `_generate_character_audio`, `_generate_narrator_audio`; `export_timeline.py:15`.
**Problem:** No resume; no way to place a sound on a word. **Root cause:** Files keyed by position, not content; no alignment step.
**Desired behavior:** `audio/lines/<line_id>.wav` + `.json` with content hash and word timings (doc 08 §4.4, §7).
**Proposed architecture:** `audio_align.py` *(new)*: `align(wav_path, text) -> list[Word]` with pluggable backends (`engine`, `ctc`, `proportional`); `audio_pipeline` gains `render_line(line, voice) -> LineAudio` that checks the cache first.
**Files to change:** `audio_pipeline.py`, `dialogue_engine.py` (return engine timings when available), `export_timeline.py`. **Files to create:** `audio_align.py`, `tests/test_audio_align.py`, `tests/test_line_cache.py`.
**Dependencies:** optional `ctc-forced-aligner` or `whisperx` (BSD-2-Clause) in a new `requirements-audio.txt`; **configure a commercially usable alignment model** (doc 02 D3). `numpy`, `soundfile` (already used by `audio_qa.py` when present).
**Database/schema changes:** `lines/<line_id>.json`: `{line_id, text_hash, voice_id, engine, engine_version, params, sr, n_samples, words:[{w,start,end}], method, approximate}`.
**Implementation instructions:** 1. Hash = SHA-256 of `(normalised text, voice_id, engine, engine_version, params, emotion)`. 2. Cache hit → return without synthesis. 3. Miss → synthesise to a temp file, convert to WAV, align, write both atomically. 4. Backend order: engine → ctc → proportional. 5. Validate monotonic, in-range, word count. 6. Keep writing the legacy per-scene files only when the legacy mixer is active.
**Code example (SKETCH — proportional fallback):**
```python
def proportional(text, n_samples):
    words = text.split(); total = sum(len(w) for w in words) or 1
    out, pos = [], 0
    for w in words:
        span = int(n_samples * len(w) / total)
        out.append({'w': w, 'start': pos, 'end': pos + span}); pos += span
    return out
```
**Existing-system compatibility:** legacy mixer unaffected. **Migration:** none; first run fills the cache.
**Test procedure:** fake engine counting calls: second run makes zero calls; editing one line makes one; alignment validators; proportional fallback sums to the file length ±1 word.
**Expected output:** pass. **Failure conditions:** cache hit with a different voice or text; non-monotonic timings accepted.
**Rollback:** delete `audio/lines/`. **Dependencies on other changes:** BASE-001.
**Acceptance criteria:** T13 (tts part); T11 timing tolerance with the chosen aligner.
**Verification status:** proposed. Aligner accuracy **unverified**.

---

## AUDIO-002 — Cue syntax, timeline model, resolver

**Priority:** P0 (audio)
**Current behavior:** Parenthetical lines containing sound words become `sound_effect` lines (`story_structure.py:1584–1590`); `director_pass` extracts `[sfx: …]` that nothing reads.
**Source evidence:** as cited; `director_pass.py:26–50`.
**Problem:** No anchor, level or duration semantics. **Root cause:** Free-text cues.
**Desired behavior:** doc 08 §6.1, §8.1.
**Proposed architecture:** `audio_timeline.py` *(new)*: `parse_cue(text) -> Cue | None`, `CUE_GUIDE` (prompt text), `build_timeline(script, line_audio, assets, identities) -> Timeline`, `resolve(timeline, line_audio) -> Timeline` (fills `start_sample`), models from `reference/canon_models.py` (`Anchor`, `TimelineClip`, `GainAutomation`, `Timeline`).
**Files to change:** `story_structure.py` (`_parse_script_lines` attaches `cue` to sound lines; unparseable → legacy line), `export_timeline.py` (export resolved times; chapters), `director_pass.py` (`pause_after_ms` feeds gaps). **Files to create:** `audio_timeline.py`, `tests/test_cue_parser.py`, `tests/test_timeline_resolve.py`.
**Dependencies:** AUDIO-001. **Database/schema changes:** `line['cue']`; `audio/timeline.json`.
**Implementation instructions:** 1. Grammar: `(TRACK: id_or_slug | "description" | key: value | flag …)`; tolerant of spacing and case. 2. Legacy parenthetical → `after: prev_line +150ms`. 3. Resolver per doc 08 §8.1, including negative offsets and scene overlap. 4. Unknown line references → error finding. 5. Deterministic ordering of clips.
**Code example (SKETCH):**
```python
_CUE = re.compile(r'^\(\s*(SFX|AMB|MUS)\s*:\s*(?P<body>.+)\)\s*$', re.I)
def parse_cue(text):
    m = _CUE.match(text.strip())
    if not m: return None
    parts = [p.strip() for p in m['body'].split('|')]
    cue = {'track': m[1].lower(), 'sound': parts[0], 'options': {}}
    for p in parts[1:]:
        if p.startswith('"'): cue['description'] = p.strip('"')
        elif ':' in p: k, v = p.split(':', 1); cue['options'][k.strip()] = v.strip()
        else: cue['options'][p] = True
    return cue
```
**Existing-system compatibility:** old scripts parse to legacy cues. **Migration:** none.
**Test procedure:** 20-row table of cue strings → expected dicts (including malformed); resolver test reproducing doc 08 §8.4 with synthetic durations (assert exact sample positions).
**Expected output:** pass. **Failure conditions:** a cue silently dropped; non-deterministic clip order.
**Rollback:** flag off. **Dependencies on other changes:** AUDIO-001.
**Acceptance criteria:** the §8.4 JSON validates and resolves.
**Verification status:** models **tested** (the §8.4 JSON validates); parser and resolver proposed.

---

## AUDIO-003 — Multitrack mixer

**Priority:** P0 (audio)
**Current behavior:** `_mix_scene_audio` (`audio_pipeline.py:733–968`) concatenates; `_assemble_episode` (`:1442–1540`) concatenates scenes and re-encodes twice.
**Source evidence:** doc 01 §6.3 rows 1, 4–8, 10–11.
**Problem:** No overlap, ducking, crossfades; quality loss. **Root cause:** Concat-list design at 24 kHz mono.
**Desired behavior:** doc 08 §8.2. **Proposed architecture:** `audio_mix.py` *(new)*, based on `reference/mix_sketch.py`: `load_clip(path, sr=48000) -> np.ndarray (N,2)`, `render_scene(timeline_scene) -> stems`, `render_episode(timeline) -> {stems, mix}` rendering scene by scene and overlap-adding into memory-mapped WAV stems.
**Files to change:** `audio_pipeline.py` (`generate_episode_audio`: when `USE_TIMELINE_MIXER`, run lines → timeline → mix → master instead of `generate_scene_audio`/`_assemble_episode`; intro/outro become clips on the timeline). **Files to create:** `audio_mix.py`, `tests/test_audio_mix.py`, `tests/fixtures/audio_scene/` (generated by a script; no third-party audio).
**Dependencies:** `numpy`, `soundfile`, `scipy` (resampling); ffmpeg for decode of legacy MP3 assets. Not `pedalboard` (GPL-3).
**Database/schema changes:** `audio/stems/*.wav`, `audio/mix.wav`.
**Implementation instructions:** 1. Port the sketch's `to_stereo`, `fade`, `loop_to_length`, `place`, `duck_gain`, `limit`; vectorise `envelope`. 2. Resample at load. 3. Apply `GainAutomation` segments per bus. 4. Dialogue bus: per-line loudness match, then gentle compression. 5. Scene overlap crossfade for ambience and music. 6. Write 24-bit WAV stems and mix. 7. Determinism: no random state; fixed dtype; assert bit-exact repeat.
**Code example (VERIFIED in the sketch):** see `reference/mix_sketch.py` — `place`, `duck_gain`, `loop_to_length`, `mix_scene`; run output `onset error 1 samples, duck -9.0 dB, seam step 0.0001, peak -1.50 dBFS`.
**Existing-system compatibility:** flag off → legacy mixer. Legacy assets (MP3) load through ffmpeg decode.
**Migration:** none; re-render to benefit.
**Test procedure:** `pytest tests/test_audio_mix.py -q` — assertions 1–5, 7–8 of doc 08 §12; plus the legacy mixer on the same fixture must fail assertion 1.
**Expected output:** pass. **Failure conditions:** onset error > 1 sample; duck depth outside tolerance; non-identical repeat render; memory above a configured ceiling for a 40-minute episode.
**Rollback:** flag off. **Dependencies on other changes:** AUDIO-001, AUDIO-002; AUDIO-005 for assets.
**Acceptance criteria:** T11.
**Verification status:** DSP core **tested** in the sketch; module proposed.

---

## AUDIO-004 — Mastering and audio QA

**Priority:** P1
**Current behavior:** No loudness control; metadata step re-encodes (`audio_pipeline.py:1514–1532`); `audio_qa.py` checks WAV duration and sample peak for the first 200 WAVs only.
**Source evidence:** as cited; `audio_qa.py:36–72`.
**Problem:** Inconsistent loudness; possible overs; final mix never examined. **Root cause:** Not implemented.
**Desired behavior:** doc 08 §8.3, §10.
**Proposed architecture:** `audio_master.py` *(new)*: `measure(path) -> {lufs_i, true_peak_dbtp, lra}`, `master(mix_wav, out_path, target=-16, tp=-1, codec='aac', bitrate='160k', metadata={})` (two-pass ffmpeg `loudnorm`, single encode with metadata); `audio_qa.run_audio_qa` extended with the table's checks.
**Files to change:** `audio_qa.py`, `audio_pipeline.py`. **Files to create:** `audio_master.py`, `tests/test_audio_master.py`.
**Dependencies:** ffmpeg (present); `pyloudnorm` (MIT) for independent measurement; an ASR model for the intelligibility check (optional; skipped with a warning when absent).
**Database/schema changes:** `audio/loudness.json`; extended `audio_qa_report.json` with `blocking: [...]`.
**Implementation instructions:** 1. Pass 1: `ffmpeg -i mix.wav -af loudnorm=I=-16:TP=-1:LRA=11:print_format=json -f null -`; parse the JSON. 2. Pass 2 with `measured_*` values and `linear=true`. 3. Encode once; write tags in the same command. 4. Verify the output with `measure`; fail if outside −16 ±1 LUFS or above −1 dBTP. 5. Add QA rows; `USE_AUDIO_QA_BLOCK` blocks publishing on `blocking`.
**Code example (SKETCH):**
```python
af = (f"loudnorm=I={target}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
      f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
cmd = ['ffmpeg', '-y', '-i', mix, '-af', af, '-ar', '48000', '-c:a', 'aac', '-b:a', bitrate,
       *sum((['-metadata', f'{k}={v}'] for k, v in metadata.items()), []), out]
```
**Existing-system compatibility:** legacy path keeps its encode. **Migration:** none.
**Test procedure:** master the fixture mix → measured −16 ±1 LUFS, ≤ −1 dBTP; a deliberately clipped stem → blocking finding; a mix with music 3 dB above dialogue → intelligibility/ratio finding.
**Expected output:** pass. **Failure conditions:** more than one lossy encode in the command log; QA passing a clipped file.
**Rollback:** flag off. **Dependencies on other changes:** AUDIO-003.
**Acceptance criteria:** T12.
**Verification status:** proposed.

---

## AUDIO-005 — Asset library and cue resolution

**Priority:** P1
**Current behavior:** `_get_sound_effect` globs the full description (`audio_pipeline.py:605–609`); `_add_scene_ambience` uses 13 keywords (`:660–693`); misses are logged with duplicates.
**Source evidence:** as cited; `needed_audio_report.py`.
**Problem:** Effects are almost never found; no provenance. **Root cause:** Filename matching.
**Desired behavior:** doc 08 §9. **Proposed architecture:** `audio_assets.py` *(new)*: `ingest(path, kind, meta) -> sha`, `index()`, `resolve(cue, identities, providers) -> AssetRef | None`, `loudness_normalise_on_ingest`, `check_loop(path)`.
**Files to change:** `audio_pipeline.py`, `needed_audio_report.py` (de-duplicate by `(kind, key)`), `cli_entrypoint.py` (`assets ingest|list|rights`). **Files to create:** `audio_assets.py`, `tests/test_audio_assets.py`.
**Dependencies:** none required; embeddings optional. **Database/schema changes:** `assets/library/<sha>.wav|.json`, `assets/library/index.json`.
**Implementation instructions:** 1. Ingest legacy folders with `source: legacy`, `license: unknown`. 2. Resolution order of doc 08 §9. 3. Token-overlap score with a threshold; ties → shortest duration difference. 4. Generation hook (AUDIO-007). 5. Rights report lists unknown licences.
**Code example (pseudocode):** `ref = identities.get(cue.sound) or by_slug.get(cue.sound) or best_tag_match(cue.description) or generate(cue)`
**Existing-system compatibility:** legacy lookup remains for the legacy mixer. **Migration:** `assets ingest --legacy`.
**Test procedure:** "the gentle hum of the starship's engines" resolves to an asset tagged `engine, hum` (today's glob finds nothing); identical file ingested twice → one entry; unknown licence appears in the rights report.
**Expected output:** pass. **Failure conditions:** two different files under one hash; a cue resolving to an asset of the wrong kind.
**Rollback:** delete `assets/library/`. **Dependencies on other changes:** none (used by AUDIO-003).
**Acceptance criteria:** ≥ 90% of cues in a generated fixture episode resolve or are generated; the rest are listed once each.
**Verification status:** proposed.

---

## AUDIO-006 — TTS provider registry, `voice_id`, licence gate, benchmark

**Priority:** P1
**Current behavior:** Engines chosen by `engine_order` (`dialogue_engine.py:128–166`), committed as `["xtts", "kokoro"]`; `tts_engine.py:374–375` auto-accepts Coqui terms; voices keyed by name slug with a 35-entry alias table; config reloaded per line.
**Source evidence:** as cited.
**Problem:** Non-commercial model first in line; unstable voice identity; no way to add engines cleanly. **Root cause:** Two hard-wired engines.
**Desired behavior:** doc 08 §2–4.
**Proposed architecture:** `tts_engine.ENGINE_REGISTRY: dict[str, EngineSpec]` with `{factory, licence, commercial_ok, supports: {clone, emotion_tags, timings}}`; `dialogue_engine` resolves speaker → `character_id` → `voice_id` → engine; `publishable: true` in the show profile forbids engines with `commercial_ok=False`; harness `tools/tts_benchmark.py`.
**Files to change:** `tts_engine.py` (remove the auto-accept; require explicit `COQUI_TOS_AGREED=1` *and* `publishable=false`), `dialogue_engine.py` (cache config; `voice_id`), `voice_registry.py` (`consent_record` required for clones), `voices/voice_config.json` (default `engine_order: ["kokoro"]`). **Files to create:** `tools/tts_benchmark.py`, `tests/fixtures/tts_bench/lines.json`, `tests/test_tts_registry.py`.
**Dependencies:** candidate engines installed in separate environments; a speaker-embedding model and an ASR model for the harness (record names and licences in the benchmark report).
**Database/schema changes:** `voice_config.json` entries gain `voice_id`, `consent_record`, `emotion_refs`.
**Implementation instructions:** 1. Registry and licence gate with tests. 2. New engines implement the existing `TTSEngine` interface; heavy ones run out of process (`python -m audio_providers.tts_worker --engine … --in job.json --out dir`). 3. Emotion passed as `style: {emotion, intensity}` and mapped per engine (ignored by Kokoro). 4. Benchmark harness implementing doc 08 §3; writes `Docs/decisions/TTS-BENCHMARK-<date>.md`. 5. Drift check function for audio QA.
**Code example (SKETCH):** `if profile.publishable and not ENGINE_REGISTRY[name].commercial_ok: raise LicenceError(name)`
**Existing-system compatibility:** existing `voice_config.json` keys map to `voice_id`s by slug; XTTS still usable for non-publishable experiments.
**Migration:** `voices migrate` adds `voice_id`s; lists clones lacking consent records.
**Test procedure:** licence gate; speaker resolution by alias from the cast; config loaded once per run (mock open count); fake-engine benchmark dry run.
**Expected output:** pass. **Failure conditions:** XTTS selected for a publishable show; a clone registered without consent.
**Rollback:** restore previous `engine_order`. **Dependencies on other changes:** STORYOS-001 (IDs), BASE-003 (profile).
**Acceptance criteria:** T10; benchmark report exists before any default changes.
**Verification status:** proposed. **No engine was auditioned.**

---

## AUDIO-007 — SFX and music providers

**Priority:** P2
**Current behavior:** No SFX generation; `generate_theme_music.py` calls a paid ElevenLabs endpoint.
**Source evidence:** `generate_theme_music.py`; `USE_BARK_SFX` unused.
**Problem:** Missing sounds stay missing; music costs credits. **Root cause:** Not implemented.
**Desired behavior:** doc 08 §9 providers. **Proposed architecture:** `audio_providers/base.py` (protocols), `soundbox.py`, `moss_sfx.py`, `acestep.py`; selection in `data/audio_config.json`.
**Files to change:** `audio_assets.py` (generation hook), `generate_theme_music.py` (use `MusicProvider`; keep ElevenLabs as an optional legacy provider). **Files to create:** the package, `tests/test_audio_providers.py` (fake HTTP server for soundbox).
**Dependencies:** a running soundbox (MIT) **or** direct model installs (MOSS-SoundEffect v2 Apache-2.0; ACE-Step 1.5 MIT). Record each model's licence string in asset sidecars.
**Database/schema changes:** `data/audio_config.json`: `{"sfx": {"provider": "soundbox", "model": "…", "variations": 3}, "music": {...}, "soundbox": {"base_url": "http://127.0.0.1:17494"}}`.
**Implementation instructions:** 1. `SoundboxProvider.generate`: `POST /api/generate` `{model, prompt, duration_s, seed, variations}` → poll `GET /api/jobs/{id}` → download `/files/{id}.wav` → ingest. Confirm field names against `docs/API.md` of the installed version. 2. Timeouts and one retry. 3. Ambience: request 20–30 s, run `check_loop`, regenerate once if the seam fails. 4. Music: theme, 3 stings, 2 beds per show; register as sound identities.
**Code example (pseudocode):** `job = post('/api/generate', {...}); wait(job); for sound in job.sounds: ingest(download(sound.id), kind, meta)`
**Existing-system compatibility:** with no provider configured, behaviour is "report missing". **Migration:** none.
**Test procedure:** fake server returns a WAV → asset ingested with prompt/seed/licence; server error → cue reported missing, pipeline continues.
**Expected output:** pass. **Failure conditions:** generated asset without a licence field; pipeline abort on provider failure.
**Rollback:** remove provider config. **Dependencies on other changes:** AUDIO-005.
**Acceptance criteria:** a missing SFX cue in the fixture episode is generated, cached, and reused on the next run without a second generation.
**Verification status:** proposed. Soundbox endpoints read from its docs, **not called**.

---

## AUDIO-008 — Sound identities tied to canon

**Priority:** P2
**Current behavior:** None. **Source evidence:** —
**Problem:** Recurring sounds differ between episodes; sound cannot carry story meaning. **Root cause:** No registry.
**Desired behavior:** doc 08 §6.2–6.3. **Proposed architecture:** `sound/identities.json` (`SoundIdentity[]`); `design-sound` command; assembler section "sound identities and their meanings so far"; QA check that a used identity gained a `meanings` entry.
**Files to change:** `story_os/assembler.py`, `audio_assets.py`, `cli_entrypoint.py`. **Files to create:** `story_os/sound_identity.py`, tests.
**Dependencies:** AUDIO-005; CANON-001 for `canon_ref` validation. **Database/schema changes:** as doc 08 §6.3.
**Implementation instructions:** 1. Registry CRUD. 2. Location ambiences created per recurring location at show creation. 3. Writer may reference only registered IDs or propose new ones. 4. Treatments are timeline parameters; the asset hash never changes without an explicit `replace` with a reason.
**Code example:** JSON in doc 08 §6.3.
**Existing-system compatibility:** additive. **Migration:** none.
**Test procedure:** same `sound_id` in two episodes resolves to the same hash; replacing an asset without a reason is refused.
**Expected output:** pass. **Failure conditions:** identity silently regenerated.
**Rollback:** delete the file. **Dependencies on other changes:** AUDIO-005.
**Acceptance criteria:** doc 08 Example 7 can be represented and resolved.
**Verification status:** proposed.

---

## AUTO-001 — Job runner, `produce-episode`, resume

**Priority:** P1
**Current behavior:** Five manual commands; no state; audio regenerates everything (`audio_pipeline.py:399–454`).
**Source evidence:** `cli_entrypoint.py`; doc 01 §7.
**Problem:** No end-to-end run; interruptions waste work. **Root cause:** No job model.
**Desired behavior:** doc 09 §2. **Proposed architecture:** `story_os/jobs.py` *(new)*: `Stage{name, inputs(), run(ctx), outputs()}`, `Job.load/save`, `run(job, from_stage=None, only=None)`, hashing helper, lock.
**Files to change:** `cli_entrypoint.py` (`produce-episode`, `produce-season`, `job status`), `scripts/*.sh`. **Files to create:** `story_os/jobs.py`, `tests/test_jobs.py`.
**Dependencies:** none new. **Database/schema changes:** `episodes/<id>/job.json` (doc 09 §2.1).
**Implementation instructions:** 1. Wrap existing functions as stages first (`generate_episode`, `generate_characters`, `generate_scenes`, `generate_script`, `generate_episode_audio`) so the runner works with the legacy pipeline. 2. Input hash = SHA-256 over sorted `(path, file hash)` plus relevant config and `pipeline_version`. 3. Per-unit progress for `write` (scene drafts under `drafts/scenes/`) and `tts` (AUDIO-001 cache). 4. Atomic state writes; stale-lock takeover. 5. Snapshot `structure.json`/`script.json` before a stage overwrites them.
**Code example (SKETCH):**
```python
for st in stages:
    h = hash_inputs(st.inputs())
    rec = job.stage(st.name)
    if rec.status == 'done' and rec.input_hash == h and not forced(st): continue
    rec.update(status='running', input_hash=h); job.save()
    try: st.run(ctx); rec.update(status='done', output_hash=hash_inputs(st.outputs()))
    except Exception as e: rec.update(status='failed', error=str(e)); job.save(); raise
    job.save()
```
**Existing-system compatibility:** old commands unchanged. **Migration:** none; a job file is created on first `produce-episode`.
**Test procedure:** stages that count calls; inject a failure in `write` after scene 4 → rerun starts at scene 5; unchanged inputs → zero stage runs; changed card → `write` and later stages rerun, `tts` reuses unchanged lines.
**Expected output:** pass. **Failure conditions:** a completed unit regenerated; a stale output reused after an input change.
**Rollback:** delete `job.json`. **Dependencies on other changes:** BASE-001; benefits from NARRATIVE-001, AUDIO-001.
**Acceptance criteria:** T13.
**Verification status:** proposed.

---

## PUB-003 — Rights gate

**Priority:** P1 (must precede any live publish)
**Current behavior:** None; the committed show uses third-party IP; XTTS auto-accept.
**Source evidence:** doc 01 §3E, §6.1; doc 09 §8.
**Problem:** A publish command could ship unlicensed material. **Root cause:** No check.
**Desired behavior:** `publish --live` refuses unless the checklist of doc 09 §8 passes or items are waived by name and date.
**Proposed architecture:** `publish/rights.py` *(new)*: `build_rights_report(episode_id) -> Report`, `assert_publishable(report, waivers)`.
**Files to change:** `cli_entrypoint.py`. **Files to create:** `publish/__init__.py`, `publish/rights.py`, `tests/test_rights_gate.py`.
**Dependencies:** AUDIO-005/006 sidecars and registry; BASE-003 (`original` flag). **Database/schema changes:** `publish/rights_report.json`; `data/shows/<id>/publish/rights.json` (waivers).
**Implementation instructions:** 1. Collect voices, engines, assets, book-RAG use, `original` flag, AI-disclosure text presence. 2. Franchise term screen: a configurable deny-list checked against title, description and script. 3. Any `unknown`/non-commercial item → blocking unless waived. 4. Require `--i-authorise-publication` on the command line for live runs.
**Code example (pseudocode):** `if report.blocking and not waived: raise RightsError(report.blocking)`
**Existing-system compatibility:** affects only the new publish command. **Migration:** none.
**Test procedure:** fixture with an XTTS line → blocked; with an `unknown` asset → blocked; all clean → passes; waiver file with name/date → passes and is echoed in the log.
**Expected output:** pass. **Failure conditions:** live publish possible with a blocking item.
**Rollback:** n/a. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T14 (gate part).
**Verification status:** proposed.

---

## PUB-001 — Publish assets

**Priority:** P2
**Current behavior:** `episode_metadata.py` stores local metadata; `export_timeline.py` estimates chapter times.
**Source evidence:** doc 01 §6.4.
**Problem:** No transcript, chapters, description or artwork check. **Root cause:** Not implemented.
**Desired behavior:** doc 09 §4. **Proposed architecture:** `publish/assets.py` *(new)*: `build_metadata`, `build_transcript` (VTT + JSON from the resolved timeline), `build_chapters` (JSON chapters), `validate_cover`.
**Files to change:** `episode_metadata.py`, `export_timeline.py`, `cli_entrypoint.py` (`prepare-publish`). **Files to create:** `publish/assets.py`, `tests/test_publish_assets.py`.
**Dependencies:** AUDIO-002/003 for exact times (falls back to estimates with a warning); CANON-002 for the description; `Pillow` for cover validation (optional).
**Database/schema changes:** `episodes/<id>/publish/*` (doc 04 §3).
**Implementation instructions:** 1. VTT cues per dialogue line with `<v Speaker>` voice tags; times from `start_sample / sr`. 2. Chapters at scene starts; titles from card goals, passed through a spoiler rule (no payoff nouns of open promises). 3. Description from this episode's ledger events up to the midpoint + a hook line; AI-disclosure line from the profile. 4. Cover: square, within the host's pixel and file-size limits (configurable; defaults 3000×3000).
**Code example (SKETCH):** `f"{ts(start)} --> {ts(end)}\n<v {speaker}>{text}\n"`
**Existing-system compatibility:** additive. **Migration:** none.
**Test procedure:** VTT parses and is monotonic; chapter JSON matches the podcast-namespace chapters shape (`version`, `chapters[{startTime, title}]`); description contains no open-promise payoff terms from the fixture.
**Expected output:** pass. **Failure conditions:** overlapping cues; chapter beyond the audio duration.
**Rollback:** delete `publish/`. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T14 (assets part).
**Verification status:** proposed.

---

## PUB-002 — Host interface, dry run, Transistor adapter

**Priority:** P2
**Current behavior:** None. **Source evidence:** —
**Problem:** No path to a feed. **Root cause:** Not implemented.
**Desired behavior:** doc 09 §5–6. **Proposed architecture:** `publish/hosts.py` *(new)*: `PodcastHost` protocol, `DryRunHost`, `TransistorHost`, `SelfHostedFeed` (object-storage upload via any S3-compatible client + `publish/rss.py` feed builder); `verify-distribution`.
**Files to change:** `cli_entrypoint.py` (`publish`, `verify-distribution`). **Files to create:** `publish/hosts.py`, `publish/rss.py`, `tests/test_publish_dry_run.py`.
**Dependencies:** `requests`; host API key in `.env` (`TRANSISTOR_API_KEY`); for the self-hosted path an S3-compatible client. **No Spotify API.**
**Database/schema changes:** `data/shows/<id>/publish/feed_state.json` (`{host, host_show_id, feed_url, episodes: {episode_id: {guid, host_episode_id, published_at, enclosure_length}}}`).
**Implementation instructions:** 1. `DryRunHost` records requests and writes `feed.xml` locally. 2. RSS builder with the tags of doc 09 §5.3; GUID = episode ID, immutable. 3. `TransistorHost`: authorise upload → `PUT` → create with `audio_url` → publish; **read developers.transistor.fm for the exact create/publish parameters before coding**; send the API key in the header the docs specify. 4. `publish` defaults to dry run; `--live` requires PUB-003 to pass. 5. `verify-distribution`: fetch the feed, check the item, GUID, enclosure length and `HEAD` on the enclosure. 6. Print the one-time manual steps for Spotify and Apple (doc 09 §6) after the first live publish.
**Code example (SKETCH):**
```python
r = s.get(f'{API}/v1/episodes/authorize_upload', params={'filename': path.name}); r.raise_for_status()
attrs = r.json()['data']['attributes']
requests.put(attrs['upload_url'], data=path.read_bytes(), headers={'Content-Type': attrs['content_type']}).raise_for_status()
audio_url = attrs['audio_url']
```
(Attribute names as described in Transistor's changelog; confirm against the live API reference.)
**Existing-system compatibility:** additive. **Migration:** none.
**Test procedure:** dry run on the fixture episode → valid XML, required tags, enclosure length equals file size, stable GUID across two runs; Transistor adapter against a mocked HTTP layer.
**Expected output:** pass. **Failure conditions:** any network call in dry-run mode; GUID change on republish.
**Rollback:** nothing is published without `--live`. **Dependencies on other changes:** PUB-001, PUB-003.
**Acceptance criteria:** T14.
**Verification status:** proposed. Transistor create/publish endpoints **unverified**.


---

# Amendments for universal scope

Background and design: `16_UNIVERSAL_SCOPE_AND_REFERENCE_CONTROL.md`. Schemas: `reference/reference_models.py` (executed). Each amendment lists only what changes; every other field of the original spec stands.

Shared rule for all amended specs: code asks `project.capability('<key>')` (GEN-001) and never compares the mode name. With `mode = serialized_fiction` the behaviour is exactly the original spec's.

### BASE-003 (MODIFIED)
- **Source evidence — add:** the full table in doc 16 §A4 (17 non-test files), including `tts_pronunciation.py:51–87, 102–149`, `audio_pipeline.py:159–165, 237–240, 660–693`, `generate_theme_music.py:64, 73`, `episode_metadata.py:632–633`, `main.py:3, 9, 211`, `cli_entrypoint.py:5, 1017`, `script_editor.py:328`, `story_structure.py:1436`.
- **Schema:** `format` block replaces `show_profile` (already edited in the spec above).
- **Implementation — add:** 7. Make `species` optional in `_parse_characters` and omit it from `character_info` when empty (`story_structure.py:1265–1269`). 8. Delete the unused `role_to_character` map. 9. Remove stardate handling from the generic intro path; keep it as a `number_rules` entry for the legacy show. 10. Banner and docstrings: "AI podcast studio".
- **Superseded:** step 4's `use_book_rag` switch. Until REF-001 lands, `get_rag_context` returns `''` for any project without references.
- **Tests — add:** the franchise grep uses the widened pattern `star trek|starfleet|stardate|celestial temple|gamma quadrant|bajor|klingon|vulcan|transporter|shuttlecraft|trek` and must be empty outside `tests/`, `story_os/migrate.py`, legacy scripts (`register_voices*.py`, `cli/`), and data files.
- **Acceptance — add:** prompts rendered for a horror anthology and an educational show contain no science-fiction wording (T15, T18).

### STORYOS-001 (MODIFIED)
- **Schema — add:** `data/projects/<project_id>/project.json` (GEN-001); `"project_id"` in each show's bible and in every `structure.json`; `data/shows/index.json` gains `"projects": {show_id: project_id}`.
- **Implementation — add:** `ShowStore.project()`; `resolve_show_id` also returns `project_id`; migration creates one project per existing show (`project_id = show_id`, `mode = serialized_fiction`, `original` from the format block) and records the third registry found in `episode_metadata.py` (`data/metadata` series registry) in the index without changing it.
- **Rule — add:** generation functions take `show_id`/`project_id` explicitly; reading `data/active_show.json` is allowed only in `cli_entrypoint.py`. Test: grep.
- **Dependencies:** GEN-001 first.

### STORYOS-002 (MODIFIED)
- `season_plan` capability selects the plan type: `arc` → `SeasonRoadmap` exactly as specified; `slate` → `EpisodeSlate{episodes:[{episode_number, premise_or_topic, status, notes}], theme}`; `curriculum` → `Curriculum{objectives:[{id, statement, prerequisites[]}], episodes:[{episode_number, objectives[], status}]}`; `none` → no file.
- `milestone_for` returns the slate or curriculum entry in the same dict shape (`arc_beat` = premise/topic) so existing readers work.
- Validation rules of doc 06 §4 apply to `arc` only. Curriculum validation: every objective scheduled once; prerequisites scheduled earlier.
- Tests — add: slate and curriculum round-trip; `none` returns `None` and outline generation proceeds.

### STORYOS-003 (MODIFIED)
- Sections are included by capability: roadmap/promises/beliefs/character-state only when the capability is present; add **style directives** (all modes; from `resolve_style` → `render_directives`), **claims for this segment** (claims modes), **source-established canon** (when a world-building source is enabled), **taught concepts / callbacks** (educational, conversational).
- Test — add: for an educational project the context contains no "promises", "beliefs" or "dramatic question" section.

### CANON-001 (MODIFIED)
- `CanonEvent` gains `origin: 'generated' | 'source'` and `source_id` (already in `reference/canon_models.py`). Source events use `evidence.episode_id = "REF:<source_id>"`.
- `CanonStore` is created only when `continuity` is `canon_full`, `canon_light`, `per_episode` or `per_story`. For `per_episode`/`per_story` the store lives under the episode folder and is not carried forward; `canon_light` keeps only state-change consequences for recurring entities.
- Query helpers accept `origin=`.

### CANON-005 (MODIFIED)
- Namespaces per project (GEN-003). `sync_semantic_index` writes to `<project_id>:canon`.

### PLAN-001 (MODIFIED)
- `create_season` dispatches on `season_plan`: `arc` unchanged; `slate` → one planner call for N premises/topics with variety checks (no two with the same protagonist type/obstacle/topic angle), for anthology around the project theme; `curriculum` → objectives first, then episodes; `none` → skipped.
- The mystery-solution file is created only when the frame contains a mystery.
- CLI: `new-season` works for every mode; prints which plan type was created.

### NARRATIVE-002 (MODIFIED)
- `Framework.family: 'fiction' | 'nonfiction' | 'educational' | 'conversational'`. Selection filters by the mode's `frameworks` capability before any other rule.
- Add data rows — nonfiction: `investigative_question`, `chronological`, `case_study`, `profile`; educational: `explainer` (hook → objective → explain → worked example → check → recap), `myth_vs_fact`, `how_to`; conversational: `host_discussion`, `interview_persona`, `roundtable`, `listener_questions`.
- Genre preferences for fiction are data, not code: `genre_bias` maps genre keywords to preferred frameworks (for example horror → `bottle`, `mystery_fairplay`, `tragedy_dilemma`; comedy → `abc_ensemble`, `two_hander`).
- Rotation rules unchanged, applied within the family.

### NARRATIVE-003 (MODIFIED)
- The writer prompt's style block is the output of `render_directives` (REF-002) for the scene's scope. Raw reference text appears only for research claims and authorised adaptation passages.
- Character briefs are rendered for whatever cast style the mode has; host personas use `DialogueProfile` only.

### CHAR-001 (MODIFIED)
- `CharacterProfile.role_kind: 'character' | 'host' | 'narrator' | 'guest_persona'`. For non-`character` kinds `want`, `need`, `wound`, `false_belief`, arc and beliefs are not required and not generated.
- Cast creation dispatches on `cast`: `ensemble`/`recurring` as specified; `per_episode`/`per_story` creates profiles under the episode and does not add them to the show cast; `hosts` creates 1–3 host personas.
- Guest personas are fictional by default; a persona representing a real person is refused unless the user supplies consent, and is never given invented quotations.
- `species` is optional everywhere.

### QUALITY-001 (MODIFIED)
- Rule sets keyed by `editorial`: `fiction` = original list; `factual` = unsupported claim, figure/date mismatch with its claim, quotation not matching a cited quote, contested claim stated as settled, missing spoken uncertainty where `must_flag_uncertainty`, term used before definition (educational), recap not matching objectives (educational), invented person or institution.
- Editor checklist is chosen the same way. Both sets get one shared item when technique references are enabled: "reads as pastiche of a recognisable author".
- Revision loop, caps and line-ID preservation unchanged.

### QUALITY-004 (MODIFIED)
- "Narration share" and "description-only information" apply to fiction modes only. For hosts-style modes add: no more than three speakers per segment; each host named or self-identified within the first minute; lists longer than four items flagged for audio.

### AUDIO-005 (MODIFIED)
- Sidecar `tags` use generic categories: `ambience/interior|exterior|nature|urban|vehicle|crowd|weather|room_tone`, `sfx/impact|door|footsteps|mechanical|electronic|organic|water|fire|vocal|alert|transition`, `music/theme|sting|bed|transition`. The 13-keyword table (`audio_pipeline.py:660–693`) is removed, not extended.
- Test — add: cues from three settings (rainforest, hotel corridor, radio studio) resolve or are reported, with no spaceship-specific code path.

### AUDIO-006 (MODIFIED)
- `voice_id` = `V-<show_id>-<character_id>`; `voices/voice_config.json` becomes per show (`data/shows/<id>/voices.json`), with the global file read as a legacy fallback for the legacy show only. Two shows may both have a "Narrator" with different voices.

### AUDIO-008 (MODIFIED)
- `sound/identities.json` and a `locations.json` registry are per show; examples in doc 08 are one show's data, not defaults. `design-sound` derives the initial palette from `ProjectConfig.genre` and the show identity. Conversational/educational defaults: studio room tone, intro/outro theme, two stingers.

### AUTO-001 (MODIFIED)
- The stage list is built from capabilities: `plan` uses the mode's planner; `outline` produces scene or segment cards; `extract` runs canon extraction or claim checking; `approve` promotes canon or freezes the claim set. Audio and publishing stages are identical for all modes.
- `produce-episode` requires `--show`; there is no implicit active show in the runner.

### PUB-001 (MODIFIED)
- For claims modes: description lists topics; show notes include a "Sources" list from the cited claims (title, author, locator); chapters come from segment purposes; the spoiler rule is skipped.
- `metadata.json` gains `project_id`, `mode`, `sources[]`, `attributions[]`.

### PUB-002 (MODIFIED)
- **Source evidence — add:** `episode_metadata.generate_episode_feed` (`episode_metadata.py:604–662`) already emits minimal RSS. Extend it (per-show channel data, absolute enclosure URLs, lengths, dates, namespace tags) rather than creating `publish/rss.py`; `publish/hosts.py` calls it.
- `itunes:type` from `feed_type`. Channel title/description from the project, replacing the constants at `:632–633`.

### PUB-003 (MODIFIED)
- Report includes every enabled or snapshot-recorded reference with purpose and rights. Blocking: an enabled `world_building`/`adaptation` source without `owned|licensed|public_domain`; a claims-mode episode with `unsupported` claims not signed off by a human; a guest persona flagged as a real person without consent; missing `attribution_text` for an adaptation.

---

# New specifications (universal scope)

## GEN-001 — Project config, production modes, one-sentence creation

**Priority:** P0 · **Status:** NEW
**Current behavior:** `new-show` needs a name, a concept and previously ingested books (`show_os/new_show.py:102–191`, refusal at `:124–130`); there is no notion of format. Generation is always the fiction pipeline.
**Source evidence:** as cited; `cli_entrypoint.py` `cmd_new_show`; `story_structure.py:257` (beat sheet for every episode).
**Problem:** A sentence cannot create a podcast; non-fiction formats are forced through fiction machinery.
**Root cause:** The tool was built around one franchise show.
**Desired behavior:** `python main.py create-podcast "<one sentence>"` creates a complete project with no other input; the mode is proposed and overridable; every later stage reads capabilities.
**Proposed architecture:** `story_os/project_models.py` *(new; `ProjectConfig`, `MODE_CAPABILITIES`, `SegmentCard` from `reference/reference_models.py`)*; `story_os/projects.py` *(new)*: `propose_project(idea) -> ProjectConfig`, `create_project(config)`, `load_project(project_id)`, `capability(show_id, key)`. `ShowCreator.create_show` gains `project: ProjectConfig` and a no-books path.
**Files to change:** `show_os/new_show.py`, `cli_entrypoint.py` (`create-podcast`, `project show|set-mode|list`), `story_structure.py` (`generate_episode_structure` stores `project_id`, `mode`). **Files to create:** the two modules, `tests/test_projects.py`.
**Dependencies:** BASE-002 (planner role), BASE-003.
**Database/schema changes:** `data/projects/<project_id>/project.json`:
```json
{"project_id": "the_last_station", "show_id": "the_last_station", "title": "The Last Station",
 "idea": "A horror anthology told by the night announcer of a railway station that is no longer on any map.",
 "mode": "anthology", "mode_source": "proposed",
 "mode_rationale": "Self-contained stories linked by a host and a place.",
 "genre": "gothic horror", "audience": "adult", "language": "en", "episode_minutes": 25,
 "original": true, "publishable": true, "shared_reference_projects": [], "schema_version": 1}
```
**Implementation instructions:**
1. Copy the models; add `tests/test_projects.py` asserting every mode has every capability key.
2. `propose_project`: one planner call, JSON validated by `ProjectConfig`; on invalid output re-ask once; on failure or no model use the keyword fallback (doc 16 §C3) and `mode_source='proposed'` with rationale "keyword fallback".
3. `create-podcast`: print the proposal; accept `--mode`, `--title`, `--minutes`, `--yes`; then run: identity (bible from the idea — the existing cast-proposal call generalised to "identity + cast or hosts" by cast style), default voice assignment from the engine's built-in voices, baseline `StyleProfile` from idea and genre, season plan per mode (PLAN-001), and write the project.
4. `ShowCreator.create_show`: when no book-derived bible exists start from `{}`; never raise for missing books.
5. Replace mode-agnostic assumptions with capability reads in the specs amended above.
6. `project set-mode` is allowed until the first episode is approved; afterwards it needs `--force` and writes a decision record.

**Code example (SKETCH):**
```python
def capability(show_id: str, key: str):
    return load_project(ShowStore(show_id).project_id()).capability(key)

if capability(show_id, 'outline') == 'scene_cards':
    scenes = self._generate_scenes_from_cards(episode)       # NARRATIVE-001
else:
    scenes = self._generate_segments_from_cards(episode)     # GEN-002
```
**Example input → output:** `create-podcast "Ten-minute lessons on how bridges stay up, for curious teenagers."` → proposal `mode: educational`, `genre: engineering explainer`, `episode_minutes: 10`, two host personas, curriculum of objectives; no reference prompts, no fiction roadmap.
**Existing-system compatibility:** existing shows get a project with `mode='serialized_fiction'` in migration (STORYOS-001), so their behaviour is unchanged.
**Migration:** part of `migrate-shows`.
**Test procedure:** `pytest tests/test_projects.py -q` (stub planner): three ideas → three modes; invalid planner JSON → fallback; `--mode` override recorded as `user`; creation with empty `books/` and `STARDOCK_DISABLE_MEM0=1` succeeds. T15.
**Expected output:** pass. **Failure conditions:** any call into `epub_processor`, `reference_memory_sync` or `book_knowledge` extraction during prompt-only creation (assert with mocks); a mode-name comparison outside `project_models.py` (grep for `== 'serialized_fiction'` etc.).
**Rollback:** delete `data/projects/`; `new-show` keeps working. **Dependencies on other changes:** BASE-002, BASE-003.
**Acceptance criteria:** T15; the capability grep is clean.
**Verification status:** models **tested**; proposal and creation flow proposed.

## GEN-003 — Project isolation: memory, voices, metadata

**Priority:** P0 · **Status:** NEW
**Current behavior:** Mem0 uses three installation-wide namespaces — `user_id="reference_materials"`, `"episodes"`, `"characters"` (`mem0_client.py:270, 297, 324, 341, 360, 386`). Episode memories of different shows are separated only by a `series` string in metadata. `voices/voice_config.json` is one global name→voice map. `episode_metadata.py` keeps a global series and tag registry.
**Source evidence:** as cited; `reference_memory_sync.py:160–206`.
**Problem:** A book or memory from one project can surface in another; same-named characters collide.
**Root cause:** Single-show origin.
**Desired behavior:** No read or write crosses a project boundary without explicit sharing.
**Proposed architecture:** `mem0_client` helper `ns(project_id, kind) -> f'{project_id}:{kind}'` used by every add/search/get; kinds `refs`, `canon`, `episodes`, `characters`. Legacy unprefixed namespaces are read only for the project flagged `legacy_namespace: true` (the migrated Star Trek show).
**Files to change:** `mem0_client.py` (all `add_*`/`search_*`/`get_*` gain `project_id`), `reference_memory_sync.py`, `episode_memory.py`, `book_knowledge.py`, `story_structure.py` (callers), `dialogue_engine.py` (per-show voices, with AUDIO-006), `episode_metadata.py` (registries keyed by project). **Files to create:** `tests/test_isolation.py`.
**Dependencies:** STORYOS-001, GEN-001.
**Database/schema changes:** none beyond the namespace strings; Mem0 metadata always includes `project_id`.
**Implementation instructions:** 1. Add `project_id` as a required keyword on the client methods; calling without it raises (no default). 2. Update callers. 3. `shared_reference_projects`: reference search unions the listed projects' `refs` namespaces — references only. 4. Add an isolation test that creates two projects with a fake Mem0, writes to both, and asserts every query returns only its own records. 5. A static test greps for the literal strings `"reference_materials"`, `"episodes"`, `"characters"` used as `user_id`.
**Code example (SKETCH):** `self.client.add(content, user_id=ns(project_id, 'refs'), metadata={**metadata, 'project_id': project_id}, infer=False)`
**Existing-system compatibility:** the legacy project keeps reading its old namespaces; nothing is copied or deleted in Mem0.
**Migration:** none required; optional `mem0 reindex --project <id>` rewrites legacy entries into the prefixed namespace.
**Test procedure:** `pytest tests/test_isolation.py -q`; T18.
**Expected output:** pass. **Failure conditions:** any Mem0 call without `project_id`; a search result whose metadata `project_id` differs from the caller's and is not in its share list.
**Rollback:** revert. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T18.
**Verification status:** proposed.

## REF-001 — Reference registry on the existing ingestion path

**Priority:** P1 · **Status:** NEW
**Current behavior:** `ingest` processes an EPUB into `books/<book_id>/`; `sync-memory` pushes all sections of all books to one Mem0 namespace; `analyze` runs style-and-content analysis; the series-bible extractor (`SeriesBibleExtractor`) makes one global bible from all books (doc 16 §A3).
**Source evidence:** `epub_processor.py:57–135`; `reference_memory_sync.py:38–206`; `book_knowledge.py:178–240`; `ingest_all.py`; `cli_entrypoint.py` commands `ingest` (`:98`), `analyze` (`:253`), `sync-memory` (`:266`).
**Problem:** No purpose, rights, project scope or enable switch; EPUB only; any book becomes universal canon.
**Root cause:** References were designed as a single franchise library.
**Desired behavior:** doc 16 §D1–D2, §C4. Same ingestion code, with a registry in front.
**Proposed architecture:** `story_os/references.py` *(new)*: `add_reference(path, project_id, purposes, rights, show_id=None) -> ReferenceSource`, `list_sources(project_id, *, enabled_only=True, purpose=None)`, `set_enabled`, `load_source`, `audit(event)`. Loaders: `epub_processor.process_epub` (existing) and new `process_text`, `process_markdown`, `process_docx`, `process_pdf`, `process_html` in the same module, each returning the existing chapter/section structure.
**Files to change:** `epub_processor.py` (new loaders; `process_file` dispatcher), `reference_memory_sync.py` (`sync_book(book_id, project_id, source_id, purposes)`; skip technique-only sources), `ingest_all.py` (`--project`, `--purpose`, `--rights`), `cli_entrypoint.py` (`reference add|list|show|enable|disable`; `ingest` kept as an alias that requires `--project` and `--purpose`). **Files to create:** `story_os/references.py`, `tests/test_references.py`, small fixture files in each format.
**Dependencies:** GEN-001, GEN-003. Optional packages for formats: `python-docx`, `pypdf` (check licences when adding; both are permissive at the time of writing — **UNVERIFIED** today). EPUB needs none new.
**Database/schema changes:** `data/projects/<id>/references/…` (doc 16 §C2); `ReferenceSource` JSON (doc 16 §D2).
**Implementation instructions:** 1. `source_id = 'SRC-' + sha256(file)[:12]`; adding the same file twice to one project returns the existing record. 2. Require `--purpose` (one or more) and `--rights` (default `unspecified`); the model validator enforces rights for world/adaptation. 3. Dispatch to a loader; record `legacy_book_id`. 4. Run only the extractors for the selected purposes (REF-002/003/004). 5. Append an audit line for every state change. 6. `list_sources` is the only way other modules find references; it filters by project (plus explicit shares), enabled, not removed, purpose.
**Code example (SKETCH):**
```python
def add_reference(path, project_id, purposes, rights, show_id=None):
    digest = sha256_file(path); sid = f'SRC-{digest[:12]}'
    if (existing := _try_load(project_id, sid)): return existing
    book = epub_processor.process_file(path)                 # existing structure
    src = ReferenceSource(source_id=sid, project_id=project_id, show_id=show_id,
                          source_format=_fmt(path), title=book['title'], author=book.get('author', ''),
                          purposes=purposes, rights=rights, ingested_at=time.time(),
                          content_sha256=digest, legacy_book_id=book['book_id'])
    _save(src); audit({'op': 'add', 'source_id': sid, 'purposes': purposes, 'rights': rights.status})
    return src
```
**Existing-system compatibility:** books already ingested are registered by migration as legacy references of the legacy project; the old commands keep working with the two new required flags.
**Migration:** `reference import-legacy --project <id>` lists `books/*` and registers each.
**Test procedure:** `pytest tests/test_references.py -q`: one file per format loads to sections; duplicate add is idempotent; `world_building` with `unspecified` rights is refused; a source in project A is invisible from project B; technique-only source triggers no Mem0 sync (mock).
**Expected output:** pass. **Failure conditions:** any extractor running for an unselected purpose; a source visible across projects without sharing.
**Rollback:** delete `references/`; old commands unaffected. **Dependencies on other changes:** GEN-001, GEN-003.
**Acceptance criteria:** T16, T18 (reference part), T20.
**Verification status:** schemas **tested**; registry proposed.

## REF-002 — Technique profiles and influence control

**Priority:** P1 · **Status:** NEW
**Current behavior:** One global `style_profile.json` of free-text fields produced from all books (`book_knowledge.py:86–108`), injected into every system prompt; includes `recurring_motifs`. No user control.
**Source evidence:** `STYLE_EXTRACTION_PROMPT`; `KnowledgeContext.build_system_prompt`; `book_style_analysis.py:214–417`.
**Problem:** Style cannot be scoped, weighted, combined, previewed or switched off; free text can carry content.
**Root cause:** Style was extracted as prose for one show.
**Desired behavior:** doc 16 §D3–D4.
**Proposed architecture:** in `story_os/references.py`: `extract_style_profile(source) -> StyleProfile`, `name_leak_guard(profile, source) -> list[str]`, `save_binding`, `resolve_style(...)`, `render_directives(...)` (the last two copied from the reference file, already tested), `style_adherence(script, resolved) -> dict`.
**Files to change:** `book_knowledge.py` (`KnowledgeContext(project_id, show_id)`; `build_system_prompt` uses directives; the old style profile is read only for the legacy project), `story_structure.py` (pass scope), `cli_entrypoint.py` (`reference bind|resolve|edit-profile|reset`). **Files to create:** tests in `tests/test_reference_style.py`.
**Dependencies:** REF-001; `nltk` (already required by `book_style_analysis.py`).
**Database/schema changes:** `profiles/<source_id>.v<N>.json`, `bindings.json`, `data/shows/<id>/style_baseline.json`.
**Implementation instructions:** 1. Copy `StyleProfile`, `ReferenceBinding`, `resolve_style`, `render_directives`, `DIRECTIVES`, trait tables; complete `DIRECTIVES` for all nine numeric traits (three are written; the rest fall back to band words until written). 2. Extraction per doc 16 §D4: sample → statistics → one extractor call returning only the closed-vocabulary JSON → validation → guard. Map statistics to `sentence_length` and `dialogue_density` deterministically (document the mapping constants in code). 3. Guard: names from `BookStyleAnalyzer._identify_characters` plus capitalised bigrams occurring ≥ 3 times; fail the extraction if any appears in the profile or in rendered directives. 4. Baseline profile at show creation (planner call constrained to the same schema). 5. Bindings CRUD with audit lines. 6. The assembler calls `resolve_style` for the scene/segment scope and passes rendered directives; store the trace in the generation trace. 7. `style_adherence` after drafting (advisory).
**Code example (VERIFIED — excerpt of the executed reference):**
```python
total = sum(w for _, w, _ in contrib)
v = base + sum(w * (p - base) for _, w, p in contrib) / max(1.0, total)
```
**Example input → output:** binding `{influence: 0.4, selected_traits: {pacing: 0.7, atmosphere: 0.8, dialogue_density: 0.3, descriptive_density: 0.5, narrative_complexity: 0.6}}` on a source whose profile has pacing 0.2 and a baseline of 0.5 → weight 0.28 → resolved pacing `0.5 + 0.28 × (0.2 − 0.5) = 0.416` → band "moderate" → directive "Balanced pace."; raising influence to 1.0 → 0.29 → "Unhurried; allow pauses."
**Existing-system compatibility:** projects without bindings get the baseline; the legacy project keeps its old style text.
**Migration:** none.
**Test procedure:** `python reference/reference_models.py`; `pytest tests/test_reference_style.py -q`: extraction with a stub returning a name → rejected by validation or guard; resolution cases; directives contain no `%`, source ID, title or author; T16, T17, T19, T20.
**Expected output:** `OK reference_models`; pass.
**Failure conditions:** a prompt containing a reference's title, author or text for a technique-only source; non-deterministic resolution; a percentage in a prompt.
**Rollback:** `reference reset`; revert. **Dependencies on other changes:** REF-001.
**Acceptance criteria:** T16, T17, T19, T20.
**Verification status:** blending, isolation and rendering **tested**; extraction proposed. Audible effect of directives **unverified**.

## REF-003 — Factual research: claims, citations, conflicts

**Priority:** P1 · **Status:** NEW
**Current behavior:** None. Reference chunks are pasted into prompts as "Reference Material" (`book_knowledge.py:387–422`) with no citation.
**Source evidence:** as cited.
**Problem:** Factual scripts would be unsourced; contradictions between sources invisible.
**Root cause:** References were lore, not evidence.
**Desired behavior:** doc 16 §D5.
**Proposed architecture:** `story_os/claims.py` *(new)*: `extract_claims(source) -> list[FactClaim]`, `verify_quote(claim, section_text)`, `find_conflicts(claims)`, `ClaimStore(project_id)` (append-only `claims.jsonl`, latest line per `claim_id` wins), `retrieve(topic, k)`, `check_script(script, store) -> list[Finding]`.
**Files to change:** `story_os/references.py` (purpose dispatch), `story_os/assembler.py`, `quality_checker.py`. **Files to create:** `story_os/claims.py`, `tests/test_claims.py`, a small two-source fixture with one deliberate disagreement.
**Dependencies:** REF-001, BASE-002 (extractor, judge), QUALITY-003 (`judge.claim`).
**Database/schema changes:** `claims.jsonl` (`FactClaim`).
**Implementation instructions:** 1. Extract per section with locator and verbatim quote; reuse the CANON-002 quote normaliser. 2. Drop unverifiable claims; log counts. 3. Conflicts: candidate pairs by token overlap on entities and numbers → single-claim judge → link both ways. 4. Never merge or average; `support` is computed by the model validator. 5. Retrieval for planning by keyword plus optional Mem0 search in `<project>:refs`. 6. `check_script`: extractor lists factual statements with line IDs → map to claims (ID markers the writer was asked to keep in a non-voiced `claim_ref` field on the line) → findings per QUALITY-001 amendment. 7. Human sign-off: `claims verify CL-… --by <name>`.
**Code example (VERIFIED — model behaviour in the reference file):** a claim with `conflicts_with` gets `support == 'contested'` and `must_flag_uncertainty is True`; two citations from different sources → `corroborated`; none → `unsupported`.
**Example input → output:** sources A ("opened to traffic in 1883") and B ("the 1884 opening") → `CL-1` and `CL-2`, each contested; the segment card must choose present-both / prefer-with-reason / omit; a script line stating "1883" flatly → finding "contested claim stated as settled".
**Existing-system compatibility:** fiction projects are unaffected unless they bind a research source, in which case claims are offered to the planner as constraints.
**Migration:** none.
**Test procedure:** `pytest tests/test_claims.py -q`: fabricated quote rejected; conflict linked both ways; unmapped factual statement flagged; figure mismatch flagged. T21.
**Expected output:** pass. **Failure conditions:** a claim stored without a verified quote; two conflicting claims merged; an uncited statement passing in documentary/educational mode.
**Rollback:** disable the factual rule set. **Dependencies on other changes:** as listed.
**Acceptance criteria:** T21.
**Verification status:** claim model **tested**; extraction and checking proposed; accuracy unmeasured.

## REF-004 — Authorised world building and adaptation

**Priority:** P2 · **Status:** NEW
**Current behavior:** `SeriesBibleExtractor` merges all books into one bible with fixed queries; no rights; no distinction between source facts and inventions.
**Source evidence:** `book_knowledge.py:50–84, 178–296`.
**Problem:** Reference lore becomes canon automatically and untraceably.
**Root cause:** Single-franchise design.
**Desired behavior:** doc 16 §D7.
**Proposed architecture:** `story_os/references.py`: `extract_world(source) -> WorldExtract` (generic prompt; sampling by the source's headings; output entities and events with locators and quotes), `import_world(extract, store)` (writes `CanonEvent(origin='source')`, character and location stubs with `source_id`), `adaptation_outline(source) -> list[ChapterSummary]`.
**Files to change:** `book_knowledge.py` (extractor generalised and made per-source), `story_os/canon_store.py`, `story_os/scene_cards.py` (`SceneCard.adapts: Optional[dict]`), `story_os/assembler.py`. **Files to create:** `tests/test_world_reference.py`.
**Dependencies:** REF-001, CANON-001, CHAR-001.
**Database/schema changes:** `origin`, `source_id` on events (done in the reference file); `characters/C*.json` gains `established_by: source_id | null`.
**Implementation instructions:** 1. Refuse unless rights qualify (model validator). 2. Verify each extracted fact's quote against the source. 3. Import as canon with `origin='source'`; conflicts between two world sources are listed for the user to resolve — not auto-merged. 4. Consistency check (CANON-002 step 5) treats source events like any canon. 5. Adaptation: cards carry `adapts`; the writer may see the adapted passage; show notes carry `attribution_text`.
**Code example (pseudocode):** `store.append_events([CanonEvent(..., status='canon', origin='source', source_id=sid, evidence=Evidence(episode_id=f'REF:{sid}', line_ids=[locator], quote=q), provenance=Provenance(..., verified_by=['quote_match']))])`
**Existing-system compatibility:** the legacy bible remains for the legacy project.
**Migration:** none.
**Test procedure:** rights refusal; imported events carry `origin='source'`; a generated script contradicting a source event raises a consistency error; `canon show --origin generated` excludes source events.
**Expected output:** pass. **Failure conditions:** world import from a technique-only source; source and generated facts indistinguishable.
**Rollback:** `reference purge` (REF-005) for unapproved material; revert. **Dependencies on other changes:** as listed.
**Acceptance criteria:** situation C of doc 16 §C4 demonstrable on a small owned-lore fixture.
**Verification status:** proposed.

## REF-005 — Reference lifecycle and generation snapshots

**Priority:** P1 · **Status:** NEW
**Current behavior:** No way to disable or remove a reference; removing a book's files leaves its Mem0 entries and bible content in place.
**Source evidence:** `reference_memory_sync.py` (no delete path used by any command); `book_knowledge.py:164–187`.
**Problem:** Reference changes are all-or-nothing and can orphan or erase history.
**Root cause:** Not designed.
**Desired behavior:** doc 16 §D6.
**Proposed architecture:** `references.remove(source_id)`, `references.purge(source_id)`, `references.snapshot(episode_id)`; append-only `audit.jsonl`.
**Files to change:** `story_os/references.py`, `story_os/jobs.py` (stage hashes include the resolved style and enabled-source list), `cli_entrypoint.py` (`reference remove|purge`, `project delete`). **Files to create:** `tests/test_reference_lifecycle.py`.
**Dependencies:** REF-001, REF-002; AUTO-001 for hash integration.
**Database/schema changes:** `episodes/<id>/reference_snapshot.json`: `{resolved_style, bindings, sources:[{source_id, title, purposes, rights.status, content_sha256}], created_at}` written when an episode is approved; `source_purged: true` flag on kept canon/claims.
**Implementation instructions:** 1. `remove` sets `removed_at`; queries exclude it. 2. `purge` deletes profiles, uncited claims, cached text and Mem0 entries for the source; keeps the source record, audit log, and any canon event or claim referenced by an approved or published episode (flagged). 3. Changing a binding never touches approved episodes; unpublished drafts are marked stale through the job hash. 4. `project delete` archives first and asks for confirmation.
**Code example (pseudocode):** `if claim.claim_id in cited_by_approved: keep(flag='source_purged') else: delete`
**Existing-system compatibility:** additive. **Migration:** none.
**Test procedure:** T19 and: purge keeps cited claims and source events of approved episodes; the audit log has one line per operation; the snapshot of an approved episode is unchanged after a binding edit.
**Expected output:** pass. **Failure conditions:** any change to approved canon, script or snapshot caused by a reference operation; missing audit line.
**Rollback:** `removed_at` can be cleared; a purge is irreversible by design and requires `--yes`.
**Dependencies on other changes:** as listed.
**Acceptance criteria:** T19, T20.
**Verification status:** proposed.

## GEN-002 — Nonfiction pipeline: segment cards and factual editorial

**Priority:** P1 · **Status:** NEW
**Current behavior:** Only the fiction pipeline exists.
**Source evidence:** `story_structure.py` generation path; doc 01 §4.
**Problem:** Documentary, educational and conversational projects would be planned as dramas.
**Root cause:** Single pipeline.
**Desired behavior:** doc 16 §C3 (nonfiction counterparts table).
**Proposed architecture:** `story_os/segment_cards.py` *(new, parallel to `scene_cards.py`)*: `build_segment_prompt(episode, framework, claims, context)`, `parse_segments`, `validate_segments(cards, hosts, store)`, `segments_to_scenes` (so `episode['scenes']` keeps its shape and audio code is unchanged), `render_segment_block`. `StoryStructure._generate_segments_from_cards` mirrors the tested scene-card method.
**Files to change:** `story_structure.py` (dispatch on `outline` capability; script prompt variant for hosts), `quality_checker.py` (factual rule set — QUALITY-001 amendment). **Files to create:** `story_os/segment_cards.py`, `tests/test_segment_cards.py`.
**Dependencies:** GEN-001, NARRATIVE-001 (pattern), NARRATIVE-002 (families), REF-003 for claims (without research sources the pipeline still runs; claims are created from the draft as `unsupported`).
**Database/schema changes:** `SegmentCard` (reference file); lines may carry a non-voiced `claim_ref`.
**Implementation instructions:** 1. Copy `SegmentCard`. 2. Validation: numbering; non-empty purpose, key points and takeaway; `builds_on` references earlier segments; speakers are known hosts; for claims modes every key point that asserts a fact lists a `claim_id` or is marked "general knowledge"; educational: every curriculum objective of the episode is covered by a segment and the last segment is a recap. 3. Writer prompt: segment card, previous segment's transition and last lines, host personas, style directives, the claims with support levels and the instruction to voice uncertainty. 4. After drafting run `claims.check_script`. 5. Sequential writing and one re-ask on validation failure, as in NARRATIVE-001.
**Code example (SKETCH):** validation mirrors `validate_cards`; for example `if cap('claims') and not card.claim_ids and _asserts_fact(card): issues.append(f'segment {i}: key points without claims')`.
**Example input → output:** project "how bridges stay up", episode 2 objective "tension vs compression" → six segments: cold open (a rope and a brick), objective, explanation, worked example (suspension vs arch), check understanding, recap; each explanatory segment lists claim IDs or "general knowledge".
**Existing-system compatibility:** fiction modes never enter this path.
**Migration:** none.
**Test procedure:** `pytest tests/test_segment_cards.py -q` with stubs: valid cards accepted; a segment asserting a figure without a claim rejected; missing recap rejected for educational; prompts sequential (same assertions as the scene-card test). T21.
**Expected output:** pass. **Failure conditions:** fiction fields (goal/opposition/turn) required in a nonfiction outline; a nonfiction episode calling canon extraction.
**Rollback:** set the project mode to a fiction mode or disable creation of claims modes in config.
**Dependencies on other changes:** as listed.
**Acceptance criteria:** T21; an educational and a conversational fixture episode complete end to end with stub models.
**Verification status:** `SegmentCard` **tested**; pipeline proposed. Quality of generated nonfiction **unverified**.
