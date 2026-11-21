"""EXP-TTS: compare speech engines on the same lines and voices.

Engines: Kokoro (current default) and Coqui XTTS v2 (cloning each Kokoro
voice from a ~12 s Kokoro reference, so both engines aim at the same voice).

Per clip it measures:
  * speed    real-time factor (synth seconds / audio seconds)
  * accuracy word error rate of Whisper-base's transcript against the text
  * identity WavLM-base-plus-sv speaker embedding:
      - consistency: cosine of each clip to its character's centroid (same engine)
      - separation:  cosine between different characters' centroids
      - fidelity:    cosine of XTTS clips to the Kokoro voice they clone
Thresholds tau_same / tau_min / tau_diff are set from Kokoro's own
distribution (handoff doc 12, T-voice).

Usage:  python tools/tts_benchmark.py [--project static_at_mesquite_flats] [--engines kokoro,xtts]
Writes experiments/tts/<date>/ (audio + results.json) and
Docs/decisions/TTS-BENCHMARK-<date>.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics as st
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LINES = [
    "Three a.m. on the dial. Four hundred of you awake out there tonight.",
    "That's the unlisted line. It has been dead for years.",
    "Keep your radios close, and leave your porch lights on.",
    "I counted the cars on the highway, and none of them had headlights.",
    "Tell me the year where you are, slowly, so I can write it down.",
    "Owen, check the transmitter. The needle's climbing past the red mark again.",
    "I remember the flood. The whole valley turned to glass and nobody came.",
    "If you can hear me, don't hang up. Whatever happens next, stay on the line.",
]
REF_TEXT = ("Good evening. The wind has been blowing since sundown, and the coffee is "
            "terrible, but the lights are on and the phones are working. Let's begin.")


def load16(path: str) -> np.ndarray:
    import librosa
    y, _ = librosa.load(path, sr=16000, mono=True)
    return y


def norm_words(text: str):
    """Lower-case words with digits spelled out ("3am" == "three a.m.")."""
    from num2words import num2words
    t = text.lower().replace("a.m.", " am").replace("p.m.", " pm").replace("'", "")
    t = re.sub(r"\d+", lambda m: " " + num2words(int(m.group())) + " ", t)
    return re.findall(r"[a-z]+", t.replace("-", " "))


def wer(ref: str, hyp: str) -> float:
    r, h = norm_words(ref), norm_words(hyp)
    d = np.zeros((len(r) + 1, len(h) + 1), dtype=int)
    d[:, 0] = range(len(r) + 1)
    d[0, :] = range(len(h) + 1)
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i, j] = min(d[i - 1, j] + 1, d[i, j - 1] + 1,
                          d[i - 1, j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r), len(h)] / max(1, len(r))


class Scorer:
    def __init__(self):
        from transformers import (AutoFeatureExtractor, WavLMForXVector, pipeline)
        self.fe = AutoFeatureExtractor.from_pretrained("microsoft/wavlm-base-plus-sv")
        self.sv = WavLMForXVector.from_pretrained("microsoft/wavlm-base-plus-sv").eval()
        self.asr = pipeline("automatic-speech-recognition", model="openai/whisper-base",
                            device=-1)

    def embed(self, path: str) -> np.ndarray:
        import torch
        y = load16(path)
        inp = self.fe(y, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            e = self.sv(**inp).embeddings[0].numpy()
        return e / np.linalg.norm(e)

    def transcribe(self, path: str) -> str:
        return self.asr(load16(path), generate_kwargs={"language": "en"})["text"]


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="static_at_mesquite_flats")
    ap.add_argument("--engines", default="kokoro,xtts")
    ap.add_argument("--characters", default="della_reyes,owen_pike,margaret_hale")
    args = ap.parse_args()
    import soundfile as sf
    from tts_engine import get_kokoro_engine

    date = dt.date.today().isoformat()
    out = ROOT / "experiments" / "tts" / date
    out.mkdir(parents=True, exist_ok=True)
    voices = json.loads((ROOT / "data" / "projects" / args.project / "voices.json")
                        .read_text(encoding="utf-8"))["characters"]
    chars = [c for c in args.characters.split(",") if c in voices]
    engines = args.engines.split(",")

    kok = get_kokoro_engine()
    xtts = None
    if "xtts" in engines:
        from tts_engine import get_xtts_engine
        t = time.time()
        xtts = get_xtts_engine()
        print(f"XTTS loaded in {time.time() - t:.0f}s", flush=True)

    rows = []
    refs = {}
    for ch in chars:
        ref = out / f"ref_{ch}.wav"
        kok.synth(text=REF_TEXT, speaker_wav=voices[ch]["kokoro_voice"], language="en",
                  output_path=str(ref))
        refs[ch] = str(ref)
        for eng in engines:
            for i, text in enumerate(LINES, 1):
                p = out / f"{eng}_{ch}_{i:02d}.wav"
                t = time.time()
                if eng == "kokoro":
                    kok.synth(text=text, speaker_wav=voices[ch]["kokoro_voice"],
                              language="en", output_path=str(p))
                else:
                    xtts.synth(text=text, speaker_wav=refs[ch], language="en",
                               output_path=str(p))
                took = time.time() - t
                dur = sf.info(str(p)).duration
                rows.append({"engine": eng, "character": ch, "line": i, "text": text,
                             "file": p.name, "synth_s": round(took, 2),
                             "audio_s": round(dur, 2), "rtf": round(took / dur, 3)})
                print(f"{eng:6} {ch:14} {i:02d}  rtf={took / dur:.2f}", flush=True)

    print("scoring...", flush=True)
    sc = Scorer()
    emb = {}
    for r in rows:
        f = str(out / r["file"])
        r["transcript"] = sc.transcribe(f).strip()
        r["wer"] = round(wer(r["text"], r["transcript"]), 3)
        emb[r["file"]] = sc.embed(f)
    ref_emb = {ch: sc.embed(p) for ch, p in refs.items()}

    summary = {}
    for eng in engines:
        cents = {}
        within = []
        for ch in chars:
            es = [emb[r["file"]] for r in rows if r["engine"] == eng and r["character"] == ch]
            c = np.mean(es, axis=0)
            cents[ch] = c
            sims = [cos(e, c) for e in es]
            within += sims
            for r in rows:
                if r["engine"] == eng and r["character"] == ch:
                    r["consistency"] = round(cos(emb[r["file"]], c), 4)
                    r["fidelity_to_ref"] = round(cos(emb[r["file"]], ref_emb[ch]), 4)
        cross = [cos(cents[a], cents[b]) for i, a in enumerate(chars) for b in chars[i + 1:]]
        er = [r for r in rows if r["engine"] == eng]
        summary[eng] = {
            "clips": len(er),
            "rtf_mean": round(st.mean(r["rtf"] for r in er), 3),
            "wer_mean": round(st.mean(r["wer"] for r in er), 3),
            "wer_clips_over_0_2": sum(r["wer"] > 0.2 for r in er),
            "consistency_mean": round(st.mean(within), 4),
            "consistency_min": round(min(within), 4),
            "consistency_sd": round(st.pstdev(within), 4),
            "cross_character_max": round(max(cross), 4) if cross else None,
            "cross_character_mean": round(st.mean(cross), 4) if cross else None,
            "fidelity_to_kokoro_ref_mean": round(st.mean(r["fidelity_to_ref"] for r in er), 4),
        }
    k = summary.get("kokoro")
    thresholds = None
    if k:
        thresholds = {"tau_same": round(k["consistency_mean"] - 2 * k["consistency_sd"], 4),
                      "tau_min": round(k["consistency_min"] - 0.02, 4),
                      "tau_diff": round(k["cross_character_max"] + 0.02, 4)}
        for eng, s in summary.items():
            s["passes_kokoro_thresholds"] = (
                s["consistency_mean"] >= thresholds["tau_same"]
                and s["consistency_min"] >= thresholds["tau_min"]
                and s["cross_character_max"] <= thresholds["tau_diff"])
    res = {"date": date, "project": args.project, "characters": chars, "lines": LINES,
           "device": "cuda" if __import__("torch").cuda.is_available() else "cpu",
           "summary": summary, "thresholds": thresholds, "rows": rows}
    (out / "results.json").write_text(json.dumps(res, indent=2, default=lambda o: o.item()), encoding="utf-8")
    write_report(res, out)
    print(json.dumps(summary, indent=2, default=lambda o: o.item()))


def write_report(res, out):
    s = res["summary"]
    engines = list(s)
    L = [f"# TTS benchmark ({res['date']})", "",
         f"EXP-TTS. Project `{res['project']}`, characters {', '.join(res['characters'])}, "
         f"{len(res['lines'])} identical lines per character and engine, device **{res['device']}**. "
         f"Audio: `{out.relative_to(ROOT).as_posix()}/`.", "",
         "XTTS clones each character from a 12 s Kokoro reference, so both engines target the same voice.",
         "Speaker scores use WavLM-base-plus-sv, and accuracy uses Whisper-base WER. Numbers read as words count as errors for both engines alike.", "",
         "| Metric | " + " | ".join(engines) + " |", "|---|" + "---|" * len(engines)]
    labels = [("rtf_mean", "Real-time factor (lower = faster)"),
              ("wer_mean", "Word error rate"),
              ("wer_clips_over_0_2", "Clips with WER > 0.2"),
              ("consistency_mean", "Voice consistency (mean cos to own centroid)"),
              ("consistency_min", "Voice consistency (worst clip)"),
              ("cross_character_max", "Max similarity between different characters"),
              ("fidelity_to_kokoro_ref_mean", "Similarity to the Kokoro reference voice"),
              ("passes_kokoro_thresholds", "Passes Kokoro-derived thresholds")]
    for key, lab in labels:
        L.append(f"| {lab} | " + " | ".join(str(s[e].get(key)) for e in engines) + " |")
    if res["thresholds"]:
        t = res["thresholds"]
        L += ["", f"Thresholds from Kokoro's distribution: tau_same={t['tau_same']}, "
                  f"tau_min={t['tau_min']}, tau_diff={t['tau_diff']}. "
                  "These are now the T-voice regression thresholds."]
    worst = sorted(res["rows"], key=lambda r: -r["wer"])[:5]
    L += ["", "## Worst transcripts", "", "| Engine | Character | WER | Heard |", "|---|---|---|---|"]
    for r in worst:
        L.append(f"| {r['engine']} | {r['character']} | {r['wer']} | {r['transcript'][:90]} |")
    L += ["", "## Licences", "",
          "- Kokoro-82M: Apache-2.0, fine for commercial use.",
          "- XTTS v2: Coqui Public Model License, **non-commercial only**. Cloning a real person also needs their consent.", "",
          "## Decision", "", "_Filled in after the listening check._", ""]
    p = ROOT / "Docs" / "decisions" / f"TTS-BENCHMARK-{res['date']}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(L), encoding="utf-8")
    print(f"report: {p}")


if __name__ == "__main__":
    main()
