#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys


def main() -> int:
    out_dir = os.environ.get("OKTRADER_PROFILE_DIR", "data/profiler")
    cmd = [_python(), "profiler/profile_wallets.py", "agent", "--profile-dir", out_dir, *sys.argv[1:]]
    return subprocess.call(cmd)


def _python() -> str:
    configured = os.environ.get("OKTRADER_PYTHON")
    if configured:
        return configured
    venv = Path(".venv/bin/python")
    return str(venv) if venv.exists() else sys.executable


if __name__ == "__main__":
    raise SystemExit(main())
