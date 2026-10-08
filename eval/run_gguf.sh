#!/usr/bin/env bash
# Serve each GGUF with llama-server (one at a time, so latency is clean) and run
# rippy's jev-eval on gold and test_unseen.   eval/run_gguf.sh <name> ...
set -uo pipefail
K=/Users/mdp/src/github.com/mpecan/rippy-kev
RIPPY=/Users/mdp/src/github.com/mpecan/rippy/.claude/worktrees/agent-ac4a86f32b28175e8/target/release/rippy
E=/Users/mdp/src/github.com/mpecan/rippy/scripts/jev-eval
for name in "$@"; do
  llama-server -m "$K/runs/gguf/$name.gguf" --port 8020 -ngl 99 --parallel 1 -c 4096 --cache-ram 0 --ctx-checkpoints 0 > "$K/runs/gguf/$name.server.log" 2>&1 &
  pid=$!
  until curl -sf -o /dev/null -X POST http://127.0.0.1:8020/v1/systemone -H 'content-type: application/json' \
      -d '{"state":"x","questions":{"q":{"type":"noul","instructions":"Is it x?"}}}'; do sleep 2; done
  cat > "$K/runs/gguf/backends-$name.toml" <<EOT
[[backend]]
name = "gguf-$name"
endpoint = "http://127.0.0.1:8020/v1/systemone"
model = "$name"
api-key-env = "LOCAL_JEV_KEY"
dummy-key = true
timeout-ms = 10000
EOT
  for s in gold test_unseen; do
    sample=$K/data/v2/eval/$s.toml; [ "$s" = gold ] && sample=$E/sample.toml
    python3 $E/eval.py --rippy "$RIPPY" --backends "$K/runs/gguf/backends-$name.toml" --sample "$sample" \
      --out "$K/data/v2/eval/results-$s" 2>/dev/null | sed -n "/^gguf-$name /p" | sed "s/^/$s  /"
  done
  kill $pid; wait $pid 2>/dev/null
done
