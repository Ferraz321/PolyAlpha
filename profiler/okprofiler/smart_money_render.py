def render_smart_money_archive(result: dict) -> str:
    lines = [
        "# Smart Money Archive",
        "",
        f"- scanned_at: {result.get('scanned_at')}",
        f"- recent_trade_rows: {result.get('recent_trade_rows', 0)}",
        f"- candidate_count: {result.get('candidate_count', 0)}",
        f"- archived_wallet_count: {result.get('archived_wallet_count', 0)}",
        f"- research_ready_count: {result.get('research_ready_count', 0)}",
        "",
        "| Wallet | Status | Score | Tag | Trades | Closed | PnL | Win Rate | Effective Factors |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for wallet in result.get("wallets", []):
        history = wallet.get("history_metrics", {})
        lines.append(
            "| `{wallet}` | {status} | {score:.4f} | {tag} | {trades} | {closed} | {pnl:.2f} | "
            "{win_rate:.2%} | {effective} |".format(
                wallet=wallet["account"],
                status=wallet["archive_status"],
                score=wallet.get("smart_money_score", 0.0),
                tag=wallet.get("classification", "unknown"),
                trades=history.get("trade_count", 0),
                closed=history.get("closed_markets", 0),
                pnl=history.get("total_pnl", 0.0),
                win_rate=history.get("win_rate", 0.0),
                effective=wallet.get("effective_factor_count", 0),
            )
        )
    return "\n".join(lines) + "\n"
