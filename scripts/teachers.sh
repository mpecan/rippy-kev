#!/usr/bin/env bash
# Label one split with every teacher in parallel through OpenRouter.
#   scripts/teachers.sh <split-name> <input.jsonl> <max-cost-per-teacher>
# Needs OPENROUTER_API_KEY in the environment.
set -euo pipefail
split=$1 input=$2 cap=$3
TEACHERS=(
  "openai/gpt-oss-120b high gpt-oss-120b"
  "deepseek/deepseek-v4-pro medium deepseek-v4-pro"
  "google/gemma-4-31b-it medium gemma-4-31b"
)
for spec in "${TEACHERS[@]}"; do
  read -r model effort name <<<"$spec"
  mkdir -p "data/labels/$name"
  python3 teacher/label.py "$input" --questions data/questions.json \
    --base-url https://openrouter.ai/api/v1 --api-key-env OPENROUTER_API_KEY \
    --model "$model" --reasoning-effort "$effort" --samples 1 --jobs 8 \
    --max-cost "$cap" --timeout 180 --out "data/labels/$name/$split.jsonl" \
    2> "data/labels/$name/$split.log" &
done
wait
for spec in "${TEACHERS[@]}"; do
  read -r _ _ name <<<"$spec"
  printf '%-16s ' "$name"; tr '\r' '\n' < "data/labels/$name/$split.log" | grep -E "labelled" || tail -2 "data/labels/$name/$split.log"
done
