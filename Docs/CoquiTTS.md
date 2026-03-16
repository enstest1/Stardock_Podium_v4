<prompt>
<!-- ============================================================= -->
<!--  STARDOCK PODIUM – OFFLINE-FIRST + ELEVENLABS FALLBACK TTS MVP -->
<!--  Single, copy-and-paste coder-agent brief                       -->
<!-- ============================================================= -->

<!-- 1 ◈ CONTEXT & OBJECTIVE -->
<overview>
  Stardock Podium already generates complete Star-Trek-style episodes.
  It relies on ElevenLabs for every spoken line; when credits run out,
  audio generation stops.  
  **Goal:** add an offline Coqui TTS (YourTTS) path while *retaining*
  ElevenLabs as a secondary engine.  The user workflow remains identical
  (HOWTORUN.md), but synthesis order is now: **Coqui ➜ ElevenLabs ➜ TODO**.
</overview>

<!-- 2 ◈ DEPENDENCIES -->
<dependencies>
  <pip>
    pip install torch==2.2.0+cpu -f https://download.pytorch.org/whl/torch_stable.html
    pip install TTS==0.21.4
    pip install soundfile==0.12.1
    pip install elevenlabs==1.1.0
  </pip>
  Append these four lines to <code>requirements.txt</code>.
</dependencies>

<!-- 3 ◈ FILE MAP -->
<interfaceDefinitions>
  <file path="tts_engine.py"          purpose="Facade exposing CoquiEngine & ElevenLabsEngine" />
  <file path="cli/generate_voices.py" purpose="Batch per-line synthesis via façade" />
  <file path="cli/validate_voices.py" purpose="Checks script ↔ voice config ↔ sample WAVs" />
  <file path="voices/voice_config.json" purpose="Unified mapping (new, generated from old registry)" />
  <file path="tools/migrate_registry.py" purpose="One-time helper: convert voices/registry.json ➜ voice_config.json" />
  <!-- modify -->
  <file path="audio_pipeline.py"      purpose="Replace in-file ElevenLabs loop with subprocess call to generate_voices.py" />
  <file path="Docs/HOWTORUN.md"       purpose="Add Coqui install notes; note offline-first behaviour" />
</interfaceDefinitions>

<!-- 4 ◈ INPUT / OUTPUT CONTRACTS -->
<contracts>
  <contract id="voiceConfig">
    <schema><![CDATA[
{
  "engine_order": ["coqui", "eleven"],
  "characters": {
    "Aria T'Vel": {
      "speaker_wav" : "voices/samples/aria.wav",
      "language"    : "en",
      "eleven_id"   : "HV5LQQys2FkXruuXDrZb"
    },
    "Jalen": {
      "speaker_wav" : "voices/samples/jalen.wav",
      "language"    : "en",
      "eleven_id"   : "uLDRhO9layp3hZXPNqPL"
    }
  }
}
]]></schema>
    Characters come from existing <code>voices/registry.json</code>.
    Migration script copies <code>voice_id</code> ➜ <code>eleven_id</code>;
    user supplies <code>speaker_wav</code> paths (fail if missing).
  </contract>

  <contract id="generateCLI">
    <input>--script episodes/&lt;ep&gt;/script.json --config voices/voice_config.json --outdir audio/raw/&lt;ep&gt; [--dry-run]</input>
    <output>One WAV per line: <code>&lt;scene&gt;_&lt;idx&gt;.wav</code>; exit-0 if all created.</output>
  </contract>
</contracts>

<!-- 5 ◈ FLOW -->
<mermaid>
flowchart TD
  V[validate_voices.py] --> L[Loop lines]
  L --> C{File exists?}
  C -- yes --> L
  C -- no --> P[for eng in engine_order]
  P --> Q[try synth via eng]
  Q -->|success| L
  Q -->|SynthError| P
  P -->|all failed| T[create .TODO.wav & log ERROR]
</mermaid>

<!-- 6 ◈ IMPLEMENTATION STEPS -->
<implementationSteps>

  <step id="tts_engine.py">
    Define <code>SynthError</code>, abstract <code>TTSEngine.synth()</code>.
    <code>CoquiEngine</code> (loads YourTTS once; CPU-only)  
    <code>ElevenLabsEngine</code> (reads ELEVENLABS_API_KEY from env).  
    Both call <code>soundfile.write</code> using their model’s sample rate.
  </step>

  <step id="generate_cli">
    Build dict <code>engine_map = {"coqui": CoquiEngine(), "eleven": ElevenLabsEngine()}</code>.  
    Iterate episode script → line, skip if WAV exists.  
    For each engine in <code>config["engine_order"]</code> try synth → break on success.  
    If none succeed, touch <code>TODO.wav</code>, set exit = 1.
  </step>

  <step id="validate_cli">
    • Every character in script must appear in config.  
    • Each <code>speaker_wav</code> exists, 16 kHz mono ≤10 s (check with soundfile).  
    • If “eleven” in engine_order, ensure <code>eleven_id</code> present.  
    Exit 1 on any failure.
  </step>

  <step id="audio_pipeline_patch">
    Replace ElevenLabs loop with  
    <code>subprocess.run([sys.executable,"cli/generate_voices.py",...],check=True)</code>  
    then proceed with existing FFmpeg mix.
  </step>

  <step id="migration_tool">
    Read <code>voices/registry.json</code> → for each entry write skeleton:  
    {name, eleven_id, language:"en", speaker_wav:""} into voice_config.json.  
    Print TODO lines prompting user to record WAVs.
  </step>

  <step id="tests">
    • Unit: mock engines; ensure fallback path invoked.  
    • Integration: offline execution with Coqui only, expect WAVs.  
    • Regression: rename sample wav to trigger ElevenLabs fallback (requires API key in CI secret or skip).
  </step>

</implementationSteps>

<!-- 7 ◈ MINIMUM API SNIPPETS -->
<externalSnippets>
<code language="python"><![CDATA[
# Coqui call
from TTS.api import TTS
TTS(model_name="tts_models/multilingual/multi-dataset/your_tts").tts_to_file(
  text="Shields up.", speaker_wav="voices/samples/aria.wav",
  language="en", file_path="out.wav")
]]></code>
<code language="python"><![CDATA[
# ElevenLabs call
from elevenlabs import generate, save, set_api_key
set_api_key(os.getenv("ELEVENLABS_API_KEY"))
save(generate("Red Alert.", voice="HV5LQQys2FkXruuXDrZb"), "fallback.wav")
]]></code>
</externalSnippets>

<!-- 8 ◈ LOGGING -->
<loggingGuidelines>
  • logger names = module paths.  
  • INFO: engine loaded, line complete.  
  • WARNING: engine failed, trying next.  
  • ERROR: all engines failed, TODO.wav written.  
</loggingGuidelines>

<!-- 9 ◈ FINAL CHECKLIST -->
<checklist>
  1. Add dependencies to requirements.txt.  
  2. Implement tts_engine.py, generate_voices.py, validate_voices.py.  
  3. Create tools/migrate_registry.py and run once.  
  4. Patch audio_pipeline.py.  
  5. Update docs (HOWTORUN, Super Simple Guide) with Coqui + offline note.  
  6. Add unit + integration tests; ensure pytest passes offline.  
  7. Smoke: ingest stub book ➜ outline ➜ script ➜ generate voices (Coqui) ➜ mix ➜ play.  
  8. Fallback test: temporarily move speaker_wav; expect ElevenLabs synthesis.  
</checklist>
</prompt>
