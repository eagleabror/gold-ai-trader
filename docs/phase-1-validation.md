# Phase 1 verification evidence

Date: 2026-11-09. Environment: Codex Cloud Linux, Python **3.12.14**.
This report describes real command results, not trading performance.

Later verification: Phase 1.5 retrieved the original GitHub Actions logs and
confirmed run `42583736096` succeeded: Python 3.11.18 had `65 passed in 0.32s`,
and Python 3.12.16 had `65 passed in 0.56s`. The remaining text records what was
known at the original Phase 1 handoff; see [Phase 1.5 evidence](phase-1-5-validation.md).

## Completed checks

```text
.venv/bin/python -m pytest -q
65 passed in 0.45s

.venv/bin/ruff check .
All checks passed!

.venv/bin/ruff format --check .
16 files already formatted

.venv/bin/python -m pip check
No broken requirements found.
```

The final dependency set is pinned in `requirements-dev.lock`. Python 3.11 is
configured in GitHub CI but was not run locally; installed dependency metadata
was checked for declared Python 3.11 compatibility. The first dependency
resolution selected NumPy 2.5.4, which lacks Python 3.11 support and produced
deprecation warnings with pandas. It was replaced with NumPy 2.3.5 before the
final passing test run. Initial Ruff formatting issues were also corrected.

The README synthetic import command was executed with a new
`data/synthetic-smoke` directory. Exit code: `0`; rows: `3`; classification:
`synthetic`; observed artificial bar opens: `2024-01-02T12:00:00Z` through
`2024-01-02T12:10:00Z`. The report correctly includes `synthetic_data` and
`spread_unavailable` warnings. Both output files are ignored by Git. Editable
installation using `--no-deps --no-build-isolation` also succeeded.

## Test scope

All price data and compressed BI5 records used in pytest are **synthetic**.
HTTP responses are mocked; an autouse fixture forbids accidental real HTTP
requests. Checks cover UTC/offset handling, missing/invalid timestamps,
empty/malformed CSV, schema and duplicate headers, nonpositive/nonfinite prices,
OHLC, order, duplicate candles, M5 alignment, gaps, bid/ask preservation,
crossed quotes, hash/metadata output, non-overwrite and partial-write cleanup,
BI5 scaling/aggregation, bin boundaries, missing-window coverage, malformed
compression/ticks, download size limits, HTTP/network failures, missing optional
dependencies and CLI failures. Passing tests are evidence of code behavior only.

## Real-data blocker

A single historical hour was requested at:

`https://datafeed.dukascopy.com/datafeed/XAUUSD/2024/00/02/12h_ticks.bi5`

The initial sandbox request could not connect to the inherited proxy (curl exit
`7`). A permitted retry outside that sandbox reached the Cloud proxy but was
denied with `CONNECT tunnel failed, response 403` (curl exit `56`). The enforced
network allowlist does not include this host. No real market bytes were
downloaded. Genuine data validation, archive format and XAUUSD scaling
confirmation remain pending. CSV import is implemented and independently tested.

## Repository and phase status

Pre-existing, uncommitted working files were preserved outside this repository
at `/workspace/gold-ai-trader-preexisting-20261109`; no previous application
code was reused. The attached Git repository had no commits or remote heads
when inspected. Only Phase 1 files belong to this implementation.

GitHub Actions is configured for Python 3.11 and 3.12. This report does not
claim a remote Actions run has completed; check the repository's Actions tab
for remote results after push. No broker account, trading orders, ML training,
backtest or performance claims were involved. Phase 2 awaits owner approval.
