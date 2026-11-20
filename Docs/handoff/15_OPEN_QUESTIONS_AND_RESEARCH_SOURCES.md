# 15 — Open Questions and Research Sources

## 1. Open questions for the user

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| Q1 | Is the goal to **monetise** the podcast? | Decides whether revenue-capped and non-commercial model licences are usable | Assume yes; only permissive licences |
| Q2 | Will "Star Trek: Horizon" be kept as a private test show only? | It cannot be published as original work | Keep as a private legacy fixture; create an original show for anything public |
| Q3 | Where do the nine reference voice clips in `voice_config.json` come from, and is there consent or a licence? | Voice-clone rights | Treat as unusable for publishing; design synthetic voices |
| Q4 | What GPU is available locally (model, VRAM)? Is renting a GPU acceptable? | Decides which TTS/SFX/music candidates can be benchmarked | Kokoro on CPU; candidates needing ≤ 12 GB only |
| Q5 | Is sub-line speech editing (changing words inside a take) required, or is line-level replacement enough? | Only a 48 GB, restricted-licence model was found with that claim | Line-level replacement |
| Q6 | How much human review is wanted: roadmap, premise, every episode, or only before publishing? | Sets `auto_approve` and gates | Human approval per episode until phase 11 passes |
| Q7 | How many episodes and concurrent shows are realistically planned in the first year? | If far beyond a few hundred episodes or complex graph queries, revisit ADR-002 | ≤ 3 shows, ≤ 100 episodes |
| Q8 | Which LLMs should fill the writer, editor, extractor and judge roles, and what monthly budget? | Cost and the "different family" rule | Today's model for writer; a different provider's model for editor and one judge |
| Q9 | Should characters be allowed deliberately faulty memory (misremembering) as a story device? | Needs belief machinery first; risk of perceived errors | Not until phase 4 is stable |
| Q10 | Which podcast host? Is a subscription acceptable, or is a self-hosted feed preferred? | Adapter to build | Host with an API; dry-run feed regardless |
| Q11 | What are the origin and licence of `assets/music/*` and the files under `assets/sound_effects`, `assets/ambience`? | Rights report | Mark unknown; regenerate with licensed models |
| Q12 | Target episode length and release cadence? | Scene-count bounds, cost, scheduler need | 30 minutes; manual cadence |
| Q13 | Should narration be used at all, or pure dialogue-and-sound drama? | Changes lint rules and intro/outro handling | Minimal narration; framed episodes allowed |
| Q14 | Are source novels to be used for *style* at all in original shows? | Leakage risk | Off for original shows |

### Added by the universal-scope delta

| # | Question | Why it matters | Default if unanswered |
|---|---|---|---|
| Q15 | Which formats matter first after serialized fiction? | Orders GEN-002 work (documentary, educational, conversational share one pipeline but need separate framework data and checks) | Educational, then conversational, then documentary |
| Q16 | For nonfiction with no sources supplied, may the system publish from general model knowledge? | Accuracy cannot be guaranteed without sources | Generate, mark claims `unsupported`, require human sign-off before publishing |
| Q17 | Should claim verification search the web automatically? | Cost, and which search tool is available | Off; explicit `reference verify` only |
| Q18 | Will conversational shows ever portray real people? | Consent and impersonation | No; guests are disclosed synthetic personas |
| Q19 | Should one project hold several shows sharing a reference library? | Layout already allows it; UI and defaults | One show per project by default |
| Q20 | Which additional reference formats are needed beyond EPUB, text, Markdown, DOCX, PDF, HTML? | Loader work | Those six |

## 2. Unverified items — check before relying on them

| Item | Where used | How to verify |
|---|---|---|
| Any speech/SFX/music model's actual output quality | Doc 08 | Run `EXP-TTS`; listen |
| Model-card licences for Chatterbox weights and ACE-Step weights (repo licence is MIT) | Doc 02 C2, D2 | Read each Hugging Face model card on the day |
| Coqui TTS code licence; exact CPML terms | Doc 02 C5 | Read the licence file in the installed package and the model card |
| Fish Audio revenue threshold figure | Doc 02 C3 | Read `LICENSE` §V in the repository |
| Whether Kokoro or other engines expose word/phoneme timings | Doc 08 §7 | Inspect the engine API; else use forced alignment |
| A commercially usable CTC alignment model and its accuracy on synthetic speech | AUDIO-001 | Choose a model, read its licence, measure on T11 |
| `infer=False` on the Mem0 **managed** client in the installed version | CANON-005 | Call with a mock; read the client signature |
| Transistor create/update/publish endpoint parameters and auth header | PUB-002 | Read developers.transistor.fm |
| Other hosts' API coverage and prices; object-storage prices; RunPod prices | Doc 09 | Fetch on the day |
| Current artwork pixel/file-size limits and AI-disclosure requirements per directory | Doc 09 §4, §8 | Apple Podcasts and Spotify for Creators help pages |
| Existence of an official Spotify ingest API | Doc 09 §6 | Not found; re-check Spotify for Developers before building anything around it |
| Extraction accuracy targets (precision 0.9 / recall 0.8) are achievable | Doc 12 T03 | Measure on the annotated fixture |
| Originality thresholds | Doc 07 §8 | Calibrate on legacy output and public-domain scripts |
| Card JSON reliability and prose quality with real models | NARRATIVE-001 | Generate one episode |
| Complexity estimates | Doc 10 | Track actuals |
| Papers cited from prior knowledge (Re3, DOC, Dramatron, Generative Agents, plot-homogenisation studies) | Doc 02 A5 | Look up before citing externally |
| Windows behaviour of file locks and atomic replace | CANON-001, AUTO-001 | Run T04 and T13 on Windows |
| Mode proposal quality from one sentence | GEN-001 | Try 20 varied ideas; record overrides |
| Technique extraction places texts sensibly on the trait scales; directives change the output audibly | REF-002 | T16/T19 [LIVE] plus blind A/B of two influence settings |
| Claim extraction precision/recall; conflict detection | REF-003 | Annotated two-source fixture |
| Quality of generated nonfiction scripts | GEN-002 | Human review |
| Licences of `python-docx` and `pypdf` | REF-001 | Read on the day |

## 3. Things this research did not do

- No LLM generation; no judgement of actual prose from any pipeline, old or new.
- No audio synthesis or listening; no GPU.
- No run of the existing audio pipeline (needs ffmpeg and engines) — the audio audit is from reading source.
- No call to any publishing or hosting API.
- No inspection of LangGraph beyond licence and activity; no deep read of VibeVoice, F5-TTS or Kokoro source beyond README and licence.
- Search results in the research environment returned links without excerpts, so web facts come only from the pages explicitly fetched (listed below) and from cloned repositories.

## 4. Conflicting or surprising evidence

| Topic | Conflict | How it was handled |
|---|---|---|
| StoryDaemon licence | README and `setup.py` say MIT; no LICENSE file in the repository | Treated as unlicensed for code reuse; ideas re-implemented |
| Chatterbox status | Commits in November 2026, yet the README calls the repository an unsupported archive | Listed as a candidate with a support risk |
| Multi-agent writing | Agents' Room: raters preferred it, yet it was the longest and most repetitive and still behind human stories | Small room, ablation before adoption |
| Absolute vs pairwise scoring | longform-writing-bench uses 0–20 absolute scores; lechmazur/writing abandoned absolute scores for pairwise | Pairwise for decisions; absolute as trend only |
| Graphiti as "the" fiction memory | Strong temporal model, but server-bound and LLM-invalidated; its embedded backend is deprecated | Borrowed the model, not the library |
| Repository docs vs behaviour | `MEMORY_CONTINUITY_SYSTEM.md` describes working continuity; measurement shows mostly noise | Audit follows the measurement |
| README claim "no `--theme` → season arc slot is used" | True only for the script stage; outlining never sees it | STORYOS-002 |

## 5. Sources

### 5.1 Repository under audit
- https://github.com/enstest1/Stardock_Podium_v4 — commit `c32a96570512a5b56af96e05eb8b13ce95bb1eec`, read in full for the modules listed in doc 01; tests run.

### 5.2 Repositories cloned and read on 2026-11-11

| Repository | Newest commit seen | Licence file |
|---|---|---|
| https://github.com/EdwardAThomson/StoryDaemon | 2026-11-02 | none (README: MIT) |
| https://github.com/KazKozDev/NovelGenerator | 2026-10-09 | Business Source License 1.1 |
| https://github.com/EQ-bench/longform-writing-bench | 2025-10-26 | none |
| https://github.com/lechmazur/writing | 2026-10-24 | none |
| https://github.com/getzep/graphiti | 2026-11-11 | Apache-2.0 |
| https://github.com/langchain-ai/langgraph | 2026-11-10 | MIT |
| https://github.com/mem0ai/mem0 | 2026-11-06 | Apache-2.0 |
| https://github.com/OpenMOSS/MOSS-TTS | 2026-09-06 | Apache-2.0 |
| https://github.com/fishaudio/fish-speech | 2026-10-30 | Fish Audio Community License v1.0 |
| https://github.com/resemble-ai/chatterbox | 2026-11-04 | MIT |
| https://github.com/microsoft/VibeVoice | 2026-10-08 | MIT |
| https://github.com/SWivid/F5-TTS | 2026-11-03 | MIT (weights CC-BY-NC per README) |
| https://github.com/hexgrad/kokoro | 2025-08-06 | Apache-2.0 |
| https://github.com/HamSanders/soundbox | 2026-11-10 | MIT |
| https://github.com/ace-step/ACE-Step-1.5 | 2026-08-29 | MIT |
| https://github.com/m-bain/whisperX | 2026-10-22 | BSD-2-Clause |
| https://github.com/MahmoudAshraf97/ctc-forced-aligner | 2026-09-07 | BSD-2-Clause (default model CC-BY-NC 4.0) |
| https://github.com/csteinmetz1/pyloudnorm | 2026-01-04 | MIT |
| https://github.com/spotify/pedalboard | 2026-11-09 | GPL-3.0 |
| https://github.com/Podcastindex-org/podcast-namespace | 2026-10-10 | Public-domain dedication (README, `COPYING.txt`) |

Files read in particular: StoryDaemon `novel_agent/agent/{loop_aging,loop_closure,arc_pressure,throughline,consequences,lore_contradiction_detector,coherence_metrics,thread_registry,fact_extractor,finale}.py`, `docs/LOOP_AGING_BASELINE.md`; NovelGenerator `README.md`, `LICENSE`, `prompts/P03_SCENE_REBASE.md`, `P05_STATE_UPDATE.md`, `P06_FORWARD_UPDATE.md`; longform-writing-bench `README.md`, `data/longform_*criteria*.txt`, `core/metrics.py`; lechmazur/writing `README.md`; graphiti `README.md`, `pyproject.toml`, `graphiti_core/edges.py`; mem0 `mem0/memory/main.py`, `docs/platform/features/direct-import.mdx`; soundbox `README.md`, `docs/API.md`, `docs/new-models-2026-10.md`; fish-speech `LICENSE`, `README.md`, `docs/en/install.md`; MOSS-TTS `README.md`; chatterbox, VibeVoice, ACE-Step-1.5, F5-TTS, kokoro `README.md`; podcast-namespace `docs/tags/transcript.md`, `chapters.md`.

### 5.3 Pages fetched on 2026-11-11
- Apple Podcasts audio requirements — https://podcasters.apple.com/support/audio-requirements
- Spotify help, RSS feeds — https://support.spotify.com/us/podcasters/article/your-rss-feed/
- Spotify community thread, programmatic show submission — https://community.spotify.com/t5/Spotify-for-Developers/API-Request-Programmatic-Podcast-Show-Submission/td-p/7239240
- Transistor pricing — https://transistor.fm/pricing/
- Transistor API upload changelog — https://transistor.fm/changelog/api-upload
- XTTS-v2 licence discussion — https://huggingface.co/coqui/XTTS-v2/discussions/65
- Agents' Room paper — https://arxiv.org/pdf/2410.02603

### 5.4 Could not be fetched
- GitHub repository web pages (blocked for the fetch tool); the repositories were cloned instead, so stars, issues and release pages were not seen.
- developers.transistor.fm, Spotify for Creators submission pages, Hugging Face model cards other than the one above: not fetched.

### 5.5 Read for the universal-scope delta (same day, same commit)
- Repository: `epub_processor.py`, `book_style_analysis.py`, `reference_memory_sync.py`, `ingest_all.py`, `mem0_client.py` namespaces, `episode_metadata.py:604–662`, `tts_pronunciation.py`, and a widened franchise scan.
- No new external sources.

## 6. Resolved (Cursor appends here)

| Date | Item | Finding | Evidence |
|---|---|---|---|
| 2026-11-11 | "RSS is missing" (doc 01, first version) | Wrong: `episode_metadata.generate_episode_feed` emits minimal RSS. Corrected in doc 01, PUB-002 amended | `episode_metadata.py:604–662` |
| | | | |
