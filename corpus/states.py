#!/usr/bin/env python3
"""Keep the commands rippy would send for review, with the exact state it sends.

    corpus/states.py data/commands.jsonl --rippy ../rippy/target/release/rippy --out data/states.jsonl

Runs `rippy jev --json` against an endpoint nothing listens on: rippy builds
the production state, fails to send it, and prints it. Commands rippy decides
itself, or refuses to send, come back as "skipped" and are dropped. Nothing
is executed.
"""

import argparse
import json
import random
import re
import os
import subprocess
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CONFIG = """[jev]
enabled = true
endpoint = "http://127.0.0.1:9/v1/systemone"
model = "state-dump"
api-key-env = "RIPPY_KEV_DUMMY_KEY"
timeout-ms = 200
"""


LEAF = re.compile(r"(?:^|[|;&]\s*)([A-Za-z0-9][\w.+-]*)")


def leaves(command):
    """Command names at the start of each pipeline or list element."""
    return set(LEAF.findall(command))


def stub(dirs, names):
    """Empty files: rippy's PATH lookup only checks that a file exists."""
    for d in dirs:
        for name in names:
            (d / name).touch()


def probe(rippy, config, workdir, path_for, record):
    env = {**os.environ, "RIPPY_KEV_DUMMY_KEY": "x", "PATH": path_for(record)}
    try:
        proc = subprocess.run(
            [str(rippy), "jev", "--json", "--config", str(config), "--", record["command"]],
            cwd=workdir, env=env, capture_output=True, text=True, timeout=30,
        )
        report = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    state = (report.get("jev") or {}).get("state")
    if state is None:
        return None
    return {**record, "kind": state["uncertainty_kind"], "state": state}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("commands", type=Path)
    ap.add_argument("--rippy", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=16)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    args.rippy = args.rippy.resolve()
    records = [json.loads(line) for line in args.commands.open()]
    with tempfile.TemporaryDirectory() as tmp:
        # Same shape as scripts/jev-eval in rippy: a bare project, no .rippy.toml.
        workdir = Path(tmp) / "project"
        (workdir / ".git").mkdir(parents=True)
        config = Path(tmp) / "config.toml"
        config.write_text(CONFIG)
        # Production programs are usually installed; vary where they resolve
        # so the "programs" fact matches what rippy sends in real use.
        system_bin = Path(tmp) / "bin"
        user_bin = Path(tempfile.mkdtemp(dir=Path.home() / ".cache"))
        system_bin.mkdir()
        names = set().union(*(leaves(r["command"]) for r in records))
        stub([system_bin, user_bin], names)
        rng = random.Random(args.seed)
        choice = {id(r): rng.choices([str(system_bin), str(user_bin), ""], [60, 25, 15])[0]
                  for r in records}
        base = os.environ["PATH"]

        def path_for(record):
            extra = choice[id(record)]
            return f"{extra}:{base}" if extra else base

        try:
            with ThreadPoolExecutor(args.jobs) as pool:
                results = list(pool.map(
                    lambda r: probe(args.rippy, config, workdir, path_for, r), records))
        finally:
            shutil.rmtree(user_bin)
        kept = [r for r in results if r]
    with args.out.open("w") as out:
        for r in kept:
            out.write(json.dumps(r) + "\n")
    kinds = {}
    for r in kept:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"{len(kept)}/{len(records)} eligible -> {args.out}  {kinds}")


if __name__ == "__main__":
    main()
