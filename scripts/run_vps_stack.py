#!/usr/bin/env python3
import os
import subprocess
from pathlib import Path


def main() -> int:
    _load_env()
    for directory in ["data", "logs", "run"]:
        Path(directory).mkdir(exist_ok=True)
    bin_path = Path("target/release/oktrader-alpha")
    if not bin_path.exists():
        code = subprocess.call(["cargo", "build", "--release"])
        if code != 0:
            return code
    db = os.environ.get("OKTRADER_DB", "data/oktrader.sqlite")
    subprocess.call([str(bin_path), "init-db", "--db", db])
    _start("collector", [str(bin_path), "collector-data-api", "--db", db, "--interval-secs", _env("COLLECTOR_INTERVAL_SECS", "60")])
    _start("analyzer", [str(bin_path), "analyzer", "--db", db, "--interval-secs", _env("ANALYZER_INTERVAL_SECS", "120")])
    _start("alerts", [str(bin_path), "alerts", "--db", db, "--interval-secs", _env("ALERT_INTERVAL_SECS", "5"), "--all-wallets"])
    _start("summary-loop", [_python(), "scripts/summary_loop.py"])
    if _env("OKTRADER_ENABLE_RPC", "0") == "1":
        rpc = os.environ.get("POLYGON_RPC_URL", "")
        if not rpc:
            print("OKTRADER_ENABLE_RPC=1 but POLYGON_RPC_URL is empty")
            return 1
        _start("watch-live", [str(bin_path), "watch-live", "--db", db, "--rpc-url", rpc, "--include-neg-risk"])
    else:
        print("watch-live skipped; set OKTRADER_ENABLE_RPC=1 and POLYGON_RPC_URL to enable")
    return subprocess.call([_python(), "scripts/status.py"])


def _start(name: str, cmd: list[str]) -> None:
    pidfile = Path("run") / f"{name}.pid"
    if pidfile.exists() and _running(int(pidfile.read_text())):
        print(f"{name} already running pid={pidfile.read_text().strip()}")
        return
    log = open(Path("logs") / f"{name}.log", "a", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
    pidfile.write_text(str(proc.pid), encoding="utf-8")
    print(f"started {name} pid={proc.pid}")


def _running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _load_env() -> None:
    path = Path(".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _python() -> str:
    venv = Path(".venv/bin/python")
    return str(venv) if venv.exists() else "python3"


if __name__ == "__main__":
    raise SystemExit(main())
