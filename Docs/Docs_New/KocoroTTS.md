<prompt>
<!-- ============================================================= -->
<!--  STARDOCK PODIUM – KOKORO-TTS OFFLINE + ELEVENLABS FALLBACK  -->
<!--  One-page copy-and-paste coder-agent brief                   -->
<!-- ============================================================= -->

<!-- 1 ◈ CONTEXT & OBJECTIVE -->
<overview>
  Stardock Podium currently relies on ElevenLabs if no local engine is
  available.  We now switch to **Kokoro-TTS** (hexgrad, 82 M params)
  as the primary, fully offline synthesiser while **retaining
  ElevenLabs as a secondary fallback**.  
  **Result:** synthesis order = **Kokoro ➜ ElevenLabs ➜ TODO**, no CLI
  changes for end-users.
</overview>

<!-- 2 ◈ DEPENDENCIES -->
<dependencies>
  <pip>
    pip install torch==2.2.0+cpu -f https://download.pytorch.org/whl/torch_stable.html
    pip install git+https://github.com/hexgrad/Kokoro-TTS.git@main
    pip install soundfile==0.12.1 librosa==0.10.2
    pip install elevenlabs==1.1.0
  </pip>
  Append these to <code>requirements.txt</code>.
</dependencies>

<!-- 3 ◈ FILE MAP -->
<interfaceDefinitions>
  <file path="tts_engine.py"          purpose="Facade exposing KokoroEngine & ElevenLabsEngine" />
  <file path="cli/generate_voices.py" purpose="Batch per-line synthesis via façade" />
  <file path="cli/validate_voices.py" purpose="Checks script ↔ voice_config ↔ WAVs" />
  <file path="voices/voice_config.json" purpose="Unified mapping (new, migrated from registry)" />
  <file path="tools/migrate_registry.py" purpose="Convert registry.json ➜ voice_config skeleton" />
  <!-- modify -->
  <file path="audio_pipeline.py"      purpose="Call generate_voices.py instead of direct ElevenLabs loop" />
  <file path="Docs/HOWTORUN.md"       purpose="Add Kokoro install + offline-first notes" />
</interfaceDefinitions>

<!-- 4 ◈ INPUT / OUTPUT CONTRACTS -->
<contracts>
  <contract id="voiceConfig">
    <schema><![CDATA[
{
  "engine_order": ["kokoro", "eleven"],
  "characters": {
    "Naren":      { "speaker_wav": "voices/samples/naren.wav",  "language": "en", "eleven_id": "hmHVDDDgElcw05Hab5Aq" },
    "Aria T'Vel": { "speaker_wav": "voices/samples/aria.wav",  "language": "en", "eleven_id": "HV5LQQys2FkXruuXDrZb" }
  }
}
]]></schema>
    Migration tool copies <code>voice_id</code> ➜ <code>eleven_id</code>;
    dev fills <code>speaker_wav</code> paths (fail if blank).
  </contract>

  <contract id="generateCLI">
    <input>--script episodes/&lt;ep&gt;/script.json --config voices/voice_config.json --outdir audio/raw/&lt;ep&gt; [--dry-run]</input>
    <output>Per-line WAV <code>&lt;scene&gt;_&lt;idx&gt;.wav</code>; exit-0 if all created.</output>
  </contract>
</contracts>

<!-- 5 ◈ FLOW -->
<mermaid>
flowchart TD
  V[validate_voices.py] --> L[Loop dialogue lines]
  L --> C{WAV exists?}
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
    • Define <code>SynthError</code>; abstract <code>TTSEngine.synth()</code>.  
    • <b>KokoroEngine</b>:  
      ```python
      from kokoro.inference import KokoroSynth
      import soundfile as sf
      class KokoroEngine(TTSEngine):
          def __init__(self):
              self.kok = KokoroSynth("kokoro-tts-base-ft.pt", device="cpu")
          def synth(self, text, char_cfg, out_path):
              try:
                  wav = self.kok.tts(text,
                                     speaker_wav=char_cfg["speaker_wav"],
                                     language=char_cfg.get("language","en"))
                  sf.write(out_path, wav, 16000)
              except Exception as e:
                  raise SynthError(str(e))
      ```  
    • <b>ElevenLabsEngine</b>: unchanged (reads <code>ELEVENLABS_API_KEY</code>).
  </step>

  <step id="generate_cli">
    • Build <code>engine_map = {"kokoro": KokoroEngine(), "eleven": ElevenLabsEngine()}</code>.  
    • Iterate **only lines where <code>line["type"]=="dialogue"</code>**.  
    • Attempt engines per <code>config["engine_order"]</code>; break on first success.  
    • If none succeed, create `<name>.TODO.wav`, mark exit 1.
  </step>

  <step id="validate_cli">
    • Parse script JSON. For every `dialogue` line:  
      ```python
      if line["speaker"] not in cfg:
          error(f"Missing speaker {line['speaker']} in voice_config")
      ```  
    • Check `<speaker_wav>` exists, mono, 16 kHz, 5-10 s.  
    • If engine_order includes “eleven”, verify `eleven_id`.  
    • Exit 1 on any failure.
  </step>

  <step id="audio_pipeline_patch">
    Replace ElevenLabs loop with:  
    ```python
    subprocess.run([sys.executable,"cli/generate_voices.py",
                    "--script", script_path,
                    "--config","voices/voice_config.json",
                    "--outdir", raw_dir], check=True)
    ```
    Continue FFmpeg mix unchanged.
  </step>

  <step id="migration_tool">
    • Read <code>voices/registry.json</code>.  
    • Emit new JSON: `{ name, eleven_id, language:"en", speaker_wav:"" }`.  
    • Print TODO lines to prompt dev to drop WAVs.
  </step>

  <step id="tests">
    • Unit: mock engines; assert fallback path executed on SynthError.  
    • Integration: run without ELEVENLABS_API_KEY → Kokoro WAVs created.  
    • Regression: rename a speaker_wav then rerun → ElevenLabs WAV produced.
  </step>

</implementationSteps>

<!-- 7 ◈ MINIMUM API SNIPPETS -->
<externalSnippets>
<code language="python"><![CDATA[
# Kokoro usage
from kokoro.inference import KokoroSynth
kok = KokoroSynth("kokoro-tts-base-ft.pt", device="cpu")
wav = kok.tts("Report.", speaker_wav="voices/samples/aria.wav", language="en")
import soundfile as sf; sf.write("aria.wav", wav, 16000)
]]></code>
<code language="python"><![CDATA[
# ElevenLabs fallback
from elevenlabs import generate, save, set_api_key
set_api_key(os.getenv("ELEVENLABS_API_KEY"))
save(generate("Red Alert.", voice="hmHVDDDgElcw05Hab5Aq"), "alert.wav")
]]></code>
</externalSnippets>

<!-- 8 ◈ LOGGING -->
<loggingGuidelines>
  • Logger per module.  
  • <code>INFO</code>: engine loaded, line rendered.  
  • <code>WARNING</code>: engine failed, trying next.  
  • <code>ERROR</code>: all engines failed, TODO.wav touched.
</loggingGuidelines>

<!-- 9 ◈ FINAL CHECKLIST -->
<checklist>
  1. Add dependencies to requirements.txt.  
  2. Implement <code>tts_engine.py</code>, <code>generate_voices.py</code>, <code>validate_voices.py</code>.  
  3. Run <code>tools/migrate_registry.py</code> once.  
  4. Patch <code>audio_pipeline.py</code>.  
  5. Update all docs (HOWTORUN, Setup Guide) with Kokoro notes.  
  6. Add unit + integration tests; ensure <code>pytest</code> passes offline.  
  7. Smoke: ingest book → outline → script → generate voices (Kokoro) → mix → play.  
  8. Fallback test: rename a <code>speaker_wav</code>; expect ElevenLabs line.  
  9. Confirm validate_voices.py flags any dialogue speaker missing from config.
</checklist>
</prompt>
