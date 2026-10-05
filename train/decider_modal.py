"""Train and calibrate a Strands Decider on rippy-kev data on Modal.

    modal run train/decider_modal.py::main --name decider-v2-smoke --max-steps 10 --timeout 1200
    modal run train/decider_modal.py::main --name decider-v2 --timeout 5400
    modal run train/decider_modal.py::pull --name decider-v2

Data comes from data/v2/modal-decider (corpus/export_decider.py output, train
and teacher files concatenated with re-indexed teacher rows, plus a calib
file). The recipe is Strands Decider's reference Hobson recipe from
Qwen3.5-2B-Base with our soft targets as the teacher term. The timeout is the
cost cap: the H100 is billed only while the function runs.
"""

import os
import subprocess
from pathlib import Path

import modal

APP = "rippy-kev-decider"
GPU = os.environ.get("DECIDER_GPU", "H100")
VOL = modal.Volume.from_name("rippy-kev-decider", create_if_missing=True)
HF = modal.Volume.from_name("rippy-kev-hf-cache", create_if_missing=True)
DATA = Path(__file__).resolve().parent.parent / "data/v2/modal-decider"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("strands-decider==0.1.0", "flash-linear-attention", "pyyaml")
    .env({"HF_HOME": "/hf", "TOKENIZERS_PARALLELISM": "false"})
)
app = modal.App(APP, image=image)

CONFIG = """train_files: [/vol/data/train.jsonl]
teacher_file: /vol/data/train.teacher.jsonl
teacher_weight: 1.0
val_fraction: 0.01
base_model: Qwen/Qwen3.5-2B-Base
head_type: pointer
pointer_dim: 256
num_slots: 24
max_length: 1024
use_lora: true
lora_r: 16
lora_alpha: 32
lora_targets: [q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj, in_proj_qkv, in_proj_z, in_proj_a, in_proj_b, out_proj]
kl_frozen_weight: 0.3
epochs: 1
micro_batch_size: 16
grad_accum: 2
lr: 1.0e-4
head_lr: 1.0e-3
gradient_checkpointing: false
group_by_length: true
log_every: 10
eval_every: 1000
max_steps: {max_steps}
save_every: 1000
output_dir: /vol/runs/{name}
"""


@app.function(gpu=GPU, volumes={"/vol": VOL, "/hf": HF}, timeout=86400, cpu=8, memory=65536)
def train(name: str, max_steps: int) -> dict:
    os.makedirs("/vol/configs", exist_ok=True)
    cfg = f"/vol/configs/{name}.yaml"
    Path(cfg).write_text(CONFIG.format(name=name, max_steps=max_steps))
    run = f"/vol/runs/{name}"
    subprocess.run(["strands-decider", "train", "--config", cfg], check=True)
    subprocess.run(["strands-decider", "calibrate", run, "--data", "/vol/data/calib.jsonl",
                    "--limit", "4000"], check=True)
    VOL.commit()
    HF.commit()
    return {"run": run, "files": sorted(os.listdir(run))}


@app.local_entrypoint()
def main(name: str, max_steps: int = 0, timeout: int = 5400):
    with VOL.batch_upload(force=True) as batch:
        for f in ("train.jsonl", "train.teacher.jsonl", "calib.jsonl"):
            batch.put_file(str(DATA / f), f"/data/{f}")
    print(f"uploaded {DATA}; training {name} on {GPU}, timeout {timeout}s (cost cap)", flush=True)
    print(train.with_options(timeout=timeout).remote(name, max_steps))


@app.local_entrypoint()
def pull(name: str, out: str = "runs"):
    target = Path(out) / name
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["modal", "volume", "get", "--force", "rippy-kev-decider",
                    f"/runs/{name}", str(target.parent)], check=True)
    print(f"pulled to {target}")
