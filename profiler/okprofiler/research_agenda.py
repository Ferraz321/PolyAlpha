import json
from pathlib import Path

from .features import factor_library_rows
from .validation_summary import _bucket


def build_research_agenda(
    candidates_path: Path | None,
    validations_path: Path | None,
    diagnostics_path: Path | None,
    profile_dir: Path,
    db: Path,
    limit: int = 20,
    candidate_rows: list[dict] | None = None,
) -> dict:
    candidates = candidate_rows if candidate_rows is not None else _read_candidates(candidates_path)
    validations = _read_validations(validations_path)
    diagnostics = _read_json(diagnostics_path)
    library = {row["column"]: row for row in factor_library_rows()}
    rows = _agenda_rows(candidates, validations, diagnostics, library)
    rows = sorted(rows, key=lambda row: (-row["score"], row["factor_id"]))[:limit]
    commands = _commands_for_missing_sources(rows, profile_dir, db)
    return {
        "version": 1,
        "profile_dir": str(profile_dir),
        "sources": {
            "candidates": str(candidates_path) if candidates_path else None,
            "validations": str(validations_path) if validations_path else None,
            "diagnostics": str(diagnostics_path) if diagnostics_path else None,
        },
        "factor_count": len(rows),
        "category_counts": _category_counts(rows),
        "agenda": rows,
        "commands": commands,
    }


def render_research_agenda(agenda: dict) -> str:
    lines = [
        "# Factor Research Agenda",
        "",
        f"- profile_dir: `{agenda['profile_dir']}`",
        f"- factor_count: {agenda['factor_count']}",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in agenda.get("category_counts", {}).items():
        lines.append(f"- {category}: {count}")
    lines.extend(
        [
            "",
            "## Priority Factors",
            "",
            "| Rank | Factor | Category | Bucket | Score | Missing Sources | Next Action |",
            "| ---: | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for index, row in enumerate(agenda.get("agenda", []), start=1):
        missing = ", ".join(row.get("missing_sources", [])) or "-"
        lines.append(
            f"| {index} | `{row['factor_id']}` | {row['category']} | {row['bucket']} | "
            f"{row['score']} | {missing} | {row['next_action']} |"
        )
    lines.extend(["", "## Commands", ""])
    if not agenda.get("commands"):
        lines.append("- no data-collection command needed for the current agenda")
    for command in agenda.get("commands", []):
        lines.append(f"- {command['reason']}: `{' '.join(command['command'])}`")
    return "\n".join(lines) + "\n"


def _agenda_rows(
    candidates: list[dict],
    validations: dict[str, dict],
    diagnostics: dict,
    library: dict[str, dict],
) -> list[dict]:
    sources = diagnostics.get("sources", {})
    factor_coverage = {
        row.get("factor"): row
        for row in diagnostics.get("factor_coverage", [])
        if row.get("factor")
    }
    rows = []
    for candidate in candidates:
        factor_id = candidate.get("factor") or candidate.get("factor_id")
        if not factor_id:
            continue
        definition = library.get(factor_id, {})
        validation = validations.get(factor_id, {})
        coverage = factor_coverage.get(factor_id, {})
        merged = {
            "factor_id": factor_id,
            "status": candidate.get("status", "candidate"),
            "validation_status": candidate.get("validation_status"),
            "verdict": validation.get("verdict"),
        }
        bucket = _bucket(merged)
        missing_sources = _missing_sources(candidate, coverage, definition, sources)
        next_action = _next_action(bucket, missing_sources, candidate, validation)
        row = {
            "factor_id": factor_id,
            "label": definition.get("label", factor_id),
            "category": definition.get("category", _candidate_category(candidate)),
            "playbooks": definition.get("playbooks", candidate.get("market_categories", [])),
            "status": candidate.get("status", "candidate"),
            "bucket": bucket,
            "verdict": validation.get("verdict") or candidate.get("validation_status") or "not_tested",
            "priority": int(candidate.get("priority", 3)),
            "score": _score(candidate, bucket, missing_sources, validation, definition),
            "required_data": candidate.get("required_data") or ", ".join(definition.get("requires", [])),
            "missing_sources": missing_sources,
            "reason": candidate.get("reason") or definition.get("calculation", ""),
            "calculation": definition.get("calculation"),
            "implemented_by": definition.get("implemented_by"),
            "next_action": next_action,
        }
        if bucket != "rejected":
            rows.append(row)
    return rows


def _score(
    candidate: dict,
    bucket: str,
    missing_sources: list[str],
    validation: dict,
    definition: dict,
) -> int:
    score = 100 - int(candidate.get("priority", 3)) * 10
    if candidate.get("status") == "active_unvalidated":
        score += 15
    if bucket == "promising":
        score += 30
    elif bucket == "blocked":
        score += 12
    elif bucket == "not_tested":
        score += 20
    elif bucket == "effective":
        score += 5
    if missing_sources:
        score += min(12, len(missing_sources) * 4)
    if validation.get("out_of_sample_score", 0) and validation.get("out_of_sample_score", 0) > 0:
        score += 10
    if definition.get("category") in {"sector", "news", "microstructure", "settlement_timing"}:
        score += 8
    return score


def _next_action(
    bucket: str,
    missing_sources: list[str],
    candidate: dict,
    validation: dict,
) -> str:
    if missing_sources:
        return "collect_missing_sources_then_run_react_validation"
    if bucket == "promising":
        return "expand_sample_and_validate_replication"
    if bucket == "effective":
        return "estimate_capacity_and_build_strategy_rule"
    if bucket == "blocked":
        return "unblock_required_data"
    if validation.get("rows", 0) and validation.get("rows", 0) < 50:
        return "collect_more_rows"
    if candidate.get("status") == "active_unvalidated":
        return "run_react_validation_on_real_profile"
    return "implement_or_attach_factor_then_validate"


def _missing_sources(candidate: dict, coverage: dict, definition: dict, sources: dict) -> list[str]:
    missing = set(coverage.get("missing_sources", []))
    required_data = candidate.get("required_data", "")
    required_map = {
        "external_weather_observation": ["weather_observations"],
        "external_weather_forecast": ["weather_forecasts"],
        "official_weather_observations_and_forecast_history": ["official_weather", "weather_forecasts"],
        "intraday_official_weather_observations": ["official_weather"],
        "market_rules_and_official_weather_station_observations": ["weather_events", "official_weather"],
        "sibling_weather_market_prices": ["weather_events"],
        "fills_and_settlement": ["settlement_events"],
        "fills_and_clob_features": ["clob_features"],
        "fills_and_news_timeline": ["news"],
        "fills_and_market_sectors": ["markets"],
        "fills_and_market_resolution_times": ["markets"],
        "clob_depth_and_fills": ["clob_features"],
        "clob_bbo_and_fills": ["clob_features"],
    }
    for source in required_map.get(required_data, []):
        if _source_missing(source, sources):
            missing.add(source)
    for source in definition.get("requires", []):
        if _source_missing(source, sources):
            missing.add(source)
    return sorted(source for source in missing if source not in {"fills", "factor_table"})


def _source_missing(source: str, sources: dict) -> bool:
    if not sources:
        return source != "fills"
    if source == "settlement_events":
        return True
    return not sources.get(source, {}).get("ready", False)


def _commands_for_missing_sources(rows: list[dict], profile_dir: Path, db: Path) -> list[dict]:
    sources = {source for row in rows for source in row.get("missing_sources", [])}
    commands = []
    if "markets" in sources:
        commands.append(
            {
                "source": "markets",
                "reason": "fetch Gamma market metadata for sector and resolution factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-gamma-markets",
                    "--out",
                    str(profile_dir / "markets.csv"),
                ],
            }
        )
    if "clob_features" in sources:
        commands.append(
            {
                "source": "clob_features",
                "reason": "collect CLOB snapshots for microstructure factors",
                "command": [
                    "cargo",
                    "run",
                    "--",
                    "watch-clob",
                    "--db",
                    str(db),
                    "--assets-file",
                    str(profile_dir / "clob_assets.txt"),
                ],
            }
        )
    if "news" in sources:
        commands.append(
            {
                "source": "news",
                "reason": "attach a timestamped news/RSS timeline for information-edge factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-news-rss",
                    "--url",
                    "<rss-url>",
                    "--out",
                    str(profile_dir / "news.csv"),
                ],
            }
        )
    if "weather_observations" in sources:
        commands.append(
            {
                "source": "weather_observations",
                "reason": "fetch weather observations for actual-temperature factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-weather-open-meteo",
                    "--profile-dir",
                    str(profile_dir),
                    "--locations-csv",
                    "config/weather_locations.csv",
                    "--out",
                    str(profile_dir / "weather_observations.csv"),
                ],
            }
        )
    if "weather_forecasts" in sources:
        commands.append(
            {
                "source": "weather_forecasts",
                "reason": "fetch forecast history for forecast-error and model-disagreement factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-weather-forecast-history",
                    "--profile-dir",
                    str(profile_dir),
                    "--locations-csv",
                    "config/weather_locations.csv",
                    "--out",
                    str(profile_dir / "forecast_history.csv"),
                ],
            }
        )
    if "weather_events" in sources:
        commands.append(
            {
                "source": "weather_events",
                "reason": "fetch official weather market context and sibling ladder metadata",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-weather-event-contexts",
                    "--fills",
                    str(profile_dir / "fills.csv"),
                    "--out",
                    str(profile_dir / "weather_event_contexts.csv"),
                ],
            }
        )
    if "official_weather" in sources:
        commands.append(
            {
                "source": "official_weather",
                "reason": "fetch official station observations for settlement-grade weather factors",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "fetch-official-weather-observations",
                    "--contexts",
                    str(profile_dir / "weather_event_contexts.csv"),
                    "--out",
                    str(profile_dir / "official_weather_observations.csv"),
                ],
            }
        )
    if "settlement_events" in sources:
        commands.append(
            {
                "source": "settlement_events",
                "reason": "import settlement/redemption evidence for audited PnL factors",
                "command": [
                    "cargo",
                    "run",
                    "--",
                    "import-settlements",
                    "--db",
                    str(db),
                    "--input",
                    str(profile_dir / "settlement_events.csv"),
                ],
            }
        )
    if commands:
        commands.append(
            {
                "source": "profile",
                "reason": "rerun profiler and ReAct validation after data is collected",
                "command": [
                    "python",
                    "profiler/profile_wallets.py",
                    "agent",
                    "--profile-dir",
                    str(profile_dir),
                    "--db",
                    str(db),
                    "--rerun-profile",
                ],
            }
        )
    return commands


def _category_counts(rows: list[dict]) -> dict:
    counts = {}
    for row in rows:
        category = row.get("category", "unknown")
        counts[category] = counts.get(category, 0) + 1
    return dict(sorted(counts.items()))


def _candidate_category(candidate: dict) -> str:
    categories = candidate.get("market_categories", [])
    return categories[0] if categories else "unknown"


def _read_candidates(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("candidates", []) if isinstance(data, dict) else []


def _read_validations(path: Path | None) -> dict[str, dict]:
    if path is None or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    validations = data.get("validations", []) if isinstance(data, dict) else []
    return {
        validation["factor_id"]: validation
        for validation in validations
        if validation.get("factor_id")
    }


def _read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
