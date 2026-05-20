def render_factor_discovery(result: dict, top: int = 20) -> str:
    if "boards" in result:
        return _render_board_discovery(result, top)
    summary = ", ".join(
        f"{key}={value}" for key, value in sorted(result.get("summary", {}).items())
    )
    lines = [
        "# Factor Discovery Report",
        "",
        f"- source_factor_table: {result.get('source_factor_table') or '-'}",
        f"- category: {result.get('category') or 'all'}",
        f"- rows: {result.get('rows', 0)}",
        f"- registered_candidates: {result.get('registered_candidates', 0)}",
        f"- synthetic_candidates: {result.get('synthetic_candidates', 0)}",
        f"- summary: {summary or '-'}",
        "",
    ]
    lines.extend(_render_section("Confirmed Effective", result.get("confirmed_effective", []), top))
    lines.extend(_render_section("Confirmed Promising", result.get("confirmed_promising", []), top))
    return "\n".join(lines) + "\n"


def _render_board_discovery(result: dict, top: int) -> str:
    summary = ", ".join(
        f"{key}={value}" for key, value in sorted(result.get("summary", {}).items())
    )
    lines = [
        "# Multi-Board Factor Discovery Report",
        "",
        f"- source_factor_table: {result.get('source_factor_table') or '-'}",
        f"- board_count: {result.get('board_count', 0)}",
        f"- rows: {result.get('rows', 0)}",
        f"- summary: {summary or '-'}",
        "",
        "| Board | Effective | Promising | Rejected | Top Effective Factor |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for board in result.get("boards", []):
        board_summary = board.get("summary", {})
        top_effective = "-"
        if board.get("confirmed_effective"):
            top_effective = f"`{board['confirmed_effective'][0]['factor_id']}`"
        lines.append(
            "| {category} | {effective} | {promising} | {rejected} | {top} |".format(
                category=board.get("category") or "all",
                effective=board_summary.get("confirmed_effective", 0),
                promising=board_summary.get("confirmed_promising", 0),
                rejected=board_summary.get("confirmed_rejected", 0),
                top=top_effective,
            )
        )
    lines.append("")
    for board in result.get("boards", []):
        lines.append(f"## Board: {board.get('category') or 'all'}")
        lines.append("")
        lines.extend(_render_section("Confirmed Effective", board.get("confirmed_effective", []), top))
    return "\n".join(lines) + "\n"


def _render_section(title: str, rows: list[dict], top: int) -> list[str]:
    lines = [f"## {title}", ""]
    if not rows:
        lines.extend(["No factors met this bar.", ""])
        return lines
    lines.extend(
        [
            "| Factor | Category | Approved | OOS | Replication | Stability | Formula |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rows[:top]:
        lines.append(
            "| `{factor_id}` | {category} | {approved_cycles}/{total_cycles} | {oos:.4f} | "
            "{replication:.4f} | {stability:.4f} | {formula} |".format(
                factor_id=row["factor_id"],
                category=row["category"],
                approved_cycles=row["approved_cycles"],
                total_cycles=row["total_cycles"],
                oos=row["out_of_sample_score"],
                replication=row["replication_score"],
                stability=row["stability_score"],
                formula=_escape_table(row["formula"]),
            )
        )
    lines.append("")
    return lines


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
