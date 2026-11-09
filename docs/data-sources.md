# Data sources and limitations

## CSV

Local CSV is the offline fallback. Source name, reference, quote side and
historical/synthetic classification are mandatory declarations. The SHA-256
fingerprint identifies bytes, not truth, provider authenticity or market
completeness. The importer cannot establish the instrument from prices alone.
Only observed coverage is known; source session calendars need manual review.
Unknown or single-side quotes are unsuitable for measuring actual bid/ask costs.

## Optional Dukascopy public archive

Endpoint example (January is month `00`):

`https://datafeed.dukascopy.com/datafeed/XAUUSD/2024/00/02/12h_ticks.bi5`

The implementation assumes an LZMA-compressed sequence of big-endian `>3I2f`
records: milliseconds within UTC hour, integer ask, integer bid, ask volume,
bid volume. XAUUSD prices are divided by **1000**, a provider convention that
must be verified with genuine data before research use. This constant is not
an assumed MT5 tick size, lot size or broker contract specification.

Each hourly payload is capped at 8 MiB compressed and 32 MiB decompressed;
the decoder's LZMA memory cap is 64 MiB. Hour ranges are capped at six. Requests
use TLS verification and inherited proxies, 10-second connection and 30-second
read timeouts; these are per-operation timeouts, not a guaranteed total deadline.
HTTP errors, empty responses and redirects fail without silently moving on.
No archive request runs in tests or CI.

Bid/ask candles are aggregated independently. OHLC extrema are not synchronized
ticks; subtracting ask and bid highs/lows does not recover the executable spread
at an arbitrary instant. Tick volumes are checked but discarded. No real
exchange volume, commission, slippage or Exness execution costs are inferred.
Missing five-minute bins remain NaN and cause rejection. Complete hourly
coverage is required, including the first and last requested M5 bin. A bin
having one tick is not proof the provider delivered every tick within it.

On 2026-11-09 a one-hour archive request was blocked at the Cloud proxy:
`curl` exit 56, `CONNECT tunnel failed, response 403`. The enforced allowlist
does not include `datafeed.dukascopy.com`. No real bytes were obtained. Format,
scale and genuine data quality validation are **pending**; synthetic BI5 tests
only verify the implementation of the stated assumptions. Never treat those
tests as independent confirmation of the archive format.

Phase 1.5 adds an offline `gold-data quality-report` command and an opt-in
local real-data ingestion test. See [Phase 1.5 evidence](phase-1-5-validation.md)
for the current blocker and reviewed fallback sources. No data is committed.

After access is available: download one completed trading hour, inspect the
manifest, compare decoded price scale and UTC timestamps with an independent
provider view, check both quote sides and gaps, and record actual results here.
Provider quotes can differ from Exness Standard XAUUSD symbol/session settings.
