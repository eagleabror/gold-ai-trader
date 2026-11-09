"""Recheck a local bundle against an explicit small historical window.

Reports preserve the declared historical/synthetic classification. Hash checks
detect changed bytes, not authenticity. No download or session-calendar repair.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .csv_io import load_csv
from .dukascopy import validate_window
from .schema import Provenance, price_columns
from .validation import validate_candles


def inspect_bundle(bundle: Path, start: datetime, hours: int = 1) -> dict:
    start = validate_window(start, hours)
    metadata = json.loads((bundle / "metadata.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
        raise ValueError("Unsupported bundle metadata schema")
    required = ("source", "reference", "data_kind", "price_side", "symbol", "timeframe")
    if any(not isinstance(metadata.get(key), str) for key in required):
        raise ValueError("Bundle provenance fields must be present and strings")
    source = Provenance(**{key: metadata[key] for key in required})
    frame, digest = load_csv(bundle / "candles.csv", source)
    validation = validate_candles(frame, source)  # Strict even if original import allowed gaps.
    errors = []
    if metadata.get("candles_sha256") != digest:
        errors.append("candles_sha256 mismatch or missing hash")
    expected = pd.date_range(start, periods=hours * 12, freq="5min")
    stamps = frame.get("timestamp", pd.Series([], dtype="datetime64[ns, UTC]"))
    actual = pd.DatetimeIndex(stamps.dropna()).unique().sort_values()
    missing = expected.difference(actual)
    unexpected = actual.difference(expected)
    if len(missing) or len(unexpected) or len(frame) != len(expected):
        errors.append("Candles do not exactly cover the requested M5 window")
    gaps = []
    for previous, current in zip(actual[:-1], actual[1:], strict=True):
        if current - previous > pd.Timedelta(minutes=5):
            gaps.append(
                {
                    "previous_bar_utc": previous.isoformat(),
                    "next_bar_utc": current.isoformat(),
                    "missing_m5_bars": int((current - previous) / pd.Timedelta(minutes=5)) - 1,
                    "closure_classification": "unverified; review provider sessions and holidays",
                }
            )
    ranges = {}
    for column in price_columns(source.price_side):
        if column in frame:
            prices = pd.to_numeric(frame[column], errors="coerce")
            finite = prices[np.isfinite(prices)]
            ranges[column] = (
                None
                if finite.empty
                else {"minimum": float(finite.min()), "maximum": float(finite.max())}
            )
    # All rows must be valid before quoting even indicative bid/ask differences.
    differences = None
    if validation.valid and source.price_side == "bid_ask":
        differences = {}
        for field in ("open", "close"):
            spread = frame[f"ask_{field}"] - frame[f"bid_{field}"]
            differences[field] = {"minimum": float(spread.min()), "maximum": float(spread.max())}
    return {
        "report_schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "provenance": source.to_dict(),
        "authenticity": "source-declared; hashes do not independently authenticate market data",
        "requested_start_utc": start.isoformat(),
        "requested_end_exclusive_utc": (expected[-1] + pd.Timedelta(minutes=5)).isoformat(),
        "expected_m5_candles": len(expected),
        "actual_candles": len(frame),
        "missing_expected_bars": len(missing),
        "unexpected_bars": len(unexpected),
        "missing_bar_samples_utc": [stamp.isoformat() for stamp in missing[:12]],
        "candles_sha256": digest,
        "integrity_and_coverage_errors": errors,
        "validation": validation.to_dict(),
        "gap_count": len(gaps),
        "gap_samples": gaps[:20],
        "market_session_review": {
            "calendar_verified": False,
            "policy": "Gaps remain errors; no automatic weekend/holiday/daily-break exemptions",
            "note": "No gaps in one hour cannot establish completeness across market closures",
        },
        "price_ranges_usd_per_ounce": ranges,
        "quote_differences_usd": differences,
        "price_scale_verification": (
            "Requires independent source/decoder comparison; ranges alone are insufficient"
        ),
        "spread_limitation": "OHLC differences do not recover the intrabar executable spread path",
        "valid": validation.valid and not errors,
    }
