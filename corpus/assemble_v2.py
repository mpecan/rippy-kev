#!/usr/bin/env python3
"""Merge weighted teacher votes into Kev training records (v2).

    corpus/assemble_v2.py train --teacher sonnet-5:1 --teacher gemma-4-31b:1 \
        --teacher opus-adjudicator:2 --questions data/v2/questions.json --out data/v2/kev/train.jsonl

Unlike corpus/assemble.py, teachers need not cover every record. A teacher
listed with weight w contributes each of its votes w times, wherever it has
labelled the command. The first teacher must cover the whole split, so every
record has evidence. Targets are weighted vote fractions; ties break
conservatively, as in v1. Every question is kept, including
`self_referential`: v2's synthetic cases give it positives.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from assemble import NOUL_IDS, SEVERITY  # noqa: E402


def merge(weighted, questions):
    total = sum(w for _, w in weighted)
    effect = dict(questions["effect"])
    fractions = {e: sum(w for v, w in weighted if v["effect"] == e) / total for e in effect["criteria"]}
    top = max(fractions.values())
    effect["label"] = next(e for e in SEVERITY if fractions[e] == top)
    effect["target"] = {e: f for e, f in fractions.items() if f > 0}
    out = {"effect": effect}
    for qid in NOUL_IDS:
        q = dict(questions[qid])
        p = sum(w for v, w in weighted if v[qid]) / total
        q["label"] = p >= 0.5
        q["target"] = {"true": p, "false": 1 - p}
        out[qid] = q
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("split")
    ap.add_argument("--teacher", action="append", required=True, help="name:weight (first covers all)")
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--labels", type=Path, default=Path("data/v2/labels"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    questions = json.loads(args.questions.read_text())["questions"]
    teachers = []
    for spec in args.teacher:
        name, weight = spec.rsplit(":", 1)
        path = args.labels / name / f"{args.split}.jsonl"
        rows = {r["command"]: r for r in map(json.loads, path.open())} if path.exists() else {}
        teachers.append((name, int(weight), rows))
    base_name, _, base = teachers[0]
    if not base:
        sys.exit(f"{base_name} has no labels for {args.split}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    split_votes, contributions = 0, {name: 0 for name, _, _ in teachers}
    with args.out.open("w") as out:
        for command in sorted(base):
            weighted = []
            for name, weight, rows in teachers:
                if command in rows:
                    contributions[name] += 1
                    weighted += [(v, weight) for v in rows[command]["teacher"]["votes"]]
            qs = merge(weighted, questions)
            split_votes += len(qs["effect"]["target"]) > 1 or any(
                0 < qs[q]["target"]["true"] < 1 for q in NOUL_IDS)
            src = base[command]
            out.write(json.dumps({"state": src["state"], "questions": qs,
                                  "_meta": {"program": src.get("program", ""), "category": src.get("category", "")}}) + "\n")
    print(f"{args.split}: {len(base)} records, soft target on {split_votes}; teacher coverage {contributions} -> {args.out}")


if __name__ == "__main__":
    main()
