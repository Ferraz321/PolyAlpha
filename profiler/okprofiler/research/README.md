# Researcher Layer

The researcher layer is an agent-style analyst over deterministic outputs.

It must not claim a strategy is real unless the data pipeline provides:

- profile-readiness passed
- enough wallet samples
- factor table rows aligned to CLOB snapshots
- a mined rule with non-trivial coverage
- stability across time splits

The current local researcher is deterministic and lives in
`okprofiler/researcher.py`. A future LLM agent should consume only structured
artifacts such as `rules.json`, `factor_table.parquet` summaries, and
`report.md`; it should propose new experiments, not invent evidence.

Research matrix engines are coordinated by `okprofiler/research_matrix.py`:

- `core`: row counts, factor registry coverage, market/wallet breadth
- `alphalens`: lightweight IC-style evidence over forward price moves
- `shap`: model feature importance as a SHAP-compatible explanation bridge
- `stumpy`: lightweight motif search over OFI sequences
- `nautilus`: event-replay manifest for future NautilusTrader backtests
- `agent`: structured suggestions based only on engine outputs
