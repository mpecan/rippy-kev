#!/usr/bin/env python3
"""Record the question set rippy sends, byte for byte, from a real request.

    teacher/capture_questions.py --rippy ../rippy/target/release/rippy --out data/questions.json

Starts a one-shot local System One endpoint, points `rippy jev` at it, and
saves `questions` and the question-set version from the reason string. Training
records must use these exact strings: Kev binds behaviour to the wording.
"""

import argparse
import json
import os
import re
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

captured = {}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        captured["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(503)
        self.end_headers()

    def log_message(self, *_):
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rippy", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "config.toml"
        config.write_text(
            "[jev]\nenabled = true\n"
            f'endpoint = "http://127.0.0.1:{server.server_port}/v1/systemone"\n'
            'model = "capture"\napi-key-env = "RIPPY_KEV_DUMMY_KEY"\n'
        )
        (Path(tmp) / ".git").mkdir()
        subprocess.run(
            [str(args.rippy.resolve()), "jev", "--config", str(config), "--", "lsusb -v"],
            cwd=tmp, env={**os.environ, "RIPPY_KEV_DUMMY_KEY": "x"}, capture_output=True,
            check=True,
        )
    body = captured["body"]
    source = (args.rippy.resolve().parents[2] / "src/jev/request.rs").read_text()
    version = re.search(r'QUESTION_SET_VERSION: &str = "(\w+)"', source)[1]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"version": version, "questions": body["questions"]}, indent=1))
    print(f"question set {version}: {sorted(body['questions'])} -> {args.out}")


if __name__ == "__main__":
    main()
