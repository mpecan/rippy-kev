#!/usr/bin/env python3
"""Split v2 states into train and four evaluation sets.

    corpus/split_v2.py data/v2/states.jsonl --gold ../rippy/scripts/jev-eval/sample.toml --out data/v2/split

- `test_unseen` / `dev_unseen`: whole programs never seen in training, the same
  hash buckets as v1 (corpus/split.py), so v1 and v2 compare on equal terms.
- `test_seen` / `dev_seen`: held-out *examples* of training programs. In real
  use most unknown commands are common tools, which this measures. All fill
  variants of an example (same program and description) stay on one side, so
  no near-duplicate leaks from train into evaluation.
- `train`: everything else.

Gold-sample programs are excluded everywhere, as in v1.
"""

import argparse
import hashlib
import json
import random
import re
import tomllib
from collections import defaultdict
from pathlib import Path

LEAF = re.compile(r"(?:^|[|;&]\s*)([A-Za-z0-9][\w.+-]*)")


def program_bucket(program):
    h = int(hashlib.sha256(program.encode()).hexdigest(), 16) % 10
    return "test_unseen" if h == 0 else "dev_unseen" if h == 1 else "train"


def example_bucket(program, description, rate):
    """Seen-program holdout by example; salted so it is independent of the program split."""
    h = int(hashlib.sha256(f"example:{program}:{description}".encode()).hexdigest(), 16) % 1000
    if h < rate * 1000:
        return "test_seen"
    if h < 2 * rate * 1000:
        return "dev_seen"
    return "train"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("states", type=Path)
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seen-rate", type=float, default=0.05,
                    help="share of training-program examples held out for each of test_seen and dev_seen")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    gold = {name for case in tomllib.loads(args.gold.read_text())["case"]
            for name in LEAF.findall(case["command"])}
    splits, dropped = defaultdict(list), 0
    for line in args.states.open():
        r = json.loads(line)
        leaves = LEAF.findall(r["command"])
        if r["program"] in gold or (leaves and leaves[0] in gold):
            dropped += 1
            continue
        bucket = program_bucket(r["program"])
        if bucket == "train":
            bucket = example_bucket(r["program"], r["description"], args.seen_rate)
        splits[bucket].append(r)
    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for name in sorted(splits):
        records = splits[name]
        rng.shuffle(records)
        with (args.out / f"{name}.jsonl").open("w") as out:
            out.writelines(json.dumps(r) + "\n" for r in records)
        print(f"{name:<12} {len(records):6d} records, {len({r['program'] for r in records}):5d} programs")
    print(f"dropped {dropped} records of gold-sample programs")


if __name__ == "__main__":
    main()
