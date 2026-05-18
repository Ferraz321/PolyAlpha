#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: scripts/watch_wallet_clob.py 0xwallet [db]", file=sys.stderr)
        return 2
    wallet = sys.argv[1]
    db = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OKTRADER_DB", "data/oktrader.sqlite")
    out_dir = Path(os.environ.get("OKTRADER_PROFILE_DIR", "data/profiler_wallet_clob"))
    env = os.environ | {"OKTRADER_PROFILE_DIR": str(out_dir)}
    profile = subprocess.call([_python(), "scripts/profile_wallet.py", wallet, db], env=env)
    if profile != 0:
        return profile
    cmd = [
        "cargo",
        "run",
        "--",
        "watch-clob",
        "--db",
        db,
        "--assets-file",
        str(out_dir / "clob_assets.txt"),
        "--chunk-size",
        os.environ.get("OKTRADER_CLOB_CHUNK_SIZE", "500"),
        "--reconnect-min-secs",
        os.environ.get("OKTRADER_CLOB_RECONNECT_MIN_SECS", "2"),
        "--reconnect-max-secs",
        os.environ.get("OKTRADER_CLOB_RECONNECT_MAX_SECS", "60"),
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
