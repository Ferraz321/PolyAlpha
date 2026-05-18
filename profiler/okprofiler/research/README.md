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
