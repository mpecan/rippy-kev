#!/usr/bin/env bash
# Run one backend over the v2 dev sets (threshold fitting) with the q3 rippy build.
set -uo pipefail
B=$1
RIPPY=${2:-/Users/mdp/src/github.com/mpecan/rippy/.claude/worktrees/agent-ac4a86f32b28175e8/target/release/rippy}
E=/Users/mdp/src/github.com/mpecan/rippy/scripts/jev-eval
R=/Users/mdp/src/github.com/mpecan/rippy-kev/data/v2/eval
for s in dev_unseen dev_seen; do
  python3 $E/eval.py --rippy "$RIPPY" --backends $E/backends.toml --only "$B" --sample "$R/$s.toml" --out "$R/results-$s" 2>/dev/null \
    | sed -n "/^$B /p" | sed "s/^/$s  /"
done
