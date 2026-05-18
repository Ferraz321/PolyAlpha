#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: scripts/research_user.py @username-or-url [db]", file=sys.stderr)
        return 2
    user_id = sys.argv[1]
    db = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OKTRADER_DB", "data/oktrader.sqlite")
    cmd = [
        _python(),
        "profiler/profile_wallets.py",
        "research-user",
        user_id,
        "--db",
        db,
        "--update-candidates",
    ]
    return subprocess.call(cmd)


def _python() -> str:
    configured = os.environ.get("OKTRADER_PYTHON")
    if configured:
        return configured
    venv = Path(".venv/bin/python")
    return str(venv) if venv.exists() else sys.executable


if __name__ == "__main__":
    raise SystemExit(main())
