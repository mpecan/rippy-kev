#!/usr/bin/env python3
"""Run `strands-decider train` with the MPS kernel for Qwen3.5's chunk rule installed.

    python train/decider_train.py --config configs/decider-timing.yaml

strands_decider installs its MPS gated-delta-rule kernel only on the inference
path (infer.py), so training on Apple silicon otherwise falls back to the slow
reference implementation. Its trainer also picks "cuda" or "cpu" only; the
local venv carries a one-line patch (train.py, device selection) to add "mps".
"""

import sys

from strands_decider.cli import app
from strands_decider.mps_kernels import install

if __name__ == "__main__":
    print(f"[rippy-kev] MPS chunk-rule kernel installed: {install()}", flush=True)
    sys.argv = ["strands-decider", "train", *sys.argv[1:]]
    app()
