import csv
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .data_sources import assets_from_fills, fetch_gamma_markets, fetch_user_trades
from .pipeline import ProfilerConfig, run_profiler
from .agent_weather import fetch_weather_context, has_weather_category


@dataclass
class ToolRun:
    name: str
    command: list[str]
    status: str
    stdout: str = ""
    stderr: str = ""


@dataclass
class AgentToolConfig:
    profile_dir: Path
    db: Path
    wallets: list[str] = field(default_factory=list)
    cargo_bin: str = "cargo"
    rust_release: bool = False
    fetch_remote_trades: bool = True
    fetch_markets: bool = True
    run_rust_export: bool = True
    run_profile: bool = True
    validate_strategy: bool = True
    launch_watch_clob: bool = False
    min_trades: int = 5
    min_markets: int = 1
    min_closed_markets: int = 0
    min_clob_aligned: int = 1
    trades_limit: int = 500
    trades_max_offset: int = 5000
    gamma_limit: int = 500
    gamma_max_offset: int = 5000
    min_samples: int = 5
    research_engines: list[str] = field(default_factory=list)
    auto_weather_context: bool = True
    weather_locations_csv: Path = Path("config/weather_locations.csv")


def run_agent_tools(config: AgentToolConfig) -> dict:
    config.profile_dir.mkdir(parents=True, exist_ok=True)
    wallet_pool = _write_wallet_pool(config.profile_dir, config.wallets)
    runs = []
    if wallet_pool and config.run_rust_export:
        runs.append(_profile_readiness(config, wallet_pool))
        runs.append(_export_profiler(config, wallet_pool))
    if config.fetch_remote_trades and _csv_data_rows(config.profile_dir / "fills.csv") == 0:
        runs.extend(_fetch_remote_trades(config))
    if config.fetch_markets:
        rows = fetch_gamma_markets(
            out=config.profile_dir / "markets.csv",
            limit=config.gamma_limit,
            max_offset=config.gamma_max_offset,
        )
        runs.append(ToolRun("fetch-gamma-markets", ["python", "fetch-gamma-markets"], "ok", stdout=f"rows={rows}"))
    if config.run_profile:
        rules = _run_profile(config)
        runs.append(ToolRun("python-profile", ["python", "profile"], "ok"))
        if config.auto_weather_context and has_weather_category(rules):
            weather_runs = fetch_weather_context(config.profile_dir, config.weather_locations_csv, rules)
            for run in weather_runs:
                runs.append(ToolRun(run.name, ["python", run.name], "ok", stdout=f"rows={run.rows}"))
            if weather_runs:
                rules = _run_profile(config)
                runs.append(ToolRun("python-profile-after-weather", ["python", "profile"], "ok"))
    asset_rows = assets_from_fills(
        fills=config.profile_dir / "fills.csv",
        out=config.profile_dir / "clob_assets.txt",
        limit=500,
    )
    runs.append(ToolRun("assets-from-fills", ["python", "assets-from-fills"], "ok", stdout=f"rows={asset_rows}"))
    if config.validate_strategy:
        runs.append(_validate_strategy(config))
    if config.launch_watch_clob:
        runs.append(_watch_clob_once(config))
    return {
        "runs": [run.__dict__ for run in runs],
        "wallet_pool": str(wallet_pool) if wallet_pool else None,
    }


def _run_profile(config: AgentToolConfig) -> dict:
    rules = run_profiler(
        ProfilerConfig(
            fills_path=config.profile_dir / "fills.csv",
            clob_path=config.profile_dir / "clob_events.csv",
            news_path=_optional(config.profile_dir / "news.csv"),
            markets_path=_optional(config.profile_dir / "markets.csv"),
            weather_path=_optional(config.profile_dir / "weather_observations.csv"),
            forecast_path=_optional(config.profile_dir / "forecast_history.csv"),
            factor_out=config.profile_dir / "factor_table.parquet",
            strategy_out=config.profile_dir / "strategy_config.json",
            report_out=config.profile_dir / "report.md",
            html_out=config.profile_dir / "report.html",
            diagnostics_out=config.profile_dir / "diagnostics.json",
            factor_summary_out=config.profile_dir / "factor_summary.md",
            factor_log_out=config.profile_dir / "factor_research_log.md",
            lookback_secs=60,
            min_samples=config.min_samples,
            research_engines=config.research_engines,
        )
    )
    (config.profile_dir / "rules.json").write_text(json.dumps(rules, indent=2), encoding="utf-8")
    return rules


def update_candidate_library(path: Path, candidates: list[dict]) -> None:
    existing = {}
    if path.exists():
        for item in json.loads(path.read_text(encoding="utf-8")).get("candidates", []):
            existing[item["factor"]] = item
    for item in candidates:
        existing[item["factor"]] = {**existing.get(item["factor"], {}), **item}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": 1, "candidates": list(existing.values())}, indent=2),
        encoding="utf-8",
    )


def _profile_readiness(config: AgentToolConfig, wallet_pool: Path) -> ToolRun:
    cmd = _cargo(config) + [
        "profile-readiness",
        "--db",
        str(config.db),
        "--wallet-pool",
        str(wallet_pool),
        "--min-trades",
        str(config.min_trades),
        "--min-markets",
        str(config.min_markets),
        "--min-closed-markets",
        str(config.min_closed_markets),
        "--min-clob-aligned",
        str(config.min_clob_aligned),
    ]
    return _run("profile-readiness", cmd, config.profile_dir / "readiness.json")


def _export_profiler(config: AgentToolConfig, wallet_pool: Path) -> ToolRun:
    cmd = _cargo(config) + [
        "export-profiler",
        "--db",
        str(config.db),
        "--wallet-pool",
        str(wallet_pool),
        "--out-fills",
        str(config.profile_dir / "fills.csv"),
        "--out-clob",
        str(config.profile_dir / "clob_events.csv"),
    ]
    return _run("export-profiler", cmd)


def _validate_strategy(config: AgentToolConfig) -> ToolRun:
    cmd = _cargo(config) + ["validate-strategy-config", "--input", str(config.profile_dir / "strategy_config.json")]
    return _run("validate-strategy-config", cmd)


def _watch_clob_once(config: AgentToolConfig) -> ToolRun:
    cmd = _cargo(config) + [
        "watch-clob",
        "--db",
        str(config.db),
        "--assets-file",
        str(config.profile_dir / "clob_assets.txt"),
        "--once",
    ]
    return _run("watch-clob-once", cmd)


def _fetch_remote_trades(config: AgentToolConfig) -> list[ToolRun]:
    paths = []
    runs = []
    for wallet in config.wallets:
        path = config.profile_dir / f"fills_{wallet.lower()}.csv"
        rows = fetch_user_trades(
            wallet=wallet,
            out=path,
            limit=config.trades_limit,
            max_offset=config.trades_max_offset,
        )
        paths.append(path)
        runs.append(ToolRun("fetch-user-trades", ["python", "fetch-user-trades", wallet], "ok", stdout=f"rows={rows}"))
    _concat_csv(paths, config.profile_dir / "fills.csv")
    return runs


def _run(name: str, cmd: list[str], stdout_path: Path | None = None) -> ToolRun:
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if stdout_path is not None:
        stdout_path.write_text(proc.stdout, encoding="utf-8")
    return ToolRun(name, cmd, "ok" if proc.returncode == 0 else "error", proc.stdout[-4000:], proc.stderr[-4000:])


def _cargo(config: AgentToolConfig) -> list[str]:
    cmd = [config.cargo_bin, "run"]
    if config.rust_release:
        cmd.append("--release")
    return cmd + ["--"]


def _write_wallet_pool(profile_dir: Path, wallets: list[str]) -> Path | None:
    if not wallets:
        return None
    path = profile_dir / "wallet_pool.txt"
    path.write_text("\n".join(wallets) + "\n", encoding="utf-8")
    return path


def _csv_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _concat_csv(paths: list[Path], out: Path) -> None:
    header = None
    rows = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            file_header = next(reader, None)
            header = header or file_header
            rows.extend(reader)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if header:
            writer.writerow(header)
        writer.writerows(rows)


def _optional(path: Path) -> Path | None:
    return path if path.exists() else None
