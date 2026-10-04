#!/usr/bin/env python3
"""Turn votes written by agent labellers into label.py's record format.

    teacher/import_votes.py data/gold/gold.jsonl data/agent/votes-gold-*.jsonl \
        --questions data/questions.json --model claude-sonnet-5 --out data/labels/sonnet-5/gold.jsonl

Agents (see data/agent/brief.md) write one vote per command. Votes are joined
back onto the source records by command; a malformed vote or a command the
source does not know is reported and dropped, never guessed. A vote file's
directory names its labelling pass: one vote per command per pass is kept, so
partial files left by a failed agent and its rerun never count twice.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from label import answers, valid  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source", type=Path)
    ap.add_argument("votes", nargs="+", type=Path)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    effects = list(json.loads(args.questions.read_text())["questions"]["effect"]["criteria"])
    source = {r["command"]: r for r in map(json.loads, args.source.open())}
    votes, problems, seen = {}, 0, set()
    for path in args.votes:
        for n, line in enumerate(path.open(), 1):
            try:
                vote = json.loads(line)
            except json.JSONDecodeError:
                vote = {}
            command = vote.pop("command", None)
            if command not in source:
                continue  # another split's record: vote files may span splits
            if not valid(vote, effects):
                print(f"{path}:{n}: dropped (invalid vote)")
                problems += 1
                continue
            if (path.parent.name, command) in seen:
                continue
            seen.add((path.parent.name, command))
            votes.setdefault(command, []).append(vote)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as out:
        for command, vs in votes.items():
            out.write(json.dumps({**source[command], "teacher": {"model": args.model, "votes": vs},
                                  "report": {"jev": {"answers": answers(vs, effects)}}}) + "\n")
    missing = len(source) - len(votes)
    print(f"{len(votes)} records -> {args.out}  ({missing} without a vote, {problems} dropped)")


if __name__ == "__main__":
    main()
