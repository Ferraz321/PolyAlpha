#!/usr/bin/env python3
import os
from pathlib import Path


def main() -> int:
    pidfiles = sorted(Path("run").glob("*.pid"))
    if not pidfiles:
        print("no pid files")
        return 0
    for pidfile in pidfiles:
        pid = int(pidfile.read_text())
        status = "running" if _running(pid) else "stopped"
        print(f"{pidfile.stem} {status} pid={pid}")
    return 0


def _running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
