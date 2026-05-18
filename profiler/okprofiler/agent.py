from dataclasses import dataclass
import json
from pathlib import Path

from .agent_planner import next_commands
from .agent_tools import AgentToolConfig, run_agent_tools, update_candidate_library
from .pipeline import ProfilerConfig, run_profiler
from .sop import build_sop_status, write_sop_status


@dataclass(frozen=True)
class AgentConfig:
    profile_dir: Path
    rules_path: Path
    diagnostics_path: Path
    report_out: Path
    candidates_out: Path
    next_commands_out: Path
    sop_status_out: Path
    sop_path: Path
    candidate_library: Path
    db: Path
    wallets: list[str]
    rerun_profile: bool
    run_tools: bool
    launch_watch_clob: bool
    update_candidates: bool
    research_engines: list[str]
    min_samples: int
    trades_limit: int = 500
    trades_max_offset: int = 5000
    gamma_limit: int = 500
    gamma_max_offset: int = 5000


def run_agent(config: AgentConfig) -> dict:
    tool_result = {}
    if config.run_tools:
        tool_result = run_agent_tools(
            AgentToolConfig(
                profile_dir=config.profile_dir,
                db=config.db,
                wallets=config.wallets,
                launch_watch_clob=config.launch_watch_clob,
                min_samples=config.min_samples,
                research_engines=config.research_engines,
                trades_limit=config.trades_limit,
                trades_max_offset=config.trades_max_offset,
                gamma_limit=config.gamma_limit,
                gamma_max_offset=config.gamma_max_offset,
            )
        )
    elif config.rerun_profile:
        _rerun_profile(config)
    rules = _read_json(config.rules_path)
    diagnostics = _read_json(config.diagnostics_path)
    candidates = _candidate_factors(rules)
    commands = next_commands(config.profile_dir, config.db, diagnostics, candidates)
    result = {
        "version": 1,
        "profile_dir": str(config.profile_dir),
        "rules_path": str(config.rules_path),
        "diagnostics_path": str(config.diagnostics_path),
        "tool_result": tool_result,
        "wallets": _wallet_summaries(rules),
        "candidates": candidates,
        "next_commands": commands,
        "sop_status": {},
        "missing_actions": diagnostics.get("missing_actions", []),
    }
    _write_json(config.candidates_out, {"version": 1, "candidates": candidates})
    _write_json(config.next_commands_out, {"version": 1, "commands": commands})
    if config.update_candidates:
        update_candidate_library(config.candidate_library, candidates)
    _write_text(config.report_out, _render_report(result, diagnostics))
    sop_status = build_sop_status(
        config.profile_dir,
        diagnostics,
        rules,
        candidates,
        commands,
        config.sop_path,
    )
    result["sop_status"] = sop_status
    write_sop_status(sop_status, config.sop_status_out)
    _write_text(config.report_out, _render_report(result, diagnostics))
    return result


def _rerun_profile(config: AgentConfig) -> None:
    run_profiler(
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
            diagnostics_out=config.diagnostics_path,
            factor_summary_out=config.profile_dir / "factor_summary.md",
            factor_log_out=config.profile_dir / "factor_research_log.md",
            lookback_secs=60,
            min_samples=config.min_samples,
            research_engines=config.research_engines,
        )
    )


def _wallet_summaries(rules: dict) -> list[dict]:
    out = []
    for wallet in rules.get("wallets", []):
        best = wallet.get("mining", {}).get("best_rule", {})
        out.append(
            {
                "account": wallet.get("account"),
                "samples": wallet.get("samples", 0),
                "candidate_rule": wallet.get("candidate_rule"),
                "best_factor": best.get("name", "none"),
                "explainability_score": wallet.get("explainability_score", 0.0),
                "market_categories": wallet.get("market_categories", []),
                "next_experiments": wallet.get("researcher", {}).get("next_experiments", []),
                "caveats": wallet.get("researcher", {}).get("caveats", []),
            }
        )
    return out


def _candidate_factors(rules: dict) -> list[dict]:
    candidates = {}
    for wallet in rules.get("wallets", []):
        account = wallet.get("account")
        for category in wallet.get("market_categories", []):
            for factor in category.get("next_candidate_factors", []):
                item = candidates.setdefault(
                    factor,
                    {
                        "factor": factor,
                        "status": "candidate",
                        "priority": _priority(factor),
                        "required_data": _required_data(factor),
                        "market_categories": set(),
                        "wallets": set(),
                        "reason": _reason(factor, category),
                    },
                )
                item["market_categories"].add(category.get("id", "unknown"))
                item["wallets"].add(account)
    return [
        {
            **item,
            "market_categories": sorted(item["market_categories"]),
            "wallets": sorted(wallet for wallet in item["wallets"] if wallet),
        }
        for item in sorted(candidates.values(), key=lambda row: (row["priority"], row["factor"]))
    ]


def _render_report(result: dict, diagnostics: dict) -> str:
    lines = [
        "# OKTRADER Agent Research Report",
        "",
        f"- profile_dir: `{result['profile_dir']}`",
        f"- diagnostics_ready: {diagnostics.get('ready', False)}",
        "",
        "## Data Readiness",
        "",
    ]
    for name, source in diagnostics.get("sources", {}).items():
        rows = source.get("rows", 0)
        missing = ", ".join(source.get("missing_columns", [])) or "-"
        lines.append(f"- {name}: ready={source.get('ready', False)} rows={rows} missing={missing}")
    lines.extend(["", "## Wallet Findings", ""])
    for wallet in result["wallets"]:
        lines.extend(_wallet_lines(wallet))
    lines.extend(["", "## Candidate Factor Backlog", ""])
    for candidate in result["candidates"]:
        lines.append(
            f"- `{candidate['factor']}` priority={candidate['priority']} "
            f"required_data={candidate['required_data']}: {candidate['reason']}"
        )
    lines.extend(["", "## SOP Status", ""])
    for stage in result.get("sop_status", {}).get("stages", []):
        missing = "; ".join(stage.get("missing", [])) or "-"
        lines.append(f"- {stage.get('id')}: {stage.get('status')} missing={missing}")
    lines.extend(["", "## Next Commands", ""])
    for command in result.get("next_commands", []):
        lines.append(f"- {command.get('reason')}: `{' '.join(command.get('command', []))}`")
    if result.get("tool_result", {}).get("runs"):
        lines.extend(["", "## Tool Runs", ""])
        for run in result["tool_result"]["runs"]:
            lines.append(f"- {run['name']}: {run['status']}")
    if result.get("missing_actions"):
        lines.extend(["", "## Missing Actions", ""])
        for action in result["missing_actions"]:
            lines.append(f"- {action}")
    lines.extend(["", "## Next Agent Loop", "", "Run with `--rerun-profile` after new data is added."])
    return "\n".join(lines) + "\n"


def _wallet_lines(wallet: dict) -> list[str]:
    lines = [
        f"### {wallet.get('account')}",
        "",
        f"- samples: {wallet.get('samples', 0)}",
        f"- best_factor: {wallet.get('best_factor')}",
        f"- rule: `{wallet.get('candidate_rule')}`",
        f"- explainability_score: {wallet.get('explainability_score', 0.0):.4f}",
    ]
    for category in wallet.get("market_categories", []):
        lines.append(
            f"- market_category: {category.get('label')} "
            f"confidence={category.get('confidence', 0.0):.2%}; {category.get('summary')}"
        )
    if wallet.get("next_experiments"):
        lines.append("- next_experiments: " + "; ".join(wallet["next_experiments"]))
    if wallet.get("caveats"):
        lines.append("- caveats: " + "; ".join(wallet["caveats"]))
    lines.append("")
    return lines


def _priority(factor: str) -> int:
    if "forecast_error" in factor or "actual_temp" in factor:
        return 1
    if factor.startswith("forecast_") or "model_" in factor:
        return 2
    return 3


def _required_data(factor: str) -> str:
    if factor.startswith("forecast_") or factor in {"model_disagreement", "bucket_distance_from_normal"}:
        return "external_weather_forecast"
    if factor.startswith("actual_temp"):
        return "external_weather_observation"
    if factor.startswith("weather_") or factor.startswith("city_"):
        return "fills_and_settlement"
    return "factor_table"


def _reason(factor: str, category: dict) -> str:
    label = category.get("label", "market playbook")
    return f"needed by {label} to test whether the observed specialization is a reusable edge"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _optional(path: Path) -> Path | None:
    return path if path.exists() else None
