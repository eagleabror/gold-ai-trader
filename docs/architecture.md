# Phase boundaries

Phase 1: local data ingestion and validation only. The installed Python package
is `gold_ai_trader`, sourced from `src/`. Only `gold_ai_trader.data` is implemented.

Flow: explicit source declaration → CSV or bounded tick acquisition → UTC
candles → strict validation → new local CSV/metadata bundle. Invalid data is
not persisted. Source files are not modified. Results retain warnings and
source hashes. Output directories are never intentionally overwritten.

Reserved directories are placeholders. Later phases: 2 (features and Random
Forest baseline), 3 (chronological/walk-forward backtesting and risk simulation),
4 (MQL5 execution), 5 (owner-only Telegram control), 6 (demo integration).
None is implemented in Phase 1. There is no FastAPI service or deployment.

Future risk policy: 1% equity, 3% daily cutoff, one position; mandatory SL;
dynamic Exness contract/margin/spread checks; reject broker minimum lots when
they exceed permissible risk; MQL5 OrderCalcProfit. A daily cutoff cannot cap
realized loss reliably. Execution must fail closed, with no martingale or grid.
No setting in `.env.example` enables execution in this repository.
