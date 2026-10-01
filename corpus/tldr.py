#!/usr/bin/env python3
"""Turn tldr-pages examples into concrete shell commands.

    corpus/tldr.py vendor/tldr --out data/commands.jsonl

Each example becomes one record: the command with its {{placeholders}} filled
in, the page's program name, its platform and the example's description. The
description is for the teacher only; the model never sees it.

Placeholders are filled deterministically (seeded): `[-a|--all]` picks one
spelling, `path/to/...` becomes a project-relative, home or absolute path,
and some values become `$VARS` so dynamic-expansion asks are represented.
"""

import argparse
import json
import random
import re
from pathlib import Path

PLATFORMS = ("common", "osx", "linux")
EXAMPLE = re.compile(r"^- (?P<desc>.+?):?\n\n`(?P<cmd>.+)`$", re.M)
PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")

PROJECT_DIRS = ["src", "docs", "build", "tests", "assets", "."]
OUTSIDE_DIRS = ["~", "~/Documents", "~/Downloads", "/tmp", "/etc", "/var/log", "/usr/local"]
EXTENSIONS = {
    "image": "photo.jpg", "video": "clip.mp4", "audio": "song.mp3", "pdf": "report.pdf",
    "archive": "backup.tar.gz", "json": "data.json", "yaml": "config.yaml", "csv": "table.csv",
    "script": "run.sh", "key": "id_ed25519", "certificate": "server.crt", "database": "app.db",
}


def path_value(inner, rng):
    """`path/to/<thing>` -> a plausible path; the kind of place varies."""
    thing = inner.split("path/to/", 1)[1].rstrip("0123456789") or "file"
    name = next((v for k, v in EXTENSIONS.items() if k in thing), None)
    if name is None:
        name = "notes.txt" if "file" in thing else thing.replace("_", "-")
    roll = rng.random()
    if roll < 0.12:
        return "$" + re.sub(r"[^A-Z0-9]+", "_", thing.upper()).strip("_")
    if roll < 0.35:
        return f"{rng.choice(OUTSIDE_DIRS)}/{name}"
    directory = rng.choice(PROJECT_DIRS)
    return name if directory == "." else f"{directory}/{name}"


def fill(inner, rng):
    inner = inner.strip()
    if inner.startswith("[") and inner.endswith("]") and "|" in inner:
        return rng.choice(inner[1:-1].split("|"))
    if " ..." in inner or inner.endswith("..."):
        inner = inner.replace("...", "").split()[0] if inner.replace("...", "").split() else ""
    if "path/to/" in inner:
        return path_value(inner, rng)
    if rng.random() < 0.08 and re.fullmatch(r"[a-z_]+", inner):
        return "$" + inner.upper()
    return inner


def concrete(cmd, rng):
    out = PLACEHOLDER.sub(lambda m: fill(m.group(1), rng), cmd)
    return re.sub(r"\s+", " ", out).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tldr", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--variants", type=int, default=1,
                    help="fillings per example; duplicates are dropped, so placeholder-free examples yield one")
    args = ap.parse_args()
    rng = random.Random(args.seed)
    seen, n = set(), 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as out:
        for platform in PLATFORMS:
            for page in sorted((args.tldr / "pages" / platform).glob("*.md")):
                program = page.stem
                for m in EXAMPLE.finditer(page.read_text()):
                    for variant in range(args.variants):
                        command = concrete(m["cmd"], rng)
                        if not command or command in seen:
                            continue
                        seen.add(command)
                        out.write(json.dumps({
                            "program": program, "platform": platform, "variant": variant,
                            "command": command, "description": m["desc"].strip(),
                        }) + "\n")
                        n += 1
    print(f"{n} commands -> {args.out}")


if __name__ == "__main__":
    main()
