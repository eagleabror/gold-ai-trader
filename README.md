# Gold AI Trader v1.0 — Phase 1.5

XAUUSD M5 historical data tooling for Python 3.11+. Phase 1.5 continues the accepted
Phase 1 **foundation and data pipeline only**. There is no ML model, signal service,
backtest, MT5 execution, Telegram bot or live server. No broker credentials are
required, and no orders can be submitted by this code.

## Run in Codex Cloud

Use the Linux terminal attached to this repository. An iPhone can review files,
run Cloud tasks and inspect GitHub Actions; a local computer, Windows, MT5 and a
VPS are unnecessary for Phase 1. Commands below assume the repository root.

```bash
cd /workspace/gold-ai-trader
python3 --version  # Must be >= 3.11
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,download]'
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

For a CSV-only installation use `pip install -e .` inside the virtual environment.
To reproduce the exact locally validated dependencies instead, use:

```bash
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
```

Phase 1 does not read `.env`; `.env.example` records the future safe default.
Never add secrets to source files or terminal command arguments.

## First small sample: explicitly SYNTHETIC

The committed three-row fixture contains invented prices for software checks.
**It is not historical XAUUSD data.** This offline command demonstrates the pipeline:

```bash
.venv/bin/gold-data import-csv tests/fixtures/synthetic_xauusd_m5.csv \
  --source 'SYNTHETIC software-test fixture' \
  --reference 'tests/fixtures/README.md' \
  --data-kind synthetic --price-side bid \
  --output data/synthetic-smoke
```

The output directory must be new. It contains `candles.csv` and `metadata.json`
with source information, input/output SHA-256, observed UTC coverage and the
validation report. A valid synthetic dataset is still labeled synthetic. That
label must never be removed to make market claims.

## Import genuine historical CSV

Place your own file at `data/raw/xauusd_m5.csv` (ignored by Git), then run:

```bash
.venv/bin/gold-data import-csv data/raw/xauusd_m5.csv \
  --source 'Actual provider name' \
  --reference 'Provider URL and export provenance; no secrets' \
  --data-kind historical --price-side bid \
  --output data/imported-xauusd-m5
```

Replace the provenance with truthful details and choose the actual quote side.
`historical` is the importer's declaration, not independent authentication.
Supported sides: `bid`, `ask`, `mid`, `unknown` or `bid_ask`. Single-side data
cannot prove executable spread; `unknown` is explicitly warned against for
cost modeling. Nothing infers quote side, instrument identity or time zone
from the price values. CSV must already be XAUUSD M5.

Single-side columns (exact lowercase names):

```text
timestamp,open,high,low,close
```

Separate bid/ask columns:

```text
timestamp,bid_open,bid_high,bid_low,bid_close,ask_open,ask_high,ask_low,ask_close
```

Timestamps are **bar-open** times with explicit offsets, for example
`2024-01-02T12:00:00Z` or `2024-01-02T15:00:00+03:00`. Offsets are converted
to UTC. Naive dates and numeric epochs are rejected; convert them upstream
using documented source time zone information. CSV uses UTF-8, commas and
decimal points. Additional columns (including volume) are rejected; adapt
provider exports explicitly before import. There is no automatic M1-to-M5
CSV conversion, sorting, deduplication or interpolation.

The validator checks empty/schema errors, UTC timestamps, chronological order,
five-minute alignment, duplicate bars, finite positive prices, OHLC bounds,
corresponding bid/ask bounds and intervals longer than five minutes. Any error
prevents writing a dataset. Coverage reports first/last observed bar opens;
CSV alone cannot prove completeness before or after those endpoints.

All time gaps fail by default. There is no verified exchange/broker session
calendar, so weekend closures, holidays and daily breaks are flagged too.
After reviewing a provider's calendar, an importer can explicitly use
`--allow-gaps` to preserve gaps as warnings. This neither fills data nor
certifies gaps as expected. Issue counts and at most ten zero-based source
row samples are retained. Exit codes: `0` valid (possibly warnings), `1`
validation failed, `2` file/download/argument-value operation failed;
argparse also exits `2` for invalid CLI syntax. Reports print to stdout;
operational errors print to stderr.

## Optional Dukascopy download: one hour by default

```bash
.venv/bin/gold-data download-dukascopy \
  --start 2024-01-02T12:00:00Z --hours 1 \
  --output data/dukascopy-20240102-12
```

This fixed XAUUSD source fetches 1–6 completed UTC hours of public BI5 ticks,
then independently aggregates bid/ask to left-closed, bar-open M5 candles.
No large downloads, retries, redirections, empty-hour skips or forward fills
are performed. Failed HTTP requests, corrupt records, missing bins or crossed
quotes reject the sample. The manifest records every source URL and payload
hash plus the requested interval. Raw compressed archives are not retained;
hashes allow comparison with a later re-download.

**Real-data acquisition status:** on 2026-11-09 the Cloud proxy rejected the archive
request with `CONNECT tunnel failed, response 403`. No genuine market sample
was downloaded, and no genuine market validation is claimed. CSV import is
ready, but this downloader's format and XAUUSD scale still require validation
against genuine provider data. All automated tests are synthetic or mocked.
See [Phase 1.5 evidence](docs/phase-1-5-validation.md) for the latest acquisition
and CI status, and [data source notes](docs/data-sources.md) for limitations.

If the environment owner permits `datafeed.dukascopy.com` in Codex Cloud
network settings, retry the one-hour command. Keep TLS verification enabled.
Otherwise import a genuine, documented local CSV. Do not substitute synthetic
prices for a failed real download.

## One-hour dataset quality and genuine-data integration

After a successful real download, run this offline check. The bundle must
exactly cover the requested twelve M5 bar opens, including both endpoints:

```bash
.venv/bin/gold-data quality-report data/dukascopy-20240102-12 \
  --start 2024-01-02T12:00:00Z --hours 1 \
  --output data/quality-20240102-12.json
GOLD_REAL_DATA_BUNDLE=data/dukascopy-20240102-12 \
  GOLD_REAL_DATA_START=2024-01-02T12:00:00Z \
  .venv/bin/python -m pytest -q -m integration
```

Reports include declared source/classification, SHA-256 integrity, expected vs
observed coverage, UTC/OHLC/duplicate checks, gap intervals, price ranges and
bid/ask open/close differences. They do not independently certify authenticity
or price scale. Compare the decoded quotes with independent provider evidence.
Gaps, including candidate weekend/holiday/daily breaks, are reviewed separately
and remain errors; no unverified closure is automatically exempted. See
[session review](docs/phase-1-5-validation.md#market-closures).

The integration test reads a local, declared-historical bid/ask bundle and
round-trips it through the CSV importer. It performs no network requests. It
fails for malformed/missing configured data and rejects declared synthetic
bundles. Without `GOLD_REAL_DATA_BUNDLE`, it explicitly skips; CI's skip must
not be reported as successful real-market validation. The original 65 tests
are unchanged. New quality-report unit tests also use synthetic fixtures only.

## Repository map and review

```text
.github/workflows/ci.yml   Free GitHub Actions: Python 3.11/3.12 tests and lint
data/README.md            Local-only datasets and provenance policy
src/__init__.py           Installed package: gold_ai_trader
src/data/schema.py        Explicit source and schema contract
src/data/csv_io.py        CSV read, hash and validated bundle persistence
src/data/validation.py    UTC, OHLC, duplicate and gap checks
src/data/dukascopy.py     Optional bounded BI5 acquisition and M5 aggregation
src/data/cli.py           gold-data CLI
src/data/quality.py       Offline bundle integrity and explicit-window quality report
src/features/             Reserved; no Phase 2 implementation
src/ml/                   Reserved
src/backtest/             Reserved
src/risk/                 Reserved
mt5/                      Reserved
telegram/                 Reserved
tests/                    Synthetic fixtures and automated tests
docs/                     Data, architecture, safety and verification notes
```

Setuptools maps `src/` to the installed `gold_ai_trader` package; install it
before running tests. Review the schema and validator first, then persistence,
downloader and their tests. Run the exact commands above, inspect the synthetic
bundle's metadata and check [verification evidence](docs/phase-1-validation.md).
On GitHub, inspect the commit's **Files changed** and the **Actions** tab;
local test results do not mean remote CI has run. The Phase 1 remote run has now
been verified: Python 3.11 and 3.12 each passed all 65 original tests. See the
Phase 1.5 evidence for subsequent run IDs and counts. CI performs no market downloads
and requires no secrets. It saves JUnit results for seven days and keeps both
matrix jobs running if either fails. Dependencies are pinned in `requirements-dev.lock`;
regenerate and review that file deliberately when upgrading.

## Safety and later phases

The intended broker is Exness Standard, symbol XAUUSD, timeframe M5, with a
$100 reference balance. Future risk constraints are 1% of current equity per
trade, a 3% daily trading cutoff and one concurrent position. They are recorded
requirements, not an implemented risk engine in Phase 1.

Live trading stays disabled by default. Future execution must require a Stop
Loss, reject excess risk and infeasible broker minimum lots, check spread,
margin and dynamic contract settings, and use MQL5 `OrderCalcProfit`. No
martingale, grid averaging or uncontrolled sizing. Missing/invalid signals
must fail closed. A daily cutoff cannot guarantee a maximum loss because of
gaps, slippage and execution conditions. Dukascopy quotes are not Exness fills.

No profit, backtest, model accuracy or trading performance is claimed. Phases
2–6 remain unimplemented and require the owner's separate approval.
