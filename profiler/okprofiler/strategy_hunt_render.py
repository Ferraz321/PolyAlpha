def render_strategy_hunt(result: dict) -> str:
    lines = [
        "# Strategy Hunt Reliability Report",
        "",
        f"- generated_at: `{result.get('generated_at')}`",
        f"- found_reliable_strategy: `{result.get('found_reliable_strategy')}`",
        f"- round_count: `{result.get('round_count')}`",
        "",
        "## Reliability Gate",
        "",
        "A strategy is marked reliable only when the wallet archive is research-ready, the wallet has validated effective factors, and followability approves wallet quality, latency, depth, and paper/live edge.",
        "",
    ]
    reliable = result.get("reliable_strategies", [])
    if reliable:
        lines.extend(["## Reliable Strategies", "", _strategy_table(reliable), ""])
    else:
        lines.extend(
            [
                "## Reliable Strategies",
                "",
                "No strategy passed the full reliability gate in this run.",
                "",
            ]
        )
    for round_result in result.get("rounds", []):
        lines.extend(
            [
                f"## Round {round_result.get('round')}",
                "",
                f"- scan_dir: `{round_result.get('scan_dir')}`",
                f"- recent_trade_rows: `{round_result.get('recent_trade_rows')}`",
                f"- candidates: `{round_result.get('candidate_count')}`",
                f"- research_ready: `{round_result.get('research_ready_count')}`",
                f"- reliable: `{round_result.get('reliable_count')}`",
                "",
                _strategy_table(round_result.get("strategies", [])),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _strategy_table(rows: list[dict]) -> str:
    lines = [
        "| Wallet | Status | Factors | Classification | Live Ready | Main Reason |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        reasons = row.get("reasons", [])
        reason = reasons[0] if reasons else "-"
        lines.append(
            "| {wallet} | {status} | {factors} | {classification} | {live} | {reason} |".format(
                wallet=row.get("account"),
                status=row.get("status"),
                factors=row.get("effective_factor_count", 0),
                classification=row.get("classification"),
                live=row.get("live_follow_ready"),
                reason=_escape(reason),
            )
        )
    return "\n".join(lines)


def _escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
