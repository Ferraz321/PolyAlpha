from datetime import datetime, timezone
from pathlib import Path


def write_factor_outputs(rules: dict, summary_out: Path | None, log_out: Path | None) -> None:
    if summary_out is not None:
        summary_out.parent.mkdir(parents=True, exist_ok=True)
        summary_out.write_text(render_factor_summary(rules), encoding="utf-8")
    if log_out is not None:
        log_out.parent.mkdir(parents=True, exist_ok=True)
        with log_out.open("a", encoding="utf-8") as handle:
            handle.write(render_factor_log_entry(rules))


def render_factor_summary(rules: dict) -> str:
    diagnostics = rules.get("diagnostics", {})
    lines = [
        "# Factor Summary",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- diagnostics_ready: {diagnostics.get('ready', False)}",
        "",
        "## Coverage",
        "",
        "| Factor | Available | Non-null Rows | Missing Sources |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in diagnostics.get("factor_coverage", []):
        missing = ", ".join(row.get("missing_sources", [])) or "-"
        lines.append(
            f"| `{row['factor']}` | {row.get('available', False)} | "
            f"{row.get('non_null_rows', 0)} | {missing} |"
        )
    lines.extend(["", "## Best Wallet Rules", ""])
    for wallet in rules.get("wallets", []):
        best = wallet.get("mining", {}).get("best_rule", {})
        lines.append(f"- `{wallet.get('account')}`: {best.get('name', 'none')} -> `{wallet.get('candidate_rule')}`")
    lines.extend(["", "## Market Category Playbooks", ""])
    has_category = False
    for wallet in rules.get("wallets", []):
        for category in wallet.get("market_categories", []):
            has_category = True
            lines.append(
                f"- `{wallet.get('account')}`: {category['label']} "
                f"confidence={category['confidence']:.2%}; {category['summary']}"
            )
            lines.append(
                "  - next_candidate_factors: "
                + ", ".join(category.get("next_candidate_factors", [])[:8])
            )
    if not has_category:
        lines.append("- no market-specific playbook matched")
    react = rules.get("factor_react_loop", {})
    if react:
        lines.extend(["", "## ReAct Factor Validation", ""])
        summary = react.get("summary", {})
        lines.append(
            "- verdicts: "
            + ", ".join(f"{key}={value}" for key, value in sorted(summary.items()))
        )
        for step in react.get("steps", [])[:20]:
            observation = step.get("observation", {})
            lines.append(
                f"- `{step.get('factor_id')}` verdict={step.get('verdict')} "
                f"rows={observation.get('rows', 0)} next={step.get('next_action')}"
            )
    if diagnostics.get("missing_actions"):
        lines.extend(["", "## Missing Actions", ""])
        for action in diagnostics["missing_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines) + "\n"


def render_factor_log_entry(rules: dict) -> str:
    lines = [
        "\n## Run " + datetime.now(timezone.utc).isoformat(),
        "",
    ]
    diagnostics = rules.get("diagnostics", {})
    available = [
        row["factor"]
        for row in diagnostics.get("factor_coverage", [])
        if row.get("available", False)
    ]
    lines.append(f"- available_factors: {', '.join(available) if available else 'none'}")
    for wallet in rules.get("wallets", []):
        best = wallet.get("mining", {}).get("best_rule", {})
        lines.append(
            f"- wallet `{wallet.get('account')}` best_factor={best.get('name', 'none')} "
            f"rule=`{wallet.get('candidate_rule')}` samples={wallet.get('samples', 0)}"
        )
        for category in wallet.get("market_categories", []):
            lines.append(
                f"- market_category `{category['id']}` confidence={category['confidence']:.2%} "
                f"active={', '.join(category.get('active_factors', []))}"
            )
    for action in diagnostics.get("missing_actions", []):
        lines.append(f"- missing_action: {action}")
    react = rules.get("factor_react_loop", {})
    if react:
        lines.append(
            "- react_validation: "
            + ", ".join(
                f"{key}={value}" for key, value in sorted(react.get("summary", {}).items())
            )
        )
        for step in react.get("steps", [])[:10]:
            lines.append(
                f"- react_step factor={step.get('factor_id')} verdict={step.get('verdict')} "
                f"next={step.get('next_action')}"
            )
    return "\n".join(lines) + "\n"
