#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: scripts/profile_wallet.py 0xwallet [db]", file=sys.stderr)
        return 2
    wallet = sys.argv[1]
    db = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OKTRADER_DB", "data/oktrader.sqlite")
    out_dir = Path(os.environ.get("OKTRADER_PROFILE_DIR", "data/profiler"))
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        _python(),
        "profiler/profile_wallets.py",
        "agent",
        "--profile-dir",
        str(out_dir),
        "--wallet",
        wallet,
        "--db",
        db,
        "--run-tools",
        "--update-candidates",
        "--min-samples",
        os.environ.get("OKTRADER_MIN_SAMPLES", "2"),
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
