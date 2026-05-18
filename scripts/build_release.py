#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path


def main() -> int:
    for directory in ["data", "logs", "run"]:
        Path(directory).mkdir(exist_ok=True)
    build = subprocess.call(["cargo", "build", "--release"])
    if build != 0:
        return build
    db = os.environ.get("OKTRADER_DB", "data/oktrader.sqlite")
    init = subprocess.call(["target/release/oktrader-alpha", "init-db", "--db", db])
    if init == 0:
        print("release binary ready: target/release/oktrader-alpha")
    return init


if __name__ == "__main__":
    raise SystemExit(main())
