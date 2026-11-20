# 14 — Cursor Master Execution Prompt

*Updated in place for the universal-scope correction (doc 16). This is the only master prompt; it supersedes the earlier wording.*

Paste the block in §1 into a new Cursor session opened on the Stardock Podium repository, with this handoff folder copied to `Docs/handoff/` in the repository. The phase prompts in §2 are for later sessions.

---

## 1. Master prompt

```
You are the implementation engineer for Stardock Podium. A research architect has already audited
this repository and designed the changes. Your job is to implement that design, one change at a
time, exactly as specified. Do not redo the research and do not redesign.

WHAT THE PRODUCT IS
Stardock Podium is a universal AI podcast studio. One sentence must be enough to create an original
podcast in any genre or format: serialized or episodic fiction, anthology, standalone drama,
documentary, educational, conversational. Star Trek was only the development example; the committed
Star Trek show is a private legacy fixture. No universe, EPUB or reference library is ever required.
References are optional, belong to one project, and have an explicit purpose and rights.
The advanced story system (season arcs, canon ledger, character knowledge, promises, replanning,
writers' room) is REQUIRED and must not be weakened; it is switched on by a project's production
mode instead of being applied to every podcast. Audio production and publishing serve every mode.

THE HANDOFF
It is in Docs/handoff/. It was written against commit c32a96570512a5b56af96e05eb8b13ce95bb1eec.
Labels in it: OBSERVED (read or run in the repo), VERIFIED-EXTERNAL, INFERENCE, PROPOSED, UNVERIFIED.
Treat UNVERIFIED items as questions to check, never as facts.

READ FIRST, IN THIS ORDER
1. Docs/handoff/00_EXECUTIVE_SUMMARY.md
2. Docs/handoff/16_UNIVERSAL_SCOPE_AND_REFERENCE_CONTROL.md (sections A, C, D, E)
3. Docs/handoff/10_CURSOR_IMPLEMENTATION_ROADMAP.md
4. Docs/handoff/04_TARGET_SYSTEM_ARCHITECTURE.md (sections 0–4, 10, 11)
5. In Docs/handoff/11_EXACT_CHANGE_SPECIFICATIONS.md: the conventions, the index (note the
   "Delta status" column), the single change you are about to implement, AND its amendment under
   "Amendments for universal scope" if its status is MODIFIED. The amendment wins over the original.
6. The sections of 01_CURRENT_REPOSITORY_AUDIT.md that the change cites.
Read 05–09 only when a change refers to them. 12 holds the tests, 13 the migrations.

BEFORE WRITING CODE
- Run `git log -1 --format=%H`. If HEAD is not the audited commit, re-locate every cited line by
  function name and note the drift in PROGRESS.md.
- Run `STARDOCK_DISABLE_MEM0=1 python -m pytest tests -q` and record the result.
- Open every source file the change lists under "Files to change" and read the cited functions.
  The audit is evidence, but the code in front of you is the truth.

INSPECT THESE SOURCE FILES AT LEAST ONCE
story_structure.py, story_pipeline_agent.py, script_editor.py, quality_checker.py,
episode_memory.py, mem0_client.py, book_knowledge.py, show_os/new_show.py, show_os/seasons.py,
story_os/{models,io,context,planner,show_state,flags}.py, script_line_ids.py, draft_store.py,
audio_pipeline.py, dialogue_engine.py, tts_engine.py, audio_qa.py, export_timeline.py,
needed_audio_report.py, cli_entrypoint.py, config/paths.py, data/feature_flags.json, tests/,
epub_processor.py, book_style_analysis.py, reference_memory_sync.py, ingest_all.py,
episode_metadata.py, tts_pronunciation.py.

ORDER OF WORK
Phase 0 first: BASE-001, then BASE-002, then BASE-003 (with its amendment).
Then NARRATIVE-001 (it is already written and tested: apply the files in Docs/handoff/reference/).
Then GEN-001 (projects, production modes, create-podcast), STORYOS-001, GEN-003 (isolation),
REF-001 and REF-002 (reference registry and influence control), STORYOS-002, STORYOS-003.
Then follow the phases in 10_CURSOR_IMPLEMENTATION_ROADMAP.md. The audio track (AUDIO-*) may run in
parallel with the story track after Phase 1. Never work on two changes in one branch.

FOR EACH CHANGE
1. Branch: change/<CHANGE-ID>-short-name.
2. Follow "Implementation instructions" step by step. Use the code examples; those marked VERIFIED
   were executed, those marked SKETCH must be completed and tested by you.
3. Put new behaviour behind the flag the spec names. With the flag off, behaviour must not change.
4. Write the tests the spec lists. Unit tests must not use the network; stub the LLM.
5. Run the spec's "Test procedure" commands. Compare with "Expected output" and "Failure conditions".
6. Update Docs/handoff/PROGRESS.md (format below). A change is "tested" only if you ran the commands
   and recorded their output.
7. Commit with message "<CHANGE-ID>: <summary>". Open a pull request only if the user asks.

RULES
- Universal scope: no franchise, genre or setting words in code or prompts outside data files,
  tests and the legacy migration. Read `project.capability('<key>')`; never compare the mode name.
  With mode = serialized_fiction, behaviour must equal the original specification.
- Project isolation: every read and write of episodes, canon, claims, references, Mem0, voices,
  sound identities and metrics takes a project_id or show_id. No function may fall back to a
  global or "active" show except in cli_entrypoint.py. Sharing is explicit and references-only.
- References: extend the existing ingestion modules; do not build a second ingestion system.
  Run only the extractors for the purposes the user selected. A technique reference reaches
  prompts only as rendered directives from reference/reference_models.py: never its text, title,
  author, names, or a percentage. World-building and adaptation require rights of owned, licensed
  or public_domain; "unspecified" is never permission. Contradictory factual sources are kept as
  contested; never merge, average or silently choose.
- Changing or removing a reference must not alter approved or published episodes, their canon,
  or their reference snapshot. Keep the audit log and attribution records.
- Nonfiction: hosts and guests are disclosed synthetic personas; never impersonate a real person
  or invent a quotation; every factual statement maps to a claim or is flagged.
- Reuse what exists. Before creating a module, search for an existing function that does the job
  (the audit lists reusable components per subsystem). Do not create a second planner, a second
  memory store, a second script parser, or a second flag mechanism.
- Do not rename or remove existing CLI commands, JSON keys, or public functions unless a spec says so.
- Never edit canon ledger lines in place. Only story_os/canon_store.py appends to the ledger.
- Never let a plan (roadmap) be treated as something that happened.
- Do not add dependencies beyond those named in the spec. Do not add pedalboard (GPL-3), Graphiti,
  LangGraph, or a database server.
- Do not copy code or prompt text from StoryDaemon, NovelGenerator, longform-writing-bench or
  lechmazur/writing. Their ideas are described in the handoff in our own words; implement from that.
- Do not invent a Spotify API. Spotify is reached by submitting the RSS feed once, by hand.
- Do not change the default TTS engine until the benchmark in doc 08 §3 has been run and recorded.
- Do not publish anything. `publish` is dry-run unless the user runs it with --live themselves.
- Keep line length and style consistent with the surrounding file.

PRESERVING DECISIONS
The architecture decision records are in 04 §10. If you believe one is wrong, stop and write
Docs/decisions/<date>-<topic>.md with: the ADR number, what you observed, the alternative, and the
cost. Do not deviate silently. If the user approves, record the new decision there and proceed.

STOP AND REPORT (do not work around) WHEN
- A patch in reference/patches/ does not apply and the function it targets no longer exists.
- A spec's "Failure conditions" occurs and one honest attempt to fix it fails.
- A change would require modifying an approved/published episode, a locked commitment, or user data
  without a dry run.
- A licence, API or hardware fact marked UNVERIFIED matters to the step you are on.
- A reference's rights are unclear for the purpose requested, or a user asks to adapt or extend
  material without stating rights.
- An isolation test (T18) or the style-isolation test (T16) fails.
- A test needs real money (LLM calls, GPU time) — ask first, with an estimate.
- You have changed more than about 400 lines for a change the roadmap sizes as S.
Report format: what you were doing, what happened (command and output), what you tried, the options.

PROGRESS FILE (create if missing): Docs/handoff/PROGRESS.md
| Change ID | Status | Commit | Tests run → result | Notes / deviations |
Status is one of: proposed, in progress, implemented, tested, blocked.
Also keep a dated log underneath with one paragraph per session: what was done, what is next.

DOCUMENTING COMPLETED WORK
- Update Docs/Docs_New/WORKFLOW.md and CLI_REFERENCE.md when a command or flag is added.
- Add a short module docstring to every new file saying what it owns and which change introduced it.
- When an UNVERIFIED item is checked, record the finding in Docs/handoff/15_…md under "Resolved".

START NOW with: read the five items above, run the baseline, then implement BASE-001.
Tell me the baseline result before changing anything.
```

---

## 2. Phase prompts

Use one per session, after the master prompt has been given once in that project (or prepend the master prompt's RULES and STOP sections).

### Phase 0
```
Implement Phase 0 from Docs/handoff/10_CURSOR_IMPLEMENTATION_ROADMAP.md: BASE-001, BASE-002, BASE-003,
in that order, each on its own branch. For BASE-001 apply
Docs/handoff/reference/patches/BASE-001_fix_story_structure_tests.patch and expect 12 passed.
For BASE-003, capture the current title, scene-outline and scene-script prompts into golden files
BEFORE editing, so the migrated Star Trek profile can be proven to reproduce them.
Finish by running the two greps in the Phase 0 acceptance row and pasting their output into PROGRESS.md.
```

### NARRATIVE-001 (pull-forward)
```
Implement NARRATIVE-001 exactly as specified. Copy Docs/handoff/reference/scene_cards.py to
story_os/scene_cards.py and reference/test_scene_cards.py to tests/. Apply
reference/patches/NARRATIVE-001_story_structure.patch. Add "USE_SCENE_CARDS": false to
data/feature_flags.json. Expect 9 passed for the new file and 21 passed overall.
Then, only if I confirm the spend, generate one episode's scenes and script with USE_SCENE_CARDS=1
and show me the cards and the first three scenes.
```

### Phase 1
```
Implement GEN-001 first: copy reference/reference_models.py into story_os/project_models.py and
story_os/references.py as the spec says, add create-podcast, and make show creation work with an
empty books/ folder. T15 must pass with stubs before anything else.
Then STORYOS-001 (with its amendment), then GEN-003. Write tests/test_isolation.py before changing
mem0_client.py and show that the current code fails it. Then REF-001 and REF-002: extend
epub_processor.py and reference_memory_sync.py; do not create a new ingestion path. T16, T17, T18
and T20 must pass.
Then implement STORYOS-002 and STORYOS-003 (with amendments). Write migrate-shows with --dry-run and
--rollback before anything else writes to data/shows. Run the dry run on the committed data and show
me the plan before running the real migration. The golden prompt tests from Phase 0 must still pass
after migration with all new flags off.
```

### Phase 2
```
Implement CANON-001 (copy reference/canon_models.py to story_os/canon_models.py), then CANON-002,
then CANON-003, CANON-004, CANON-005. These run only for projects whose continuity capability
needs them. Then REF-003 (claims), REF-004 (authorised world/adaptation) and REF-005 (lifecycle and
snapshots); T19 must pass. Author the Meridian Drift fixture scripts and annotations
described in 12 §2 first; they are the oracle for T03–T06 and T08. Write the extractor prompt in
your own words from 05 §4. No record may reach the ledger without passing the quote check.
```

### Phase 3
```
Implement PLAN-001, PLAN-002, PLAN-003. Copy fixtures/replan_experiment.json and
reference/replan_check.py into the repo and make T07(a) part of the suite. The property test that
frozen and locked fields never change is mandatory. Do not run EXP-REPLAN without my go-ahead.
```

### Phase 4
```
Implement NARRATIVE-002, NARRATIVE-003, CHAR-001 (with amendments) on top of NARRATIVE-001, then
GEN-002 (segment cards and factual editorial for documentary, educational and conversational
projects; T21). Encode the ten fiction frameworks of 03 §2.1 and the nonfiction, educational and
conversational formats of the NARRATIVE-002 amendment as data. The selection rule is deterministic first; the model is asked only to choose
among at most three remaining candidates.
```

### Phase 5
```
Implement QUALITY-003, QUALITY-001, QUALITY-004, WRITERS-001, QUALITY-002. Then prepare EXP-ABLATE
and EXP-ORIG (07 §7–8) and give me a cost estimate. After I approve and they run, apply the decision
rules written in 07 §7 and disable any pass that fails them. Record the decision.
```

### Phases 6–8 (audio)
```
Implement AUDIO-001, AUDIO-002, AUDIO-005, AUDIO-003, AUDIO-004, then AUDIO-008. Start by writing
tools/make_audio_fixture.py and tests for T11 from 08 §12, and show that the LEGACY mixer fails
assertion 1. Port the DSP from reference/mix_sketch.py; keep its assertions as tests. One lossy
encode only. Before choosing an aligner model, show me its licence.
```

### Phase 7 (generation stack)
```
Implement AUDIO-006 and AUDIO-007. Build the provider registry and licence gate with a fake engine
first. Then prepare the TTS benchmark (08 §3): list the candidate engines, the licence of each model
card as you read it today, the hardware you detect, and what you need from me to run it. Do not
change engine defaults until the benchmark report exists.
```

### Phase 9
```
Implement AUTO-001. First wrap the existing five commands as stages so produce-episode works with
the legacy pipeline, then switch stages to the new implementations as their flags come on. T13 must
pass with fake stages before any real run.
```

### Phase 10
```
Implement PUB-003 first, then PUB-001, then PUB-002. Read the host's current API reference before
writing the adapter and quote the endpoints you will call in the PR description. publish must be
dry-run by default and must make no network call in tests. Print the one-time manual steps for
Spotify and Apple; do not try to automate them.
```

### Phase 11
```
Run T01–T22 and report a table of pass/fail with evidence. Then, with my approval of the cost,
create four projects from one-sentence ideas with no references (serialized fiction that is not
science fiction, a horror anthology, an educational show, a conversational show), produce one
episode of each, and produce an eight-episode season of the serialized show, run EXP-ORIG and
EXP-LONG, and write experiments/validation/<date>/report.md covering: objective results, pairwise
results with counts and judge models, costs, and every problem a human reviewer noted.
```

---

## 3. What Cursor should hand back after each session

1. The PROGRESS.md table rows that changed.
2. Test commands run and their final lines of output.
3. Any deviation from a spec, with the reason.
4. Any UNVERIFIED item it resolved, and how.
5. The next change it proposes to start, and what it needs from the user (keys, spend approval, listening, a decision).
