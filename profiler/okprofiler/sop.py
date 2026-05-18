import json
from pathlib import Path
from typing import Any


DEFAULT_SOP = Path("config/agent_sop.json")


def build_sop_status(
    profile_dir: Path,
    diagnostics: dict,
    rules: dict,
    candidates: list[dict],
    commands: list[dict],
    sop_path: Path = DEFAULT_SOP,
) -> dict:
    sop = _read_sop(sop_path)
    artifacts = _artifact_status(profile_dir)
    stages = [
        _stage_status(stage, diagnostics, rules, candidates, commands, artifacts)
        for stage in sop.get("stages", [])
    ]
    return {
        "version": sop.get("version", 1),
        "sop": sop.get("name", "OKTRADER Research SOP"),
        "profile_dir": str(profile_dir),
        "complete": all(stage["status"] == "done" for stage in stages),
        "stages": stages,
        "promotion_gates": sop.get("promotion_gates", []),
    }


def write_sop_status(status: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, indent=2), encoding="utf-8")


def _stage_status(
    stage: dict,
    diagnostics: dict,
    rules: dict,
    candidates: list[dict],
    commands: list[dict],
    artifacts: dict[str, bool],
) -> dict:
    checks = [_check(item, diagnostics, rules, candidates, commands, artifacts) for item in stage.get("checks", [])]
    missing = [item["label"] for item in checks if not item["ok"]]
    status = "done" if checks and not missing else "blocked" if missing else "pending"
    return {
        "id": stage.get("id"),
        "label": stage.get("label"),
        "status": status,
        "missing": missing,
        "checks": checks,
        "tools": stage.get("tools", []),
        "outputs": stage.get("outputs", []),
    }


def _check(
    spec: dict,
    diagnostics: dict,
    rules: dict,
    candidates: list[dict],
    commands: list[dict],
    artifacts: dict[str, bool],
) -> dict:
    kind = spec.get("kind")
    value = spec.get("value")
    ok = False
    if kind == "artifact":
        ok = artifacts.get(value, False)
    elif kind == "source_ready":
        ok = diagnostics.get("sources", {}).get(value, {}).get("ready", False)
    elif kind == "any_wallet":
        ok = bool(rules.get("wallets"))
    elif kind == "any_candidate":
        ok = bool(candidates)
    elif kind == "any_command":
        ok = bool(commands)
    elif kind == "diagnostics_ready":
        ok = bool(diagnostics)
    elif kind == "strategy_config":
        ok = artifacts.get("strategy_config.json", False)
    elif kind == "no_missing_actions":
        ok = not diagnostics.get("missing_actions")
    return {"label": spec.get("label", value or kind), "kind": kind, "ok": ok}


def _artifact_status(profile_dir: Path) -> dict[str, bool]:
    names = [
        "resolved_user.json",
        "fills.csv",
        "markets.csv",
        "weather_observations.csv",
        "factor_table.parquet",
        "rules.json",
        "diagnostics.json",
        "strategy_config.json",
        "research_report.md",
        "candidate_factors.json",
        "next_commands.json",
    ]
    return {name: (profile_dir / name).exists() and (profile_dir / name).stat().st_size > 0 for name in names}


def _read_sop(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "name": "OKTRADER Research SOP",
        "stages": [
            {"id": "profile", "label": "Profile", "checks": [{"kind": "any_wallet", "label": "wallet rules"}]}
        ],
        "promotion_gates": [],
    }
