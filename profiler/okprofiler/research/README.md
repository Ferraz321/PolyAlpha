# Researcher Layer

The researcher layer is an agent-style analyst over deterministic outputs.

It must not claim a strategy is real unless the data pipeline provides:

- profile-readiness passed
- enough wallet samples
- factor table rows aligned to CLOB snapshots
- a mined rule with non-trivial coverage
- stability across time splits

The current local researcher is deterministic. Per-wallet notes live in
`okprofiler/researcher.py`; the formal artifact-reading agent lives in
`okprofiler/agent.py` and is exposed through:

```bash
python profiler/profile_wallets.py agent --profile-dir data/profiler
```

The agent consumes only structured artifacts such as `rules.json`,
`diagnostics.json`, `factor_summary.md`, and market-category playbooks. It
proposes new experiments, writes `research_report.md`, and writes a structured
`candidate_factors.json` backlog.

With `--run-tools`, it also becomes a local orchestrator over both engines:

- Rust: `profile-readiness`, `export-profiler`, `validate-strategy-config`,
  and optional one-shot `watch-clob`.
- Python: remote user trade fetch, Gamma market metadata fetch, profiler run,
  CLOB asset extraction, and deterministic research planning.

The planner writes `next_commands.json` so a later agent loop can decide which
data source or factor family to add next.

Research matrix engines are coordinated by `okprofiler/research_matrix.py`:

- `core`: row counts, factor registry coverage, market/wallet breadth
- `alphalens`: lightweight IC-style evidence over forward price moves
- `shap`: model feature importance as a SHAP-compatible explanation bridge
- `stumpy`: lightweight motif search over OFI sequences
- `nautilus`: event-replay manifest for future NautilusTrader backtests
- `agent`: structured suggestions based only on engine outputs
