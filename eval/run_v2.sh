#!/usr/bin/env bash
# Run one backend over the v2 test sets and rippy's gold sample with the q3 rippy build.
#   eval/run_v2.sh <backend> [rippy-binary]
set -uo pipefail
B=$1
RIPPY=${2:-/Users/mdp/src/github.com/mpecan/rippy/.claude/worktrees/agent-ac4a86f32b28175e8/target/release/rippy}
E=/Users/mdp/src/github.com/mpecan/rippy/scripts/jev-eval
R=/Users/mdp/src/github.com/mpecan/rippy-kev/data/v2/eval
for s in test_unseen test_seen test_synth gold; do
  sample=$R/$s.toml; [ "$s" = gold ] && sample=$E/sample.toml
  python3 $E/eval.py --rippy "$RIPPY" --backends $E/backends.toml --only "$B" --sample "$sample" --out "$R/results-$s" 2>/dev/null \
    | sed -n "/^$B /p" | sed "s/^/$s  /"
done
