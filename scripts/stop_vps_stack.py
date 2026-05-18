#!/usr/bin/env python3
import os
from pathlib import Path


def main() -> int:
    for pidfile in sorted(Path("run").glob("*.pid")):
        pid = int(pidfile.read_text())
        if _running(pid):
            os.kill(pid, 15)
            print(f"stopped {pidfile.stem} pid={pid}")
        pidfile.unlink(missing_ok=True)
    return 0


def _running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
