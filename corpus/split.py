#!/usr/bin/env python3
"""Split eligible states by program, so test programs are never seen in training.

    corpus/split.py data/states.jsonl --gold ../rippy/scripts/jev-eval/sample.toml --out data/split

Programs from the gold sample (rippy's scripts/jev-eval/sample.toml) are left
out of every split: that sample stays the untouched end-to-end check. Each
program lands in exactly one split by hash, and at most --per-program records
per program are kept so the labelling budget spreads across many tools.
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


def bucket(program):
    h = int(hashlib.sha256(program.encode()).hexdigest(), 16) % 10
    return "test" if h == 0 else "dev" if h == 1 else "train"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("states", type=Path)
    ap.add_argument("--gold", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-program", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    gold = {name for case in tomllib.loads(args.gold.read_text())["case"]
            for name in LEAF.findall(case["command"])}
    by_program = defaultdict(list)
    dropped = 0
    for line in args.states.open():
        r = json.loads(line)
        if r["program"] in gold or LEAF.findall(r["command"])[:1] and LEAF.findall(r["command"])[0] in gold:
            dropped += 1
            continue
        by_program[r["program"]].append(r)
    rng = random.Random(args.seed)
    splits = defaultdict(list)
    for program in sorted(by_program):
        records = by_program[program]
        rng.shuffle(records)
        splits[bucket(program)].extend(records[: args.per_program])
    args.out.mkdir(parents=True, exist_ok=True)
    for name, records in splits.items():
        rng.shuffle(records)
        with (args.out / f"{name}.jsonl").open("w") as out:
            out.writelines(json.dumps(r) + "\n" for r in records)
        programs = len({r["program"] for r in records})
        print(f"{name}: {len(records)} records, {programs} programs")
    print(f"dropped {dropped} records of gold-sample programs")


if __name__ == "__main__":
    main()
