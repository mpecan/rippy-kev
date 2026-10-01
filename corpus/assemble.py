#!/usr/bin/env python3
"""Merge teacher votes into Kev training records.

    corpus/assemble.py train --teachers gemma-4-31b sonnet-5 --questions data/questions.json \
        --out data/kev/train.jsonl

Each record is the System One request rippy sends (state + the exact question
set) plus, per question, a soft `target` (the teachers' vote fractions) and a
hard `label`. Ties break conservatively: a split yes/no is labelled true, a
split effect takes the more severe option. Only commands every teacher
labelled are kept, so each target is built from the same evidence.
"""

import argparse
import json
from pathlib import Path

NOUL_IDS = ["exfiltration", "writes_outside_project", "reads_secrets", "irreversible",
            "runs_project_code", "self_referential"]
# Most severe first: the tie-break for a split effect vote.
SEVERITY = ["destructive", "download_execute", "network_send", "local_change", "remote_read",
            "read_only"]


def merge(votes, questions):
    n = len(votes)
    out = {}
    effect = dict(questions["effect"])
    fractions = {e: sum(v["effect"] == e for v in votes) / n for e in effect["criteria"]}
    top = max(fractions.values())
    effect["label"] = next(e for e in SEVERITY if fractions[e] == top)
    effect["target"] = {e: f for e, f in fractions.items() if f > 0}
    out["effect"] = effect
    for qid in NOUL_IDS:
        q = dict(questions[qid])
        p = sum(v[qid] for v in votes) / n
        q["label"] = p >= 0.5
        q["target"] = {"true": p, "false": 1 - p}
        out[qid] = q
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("split")
    ap.add_argument("--teachers", nargs="+", required=True)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--labels", type=Path, default=Path("data/labels"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    questions = json.loads(args.questions.read_text())["questions"]
    by_teacher = []
    for t in args.teachers:
        path = args.labels / t / f"{args.split}.jsonl"
        by_teacher.append({r["command"]: r for r in map(json.loads, path.open())})
    common = set.intersection(*(set(t) for t in by_teacher))
    split_votes = 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as out:
        for command in sorted(common):
            votes = [v for t in by_teacher for v in t[command]["teacher"]["votes"]]
            qs = merge(votes, questions)
            split_votes += any(0 < q["target"].get("true", 1) < 1 for q in qs.values()) or len(
                qs["effect"]["target"]) > 1
            source = by_teacher[0][command]
            out.write(json.dumps({"state": source["state"], "questions": qs,
                                  "_meta": {"program": source.get("program", "")}}) + "\n")
    sizes = ", ".join(f"{t}={len(d)}" for t, d in zip(args.teachers, by_teacher))
    print(f"{len(common)} records ({sizes}); teachers split on some question in {split_votes}"
          f" -> {args.out}")


if __name__ == "__main__":
    main()
