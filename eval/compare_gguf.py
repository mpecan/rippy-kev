#!/usr/bin/env python3
"""Compare llama.cpp GGUF backends with the original (MLX) Kev backend.

    eval/compare_gguf.py --rippy ../rippy

For each GGUF result file in data/v2/eval/results-{test_unseen,gold}/gguf-*.jsonl:
the mean and max absolute change of every answer probability against the
same model served by kev.serve, how many rippy outcomes flip, and the
safe/severe approvals at the thresholds fitted for the original
(data/v2/eval/fit-<backend>.json), so a quantised file is judged at the
setting it would ship with.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fit_thresholds import load, score, severity  # noqa: E402

ORIGINAL = {"rippy-kev-4b-v2": "kev-4b-v2", "rippy-kev-0-8b-v2": "kev-0.8b-v2"}


def probs(a):
    out = {f"effect.{k}": v for k, v in a["effect"]["probabilities"].items()}
    out.update({q: v["noul"] for q, v in a.items() if q != "effect"})
    return out


def rows(path):
    return {r["command"]: r for r in map(json.loads, path.open())}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rippy", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=Path("data/v2/eval"))
    args = ap.parse_args()
    sys.path.insert(0, str(args.rippy / "scripts/jev-eval"))
    from sweep import approves

    severe = severity(args.root)
    print(f"{'gguf':<28}{'mean|dp|':>9}{'max|dp|':>8}{'flips':>7}{'unseen safe':>13}{'severe':>8}{'gold safe':>10}{'p50 ms':>8}")
    for path in sorted((args.root / "results-test_unseen").glob("gguf-*.jsonl")):
        name = path.stem[len("gguf-"):]
        base = next(b for prefix, b in ORIGINAL.items() if name.startswith(prefix))
        thresholds = tuple(json.load(open(args.root / f"fit-{base}.json"))["thresholds"])
        g, o = rows(path), rows(args.root / "results-test_unseen" / f"{base}.jsonl")
        diffs, flips, lat = [], 0, []
        for cmd, r in g.items():
            a = (r["report"].get("jev") or {}).get("answers")
            b = (o.get(cmd, {}).get("report", {}).get("jev") or {}).get("answers")
            if r.get("latency_ms"):
                lat.append(r["latency_ms"])
            if not a or not b:
                continue
            pa, pb = probs(a), probs(b)
            diffs += [abs(pa[k] - pb[k]) for k in pa]
            flips += approves(a, *thresholds) != approves(b, *thresholds)
        u = score(load(args.root, "test_unseen", f"gguf-{name}", severe), approves, thresholds)
        gd = score(load(args.root, "gold", f"gguf-{name}", severe), approves, thresholds)
        print(f"{name:<28}{statistics.mean(diffs):>9.3f}{max(diffs):>8.2f}{flips:>7}"
              f"{u['safe_ok']:>8}/{u['safe']:<4}{u['severe_ok']:>8}{gd['safe_ok']:>6}/{gd['safe']:<3}"
              f"{statistics.median(lat):>8.0f}")


if __name__ == "__main__":
    main()
