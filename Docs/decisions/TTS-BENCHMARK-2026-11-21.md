# TTS benchmark (2026-11-21)

EXP-TTS. Project `static_at_mesquite_flats`, characters della_reyes, owen_pike, margaret_hale, 8 identical lines per character and engine, device **cuda**. Audio: `experiments/tts/2026-11-21/`.

XTTS clones each character from a 12 s Kokoro reference, so both engines target the same voice.
Speaker scores use WavLM-base-plus-sv, and accuracy uses Whisper-base WER. Numbers read as words count as errors for both engines alike.

| Metric | kokoro | xtts |
|---|---|---|
| Real-time factor (lower = faster) | 0.051 | 0.49 |
| Word error rate | 0.0 | 0.01 |
| Clips with WER > 0.2 | 0 | 0 |
| Voice consistency (mean cos to own centroid) | 0.9896 | 0.9832 |
| Voice consistency (worst clip) | 0.9776 | 0.9363 |
| Max similarity between different characters | 0.9027 | 0.9397 |
| Similarity to the Kokoro reference voice | 0.9822 | 0.9357 |
| Passes Kokoro-derived thresholds | True | False |

Thresholds from Kokoro's distribution: tau_same=0.9802, tau_min=0.9576, tau_diff=0.9227. These are now the T-voice regression thresholds.

## Worst transcripts

| Engine | Character | WER | Heard |
|---|---|---|---|
| xtts | della_reyes | 0.154 | 3 a.m. on the dial. 400 of you will wake out there tonight. |
| xtts | della_reyes | 0.083 | Owen, check the transmitter. The needle's climbing pass the red mark again. |
| kokoro | della_reyes | 0.0 | 3am on the dial. 400 of you awake out there tonight. |
| kokoro | della_reyes | 0.0 | That's the unlisted line. It has been dead for years. |
| kokoro | della_reyes | 0.0 | Keep your radios close and leave your porch lights on. |

## Licences

- Kokoro-82M: Apache-2.0, fine for commercial use.
- XTTS v2: Coqui Public Model License, **non-commercial only**. Cloning a real person also needs their consent.

## Decision

Provisional, pending the listening check: **Kokoro stays the default engine.**
- It is about 10x faster on the GPU (RTF 0.05 vs 0.49), and both engines are near-perfect on accuracy.
- It passes every voice-identity threshold. XTTS's worst clip drifts (0.936 against a minimum of 0.958), and its characters sound more alike to each other (0.94 vs 0.90).
- Caveat: XTTS here clones *Kokoro* references, so the test measures how well it copies a voice, not its own expressiveness. Its real strength is cloning real recordings with natural prosody, and these metrics don't score prosody.
- Use XTTS per character, opt-in, for voices cloned from real samples (personal use; CPML non-commercial).
