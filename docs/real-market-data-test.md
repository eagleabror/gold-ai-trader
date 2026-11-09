# Real market data test — FAIL

Date: 2026-11-09. Repository: `eagleabror/gold-ai-trader`.
Base: `phase-1-5-real-data-ci` at `9c7f6a0aa154c3738a10bdd88259a3d6d4797415`.
Test branch: `real-market-data-test`. The existing application and tests are
unchanged; this document records the actual acquisition failure and checks.

## Network permission verification

The owner reported adding `datafeed.dukascopy.com`. The attached executor is
`ccarenv_b64_Y2NhcmVudl9kZTA5NmQzODUxY2M4MTkxYTViYmQ3NGJhNzdhYTU2Mg`.
Its environment-status response still reported observed configuration revision
`1`, `observations_current: true`, enforced restricted networking, no custom
hosts, and no `datafeed.dukascopy.com` in its effective allowed hosts. The
startup `/etc/codex/network-policy.json` also had no Dukascopy rule.

The live proxy status endpoint was read, with the required execution approval,
to distinguish stale startup settings from applied policy. Observed at
`2026-11-09T14:20:47.735569+00:00`, its policy source was `runtime`, policy
revision `55e61168-a6d8-4024-b502-9b3c532a606d`, HTTP mode `allowlist` and
`allow_all_domains: false`. No visible allow rule matched Dukascopy. Some
domain patterns are omitted by that diagnostic endpoint, so visible-rule
absence alone is not treated as a complete policy proof. The fresh actual
request below establishes that this specific destination/path remains denied.

The reported configuration update therefore **has not established working
access in this executor**. No conclusion is drawn about a saved draft, reusable
environment template or another executor that was not inspected.

## Exact download attempt and error

The existing CLI was used, unchanged:

```bash
.venv/bin/gold-data download-dukascopy \
  --start 2024-01-02T12:00:00Z --hours 1 \
  --output data/real-xauusd-20240102-12
```

The sandbox attempt and the approved retry through the inherited Cloud proxy
both returned exit `2`:

```text
Data operation rejected: Dukascopy request failed (ProxyError): https://datafeed.dukascopy.com/datafeed/XAUUSD/2024/00/02/12h_ticks.bi5
```

A bounded curl diagnostic to that exact URL, with inherited proxy settings
and TLS verification enabled, returned exit `56`:

```text
curl: (56) CONNECT tunnel failed, response 403
HTTP 000
```

The proxy CONNECT response at `2026-11-09T14:20:49Z` was:

```text
HTTP/1.1 403 Forbidden
content-length: 16
content-type: text/plain
server: envoy
connection: close
```

`HTTP 000` is curl's lack of an origin HTTPS response; `403` is the proxy's
CONNECT response. The TLS tunnel was not established. This is not evidence
of a Dukascopy-origin HTTP rejection. No provider payload was acquired and
the output bundle directory was not created. No TLS disablement, relay,
alternate-host tunnel or network-policy bypass was used.

## Dataset and independent scale validation

| Requested / checked item | Actual result |
| --- | --- |
| Provider | Dukascopy public XAUUSD bid/ask tick archive, attempted only |
| Requested interval | 2024-01-02 12:00–13:00 UTC, end exclusive |
| Expected M5 bars | 12, with opens from 12:00 through 12:55 UTC |
| Genuine ticks obtained | 0 |
| Genuine M5 candles obtained | **0** |
| Bid/ask, OHLC, UTC, alignment | Not run on genuine data |
| Duplicates and gaps | Not run on genuine data |
| Tick/candle SHA-256 provenance | Not available; no provider/candle bytes |
| Independent gold-price scale verification | **Not run / not verified** |

The hardcoded divisor `1000` was neither changed nor accepted as independent
evidence. Without genuine bytes there are no decoded prices to compare with
another source or decoder. Synthetic BI5 tests, plausible price ranges and
the existing constant cannot satisfy independent scale validation.

After actual access is granted, obtain one completed hour, retain source-file
hashes and compare independently decoded bid/ask prices with provider evidence
that specifies the quote unit/precision. Then run the existing quality report
and genuine-data integration. Do not accept software-only CI as that evidence.
No market-closure observations can be inferred from an absent dataset.

## Quality CLI and opt-in integration: actual failures

```bash
.venv/bin/gold-data quality-report data/real-xauusd-20240102-12 \
  --start 2024-01-02T12:00:00Z --hours 1 \
  --output data/real-xauusd-20240102-12-quality.json
```

Exit `2`, with the exact operational error:

```text
Data operation rejected: [Errno 2] No such file or directory: 'data/real-xauusd-20240102-12/metadata.json'
```

The opt-in integration was explicitly invoked with the intended genuine
bundle path, rather than silently accepting its default skip:

```bash
GOLD_REAL_DATA_BUNDLE=data/real-xauusd-20240102-12 \
  GOLD_REAL_DATA_START=2024-01-02T12:00:00Z \
  .venv/bin/python -m pytest -q -m integration \
  --junitxml=test-results/real-market-integration.xml
```

Exit `1`: `1 failed, 75 deselected in 0.14s`. The failure was
`test_real_one_hour_csv_ingestion_round_trip`, a `FileNotFoundError` for the
same `metadata.json`. This reflects the failed acquisition prerequisite,
not a successful ingestion or evidence of invalid market prices.

An ignored, machine-readable acquisition-status report is saved locally at
`data/real-market-test-status.json`. Its genuine-data checks and hashes are
null (unmeasured), not passed. No real quality-report output was created.

## Regression and available CI

Local Python: 3.12.14. The normal suite, with no genuine bundle configured,
returned `75 passed, 1 skipped in 0.41s`. The single skip explicitly says the
genuine dataset environment variable is unset. `ruff check .` returned
`All checks passed!`; `ruff format --check .` reported `21 files already
formatted`; `pip check` reported `No broken requirements found.`

The original 65 tests and the Phase 1.5 quality/integration tests were not
changed. JUnit files stay under ignored `test-results/`. GitHub CI still runs
software-only checks on Python 3.11/3.12, with real-data integration skipped
unless a genuine local bundle is provided. New remote run results are checked
after this branch is pushed; a green CI cannot change the FAIL market verdict.

## Remaining blocker and scope

Apply the exact host permission to this task's active executor/proxy, then
confirm it with a fresh request. Saving an allowlist elsewhere does not prove
it applies here. If a fresh request is still denied after an applied-policy
change, retain that new status and CONNECT evidence for the Cloud environment
administrator. Repeated identical requests against the unchanged denial are
not a repair.

No raw prices, archives or dataset bundles are committed. No ML model, MQL5
EA, Telegram bot or trading server was built. Live trading remains disabled
and no broker credentials or orders were involved. **Overall verdict: FAIL**
because the requested genuine one-hour sample and independent scale check
could not be completed.
