#!/usr/bin/env python3
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    _load_env()
    db = os.environ.get("OKTRADER_DB", "data/oktrader.sqlite")
    interval = int(os.environ.get("SUMMARY_INTERVAL_SECS", "300"))
    bin_path = "target/release/oktrader-alpha"
    while True:
        print(datetime.now(timezone.utc).isoformat(), flush=True)
        subprocess.call([bin_path, "summary", "--db", db])
        time.sleep(interval)


def _load_env() -> None:
    path = Path(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
