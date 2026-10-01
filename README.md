# rippy-kev

A small decision model for [rippy](https://github.com/mpecan/rippy)'s uncertain
asks: a LoRA fine-tune of [Kev-4B](https://github.com/jaredpalmer/kev) on shell
commands, served locally as a System One (`/v1/systemone`) endpoint that rippy's
`[jev]` client talks to unchanged.

## Pipeline

| Step | Script | Output |
|---|---|---|
| Commands from tldr-pages examples | `corpus/tldr.py vendor/tldr --out data/commands.jsonl` | ~30k concrete commands |
| Keep what rippy would send, with the exact state | `corpus/states.py data/commands.jsonl --rippy <rippy>` | ~19k eligible states |
| Split by program (test programs unseen in training) | `corpus/split.py data/states.jsonl --gold <rippy>/scripts/jev-eval/sample.toml` | `data/split/{train,dev,test}.jsonl` |
| Capture rippy's exact question set | `teacher/capture_questions.py --rippy <rippy>` | `data/questions.json` |
| Label with OpenRouter teachers | `teacher/label.py` (`scripts/teachers.sh`) | `data/labels/<teacher>/<split>.jsonl` |
| Label with Claude agents | `data/agent/brief.md` + chunks, then `teacher/import_votes.py` | `data/labels/sonnet-5/<split>.jsonl` |
| Score teachers on rippy's gold set | `teacher/score.py data/labels/*/gold.jsonl --rippy <rippy>` | per-teacher false approvals |
| Merge votes into Kev records | `corpus/assemble.py <split> --teachers gemma-4-31b sonnet-5` | `data/kev/<split>.jsonl` |

`<rippy>` is a rippy checkout built with `cargo build --release --features jev`.

## Ground rules

- The student sees only what rippy sends (`state`); tldr descriptions are a
  teacher-only hint.
- The gold sample in rippy's `scripts/jev-eval/sample.toml` is never trained on:
  its programs are excluded from every split.
- A teacher qualifies only with zero false approvals on the gold set.
- Training records use the question set captured from rippy byte for byte; a
  `QUESTION_SET_VERSION` change in rippy means relabel and retrain.
