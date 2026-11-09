# Phase 1.5 — real-data and CI verification

Date: 2026-11-09. This phase continues commit `48ed526` without replacing
the existing project. Branch: `phase-1-5-real-data-ci`. No trading, ML or bot code.

## GitHub Actions evidence

The GitHub connector can read Actions even though shell access to
`api.github.com` is blocked by the Cloud network policy. No credential or TLS
workaround was used. This resolves the previous inability to inspect remote CI.

Original run: [42583736096](https://github.com/eagleabror/gold-ai-trader/actions/runs/42583736096),
commit `48ed526f1f1f81aa920c0695f4a95dd09b1bb247`, event `push`, conclusion
**success**, completed `2026-11-09T08:08:22Z`. Both job steps and full job logs
were retrieved through the GitHub connector:

| Job | Actual interpreter | Pytest result | Lint / format |
| --- | --- | --- | --- |
| `129048401366` | CPython 3.11.18 | `65 passed in 0.32s` | success / success |
| `129048400956` | CPython 3.12.16 | `65 passed in 0.56s` | success / success |

No original CI failure was found. The workflow retains both Python versions
and read-only repository permissions. Phase 1.5 adds `pip check`, disables
matrix fail-fast, and saves JUnit-only artifacts for seven days. No price data
or model artifacts are uploaded. The opt-in genuine-data test skips in CI
because no dataset is supplied; that skip is not real-data validation.

The new branch's run will be recorded here after push and actual inspection.

## Local regression and quality tooling

Local interpreter: Python 3.12.14. Original regression suite: `65 passed in 0.40s`.
After adding quality checks:

```text
python -m pytest -q --junitxml=test-results/pytest.xml
75 passed, 1 skipped in 0.58s

ruff check .
All checks passed!

ruff format --check .
20 files already formatted
```

The skip is explicit: `GOLD_REAL_DATA_BUNDLE unset; genuine market data
integration not executed`. All ten new quality-report unit cases use synthetic
fixtures. The original 65 tests were not changed or removed. See README for
`gold-data quality-report` and the real-data integration invocation.

## Acquisition and dataset quality status

The attempted primary source is Dukascopy's public XAUUSD tick archive:

`https://datafeed.dukascopy.com/datafeed/XAUUSD/2024/00/02/12h_ticks.bi5`

Target sample: `2024-01-02T12:00:00Z` to `2024-01-02T13:00:00Z` exclusive,
12 M5 candles with separate bid and ask. The Phase 1.5 retry reached the Cloud
proxy and failed with curl exit `56`, `CONNECT tunnel failed, response 403`.
The CONNECT response was `HTTP/1.1 403 Forbidden`, server `envoy`; no origin
HTTPS response or archive bytes were received. This is a pre-TLS-tunnel Cloud
egress denial, not evidence that Dukascopy rejected the request. The enforced,
current environment policy has no custom hosts and does not allow this host.
The owner was asked to add the domain in Cloud settings. An intention to add it
does not establish that the policy is applied; readiness must be rechecked.

| Quality item | Actual status before successful acquisition |
| --- | --- |
| Genuine dataset available | No |
| Genuine M5 candles acquired | 0 |
| Provider bytes / source hash | Not available |
| UTC / M5 alignment | Not measured on genuine data |
| OHLC / duplicate bars / missing prices | Not measured on genuine data |
| Gaps / full one-hour coverage | Not measured on genuine data |
| Bid/ask and crossed quotes | Not measured on genuine data |
| XAUUSD integer scale = 1000 | Implementation assumption; genuine validation pending |
| Real-data CSV ingestion integration | Skipped, not passed |

No synthetic values are substituted for missing observations. `quality-report`
can inspect a future local bundle, compare its CSV hash, enforce the expected
window, list gaps separately, and report price ranges and indicative quote
differences. Neither the range nor the hash proves authentic market data or
correct scale. Downloaded BI5 payloads should be checked against another
provider view or independent decoder before accepting scale as verified.

## Market closures

Reviewed [Dukascopy's published trading-hours page](https://www.dukascopy.com/swiss/english/forex/forex-trading-accounts/link/)
on 2026-11-09. It lists an XAU/USD daily break at 21:00–22:00 GMT in summer
and 22:00–23:00 GMT in winter, and separately notes US holiday restrictions.
It describes a Sunday-to-Friday trading week. The selected Tuesday 12:00 UTC
hour avoids those daily-break hours, but this current page is not a verified
historical holiday calendar for 2024 or an Exness contract specification.

Weekend, daily-break, DST and holiday omissions therefore require separate
source/date review. Quality checks never exempt them automatically, and
strictly reject gaps even if an earlier CSV import used `--allow-gaps`.
A synthetic weekend test verifies that policy without claiming any actual
market-session observation. No genuine sample currently exists to assess gaps.

## Free fallback-source review

- [dukascopy-node XAUUSD](https://www.dukascopy-node.app/instrument/xauusd)
  documents UTC tick and M5 bid/ask downloads, but uses Dukascopy underneath;
  a different client does not solve a blocked source domain.
- [Market-Data-Lab](https://github.com/kevingtlin/Market-Data-Lab/blob/main/XAUUSD_DUKASCOPY_M1_BID_ASK_README.md)
  declares Dukascopy M1 bid/ask exports with UTC millisecond timestamps.
  Its accessible Git tree did not contain CSV/BI5 price files, so it supplied
  provenance documentation only, not an acquired dataset.
- [EV Trading Labs](https://evtradelabs.com/data) advertises free archived
  XAUUSD M5 data aggregated from Dukascopy, with bid/ask. This is a third-party
  redistribution, not independently verified primary data; its domain is
  also absent from the current Cloud allowlist. No download, account creation,
  annual archive fetch or genuine-data result is claimed from it.

The supported route remains authorizing the primary domain, downloading only
one completed hour with TLS validation intact, then running the documented
quality and ingestion checks. No proxy relay, alternate-host tunnel, TLS
disablement or network-policy bypass was attempted. Dataset files stay under
ignored `data/`; reports of measured results may be documented separately.

Phase 2 and live trading remain unimplemented. Owner approval is required
after this phase's final handoff.
