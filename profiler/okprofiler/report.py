from html import escape
from pathlib import Path


def write_reports(rules: dict, report_out: Path | None, html_out: Path | None) -> None:
    markdown = render_markdown(rules)
    if report_out is not None:
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(markdown, encoding="utf-8")
    if html_out is not None:
        html_out.parent.mkdir(parents=True, exist_ok=True)
        html_out.write_text(render_html(markdown), encoding="utf-8")


def render_markdown(rules: dict) -> str:
    wallets = sorted(
        rules.get("wallets", []),
        key=lambda row: row.get("explainability_score", 0.0),
        reverse=True,
    )
    lines = [
        "# OKTRADER Profiler Report",
        "",
        f"- rows: {rules.get('rows', 0)}",
        f"- wallets: {len(wallets)}",
        f"- approved_live_factors: {_approved_live_factor_count(rules)}",
        f"- wallet_clusters: {len(rules.get('wallet_clusters', []))}",
        "",
        "## Top Reverse-Engineering Candidates",
        "",
    ]
    if not wallets:
        lines.append("No wallets were profiled.")
        return "\n".join(lines) + "\n"
    for wallet in wallets[:20]:
        lines.extend(_wallet_section(wallet))
    return "\n".join(lines) + "\n"


def render_html(markdown: str) -> str:
    body = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            body.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            body.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            body.append(f"<p>{escape(line)}</p>")
        elif line:
            body.append(f"<p>{escape(line)}</p>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>OKTRADER Profiler Report</title>"
        "<style>body{font-family:system-ui;max-width:960px;margin:40px auto;"
        "line-height:1.55;color:#18202a}code{background:#f3f5f7;padding:2px 4px}"
        "p{margin:6px 0}h1,h2{margin-top:28px}</style></head><body>"
        + "\n".join(body)
        + "</body></html>\n"
    )


def _wallet_section(wallet: dict) -> list[str]:
    backtest = wallet.get("backtest", {})
    if wallet.get("status") == "small_sample":
        return [
            f"### {wallet.get('account')}",
            "",
            f"- status: small_sample ({wallet.get('samples', 0)} samples)",
            f"- next: {wallet.get('candidate_rule')}",
            "",
        ]
    return [
        f"### {wallet.get('account')}",
        "",
        f"- samples: {wallet.get('samples', 0)}",
        f"- explainability_score: {wallet.get('explainability_score', 0):.4f}",
        f"- rule: `{wallet.get('candidate_rule', '')}`",
        f"- factor_rule: {wallet.get('mining', {}).get('best_rule', {}).get('name', '')}",
        f"- live_rule: {wallet.get('mining', {}).get('best_live_rule', {}).get('name', '')}",
        f"- reproducibility_score: {backtest.get('reproducibility_score', 0):.4f}",
        f"- coverage: {backtest.get('coverage', 0):.2%}",
        f"- precision_proxy: {backtest.get('precision_proxy', 0):.2%}",
        f"- recall_proxy: {backtest.get('recall_proxy', 0):.2%}",
        f"- factor_stability: {backtest.get('factor_stability', 0):.2%}",
        f"- research_note: {wallet.get('agent_research_note', '')}",
        f"- market_categories: {_market_categories(wallet)}",
        f"- next_experiments: {', '.join(wallet.get('researcher', {}).get('next_experiments', []))}",
        "",
    ]


def _market_categories(wallet: dict) -> str:
    categories = wallet.get("market_categories", [])
    if not categories:
        return "none"
    return "; ".join(
        f"{category['label']} ({category['confidence']:.2%})"
        for category in categories
    )


def _approved_live_factor_count(rules: dict) -> int:
    return sum(
        1
        for validation in rules.get("factor_validations", [])
        if validation.get("verdict") == "approved" and validation.get("live_feature")
    )
