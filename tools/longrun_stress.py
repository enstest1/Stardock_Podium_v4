"""EXP-LONG (offline): does the canon ledger hold up over hundreds of episodes?

No LLM. A stub writer appends episode-sized batches of canon records, at the
volume measured on the real showcase episode (about 22 events, 74 beliefs,
11 promises and 4 state changes per episode), to a temporary ledger. At
checkpoints it measures size, the latency of every read the pipeline makes,
the size of the planning context, and recall of episode-1 facts.

Usage:  python tools/longrun_stress.py [--episodes 300] [--every 25]
Writes experiments/longrun/<date>/results.json and report.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from story_os.canon_store import CanonStore  # noqa: E402
from story_os.canon_extract import omniscience_check  # noqa: E402

CAST = ["Della", "Owen", "Margaret", "Felix", "June", "Abel", "Rosa", "Hank",
        "Ida", "Cyrus", "Mae", "Tobias"]
PLACES = ["the studio", "the tower", "the diner", "the highway", "the motel",
          "the wash", "the mine", "the chapel"]
VERBS = ["finds", "hides", "breaks", "repairs", "reads", "burns", "buries", "steals"]
THINGS = ["the reel", "the ledger", "a photograph", "the key", "the letter",
          "a cassette", "the map", "the badge", "a lighter", "the dial"]
ATTRS = ["location", "condition", "possession", "role"]
PER_EP = {"events": 22, "beliefs": 74, "promises": 11, "state_changes": 4, "relationships": 4}


_SYL = ["ka", "lo", "ver", "mi", "dan", "tro", "sel", "qua", "ben", "rix", "pol", "gar"]


def _word(rng):
    return "".join(rng.choice(_SYL) for _ in range(3))


def ev(ep, n, i, rng):
    a = rng.choice(CAST)
    w = rng.sample([c for c in CAST if c != a], 2)
    return {"event_id": f"EV-{n:04d}-{i:02d}", "episode_id": ep, "episode_number": n,
            "kind": rng.choice(["action", "reveal", "decision", "arrival"]),
            # three made-up proper nouns stand in for the specific details real
            # summaries carry ("the Calloway reel", "Route 9 motel")
            "summary": f"{a} {rng.choice(VERBS)} {rng.choice(THINGS)} at {rng.choice(PLACES)} "
                       f"near {_word(rng)} with {_word(rng)} and {_word(rng)}",
            "actors": [a], "witnesses": w, "status": "draft",
            "evidence": {"episode_id": ep, "line_ids": [f"{ep}-L{i}"], "quote": "..."},
            "verification": {"quote_ok": True}}


def batch(n, rng, events_so_far):
    ep = f"ep{n:04d}"
    out = {k: [] for k in PER_EP}
    out["events"] = [ev(ep, n, i, rng) for i in range(PER_EP["events"])]
    base = {"episode_id": ep, "episode_number": n, "status": "draft",
            "evidence": {"episode_id": ep, "line_ids": [f"{ep}-L1"], "quote": "..."},
            "verification": {"quote_ok": True}}
    pool = events_so_far[-400:] + out["events"]
    for i in range(PER_EP["beliefs"]):
        e = rng.choice(pool)
        out["beliefs"].append({**base, "belief_id": f"BE-{n:04d}-{i:02d}",
                               "holder": rng.choice(CAST), "proposition": e["summary"],
                               "stance": rng.choice(["knows", "believes", "suspects"]),
                               "truth": rng.choice(["true", "true", "false", "unknown"]),
                               "about_event_id": e["event_id"]})
    for i in range(PER_EP["promises"]):
        out["promises"].append({**base, "promise_id": f"PR-{n:04d}-{i:02d}",
                                "kind": rng.choice(["question", "mystery", "setup", "threat"]),
                                "statement": f"What happens to {rng.choice(THINGS)}? ({n}.{i})",
                                "horizon": rng.choice(["episode", "episode", "season", "series"]),
                                "planted_in": ep})
    for i in range(PER_EP["state_changes"]):
        out["state_changes"].append({**base, "change_id": f"SC-{n:04d}-{i:02d}",
                                     "entity": rng.choice(CAST), "attribute": rng.choice(ATTRS),
                                     "after": f"{rng.choice(PLACES)} / ep {n}"})
    for i in range(PER_EP["relationships"]):
        a, b = rng.sample(CAST, 2)
        out["relationships"].append({**base, "delta_id": f"RD-{n:04d}-{i:02d}", "a": a, "b": b,
                                     "dimension": rng.choice(["trust", "fear", "respect"]),
                                     "direction": rng.choice(["up", "down"])})
    return ep, out


def timed(fn, *a, **kw):
    t = time.perf_counter()
    r = fn(*a, **kw)
    return r, round((time.perf_counter() - t) * 1000, 1)


def fake_script(rng, events):
    lines = []
    for i in range(60):
        who = rng.choice(CAST)
        if i % 15 == 0 and events:          # 4 lines that leak a fact to an outsider
            e = rng.choice(events)
            who = next(c for c in CAST if c not in e["actors"] + e["witnesses"])
            content = e["summary"]
        else:
            content = "I don't know what you heard, but it wasn't me on that line."
        lines.append({"type": "dialogue", "character": who, "content": content,
                      "line_id": f"x{i}"})
    return {"scenes": [{"scene_number": 1, "lines": lines}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=300)
    ap.add_argument("--every", type=int, default=25)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    tmp = Path(tempfile.mkdtemp(prefix="longrun_"))
    store = CanonStore(tmp)
    all_events = []
    checkpoints = []
    ep1_state = {}
    paid_target = None
    started = time.time()
    try:
        for n in range(1, args.episodes + 1):
            ep, recs = batch(n, rng, all_events)
            if n == 1:
                # an ep-1 fact nobody ever overwrites, and a series promise to pay later
                recs["state_changes"].append({**recs["state_changes"][0], "change_id": "SC-ANCHOR",
                                              "entity": "KMFL", "attribute": "frequency",
                                              "after": "1340 AM"})
                paid_target = recs["promises"][0]["promise_id"]
                recs["promises"][0]["horizon"] = "series"
            for kind, rows in recs.items():
                store.append(kind, rows)
            all_events += recs["events"]
            store.set_status(ep, "canon")
            # pay off ~70 % of earlier episode-horizon promises (writer behaviour)
            if n > 1:
                prev = [p for p in store.open_promises(horizons=("episode",))
                        if p["episode_id"] == f"ep{n - 1:04d}"]
                for p in prev:
                    if rng.random() < 0.7:
                        store.append("promises", [{**p, "state": "paid", "paid_by": ep}])
            if n == 150 and paid_target:
                p = next(p for p in store.records("promises") if p["promise_id"] == paid_target)
                store.append("promises", [{**p, "state": "paid", "paid_by": ep}])
            if n == 1:
                ep1_state = store.character_state("KMFL")
            if n % args.every == 0 or n == 1:
                cp = {"episode": n}
                cp["ledger_kb"] = round(sum(f.stat().st_size for f in store.dir.glob("*.jsonl")) / 1024)
                cp["records"] = {k: len(store._read(store._file(k))) for k in PER_EP}
                brief, cp["brief_ms"] = timed(store.continuity_brief)
                cp["brief_chars"] = len(brief)
                cp["brief_tokens_est"] = len(brief) // 4
                _, cp["open_promises_ms"] = timed(store.open_promises)
                cp["unpaid_season_series"] = len(store.open_promises())
                _, cp["character_state_ms"] = timed(store.character_state, "Della")
                issues, cp["omniscience_ms"] = timed(omniscience_check,
                                                     fake_script(rng, all_events[-200:]), store, "x")
                cp["omniscience_flags"] = len(issues)
                _, cp["rebuild_index_ms"] = timed(store.rebuild_index)
                # recall of episode-1 facts
                ep1 = [e for e in store.query("events") if e["episode_id"] == "ep0001"]
                cp["recall_ep1_events"] = f"{len(ep1)}/{PER_EP['events']}"
                cp["recall_ep1_anchor"] = store.character_state("KMFL") == ep1_state
                pr = next(p for p in store.records("promises") if p["promise_id"] == paid_target)
                cp["ep1_series_promise_state"] = pr["state"]
                cp["elapsed_s"] = round(time.time() - started, 1)
                checkpoints.append(cp)
                print(json.dumps(cp), flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    date = dt.date.today().isoformat()
    out = ROOT / "experiments" / "longrun" / date
    out.mkdir(parents=True, exist_ok=True)
    res = {"date": date, "episodes": args.episodes, "per_episode": PER_EP, "seed": args.seed,
           "checkpoints": checkpoints}
    (out / "results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    L = [f"# Long-run canon stress test ({date})", "",
         f"Stub writer, {args.episodes} episodes, per-episode volume {PER_EP} (matches the showcase). "
         "Latency is measured on this laptop's CPU.", "",
         "| Ep | Ledger KB | Brief ms | Brief tokens | Omniscience ms | Char state ms | Index ms | Unpaid season/series | Ep-1 recall | Anchor | Ep-1 promise |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in checkpoints:
        L.append(f"| {c['episode']} | {c['ledger_kb']} | {c['brief_ms']} | {c['brief_tokens_est']} | "
                 f"{c['omniscience_ms']} | {c['character_state_ms']} | {c['rebuild_index_ms']} | "
                 f"{c['unpaid_season_series']} | {c['recall_ep1_events']} | {c['recall_ep1_anchor']} | "
                 f"{c['ep1_series_promise_state']} |")
    (out / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
