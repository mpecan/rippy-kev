#!/usr/bin/env python3
"""Export assembled Kev records to Strands Decider's training format.

    corpus/export_decider.py data/v2/kev/train.jsonl --out data/v2/decider/train

Writes two files that `strands_decider.train` reads as `train_files` and
`teacher_file`:

- `<out>.jsonl`: one Example per (state, question). `options` are
  `[name, description]` in rippy's canonical order (noul: false, true), and
  `label` indexes the hard label.
- `<out>.teacher.jsonl`: `{"i": row, "probs": [...]}` in the same option
  order, carrying the merged teacher fractions as soft targets.

The question wording is copied verbatim, so the Decider is trained on exactly
what rippy sends.
"""

import argparse
import json
from pathlib import Path


def rows(record):
    for qid, q in record["questions"].items():
        if q["type"] == "noul":
            crit = q.get("criteria") or {}
            options = [["false", crit.get("false", "")], ["true", crit.get("true", "")]]
            label = int(bool(q["label"]))
            target = q.get("target") or {}
            probs = [float(target.get("false", 1 - label)), float(target.get("true", label))]
        else:
            options = [[name, desc or ""] for name, desc in q["criteria"].items()]
            names = [o[0] for o in options]
            label = names.index(q["label"])
            target = q.get("target") or {q["label"]: 1.0}
            probs = [float(target.get(n, 0.0)) for n in names]
        s = sum(probs)
        yield {
            "kind": q["type"], "state": record["state"], "instructions": q["instructions"],
            "options": options, "label": label, "task": f"rippy/{qid}",
        }, [p / s for p in probs]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("records", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="path prefix, without .jsonl")
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(f"{args.out}.jsonl", "w") as ex, open(f"{args.out}.teacher.jsonl", "w") as te:
        for line in args.records.open():
            for example, probs in rows(json.loads(line)):
                ex.write(json.dumps(example, ensure_ascii=False) + "\n")
                te.write(json.dumps({"i": n, "probs": probs}) + "\n")
                n += 1
    print(f"{n} examples -> {args.out}.jsonl (+ .teacher.jsonl)")


if __name__ == "__main__":
    main()
