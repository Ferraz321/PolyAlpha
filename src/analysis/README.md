# Analysis Modules

This directory holds the wallet-research core:

- `metrics.rs`: deterministic account feature vectors and closed-loop PnL.
- `filter.rs`: strict funnel checks.
- `tagging.rs`: rule/profile-based account classification.
- `profile_config.rs`: configurable strategy profile loader.
- `microstructure.rs`: wallet fills to CLOB-state joins.
- `clob_features.rs`: CLOB payload feature extraction.

The crate root re-exports these modules to keep CLI and storage boundaries stable.
