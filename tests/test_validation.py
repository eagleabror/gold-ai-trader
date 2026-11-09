"""Code validation with synthetic prices only."""

import numpy as np
import pandas as pd
import pytest

from gold_ai_trader.data.schema import Provenance
from gold_ai_trader.data.validation import normalize_timestamps, validate_candles


def codes(report):
    return {issue.code for issue in report.issues}


def test_valid_synthetic_data_is_explicitly_marked(synthetic_candles, synthetic_provenance):
    report = validate_candles(synthetic_candles, synthetic_provenance)
    assert report.valid
    assert report.coverage_start_utc == "2024-01-02T12:00:00+00:00"
    assert report.coverage_end_utc == "2024-01-02T12:10:00+00:00"
    assert {"synthetic_data", "spread_unavailable"} <= codes(report)


def test_offsets_normalized_but_naive_invalid_numeric_rejected():
    stamps = normalize_timestamps(
        pd.Series(
            [
                "2024-01-02T15:00:00+03:00",
                "2024-01-02T12:00:00Z",
                "2024-01-02 12:00:00",
                "invalid",
                "",
                1704196800,
                "9999-01-01T00:00:00Z",
            ]
        )
    )
    assert stamps[0] == stamps[1]
    assert stamps[2:].isna().all()
    assert str(stamps.dt.tz) == "UTC"


@pytest.mark.parametrize("value", [None, "broken", np.nan, np.inf, -np.inf, 0, -1])
def test_invalid_prices_rejected(synthetic_candles, synthetic_provenance, value):
    frame = synthetic_candles.astype({"open": object})
    frame.loc[1, "open"] = value
    report = validate_candles(frame, synthetic_provenance)
    assert not report.valid
    assert "invalid_prices" in codes(report)


@pytest.mark.parametrize("column,value", [("high", 1990), ("low", 2010), ("close", 2010)])
def test_ohlc_bounds_rejected(synthetic_candles, synthetic_provenance, column, value):
    synthetic_candles.loc[0, column] = value
    assert "ohlc_inconsistent" in codes(validate_candles(synthetic_candles, synthetic_provenance))


def test_duplicates_disorder_and_m5_alignment(synthetic_candles, synthetic_provenance):
    frame = synthetic_candles.copy()
    frame.loc[1, "timestamp"] = frame.loc[0, "timestamp"]
    assert "duplicate_candles" in codes(validate_candles(frame, synthetic_provenance))
    frame = synthetic_candles.iloc[::-1]
    assert "unordered_candles" in codes(validate_candles(frame, synthetic_provenance))
    frame = synthetic_candles.copy()
    frame.loc[1, "timestamp"] += pd.Timedelta(seconds=1)
    assert "m5_alignment" in codes(validate_candles(frame, synthetic_provenance))


def test_gaps_rejected_unless_explicitly_retained_for_review(
    synthetic_candles, synthetic_provenance
):
    frame = synthetic_candles.iloc[[0, 2]]
    assert not validate_candles(frame, synthetic_provenance).valid
    report = validate_candles(frame, synthetic_provenance, allow_gaps=True)
    assert report.valid
    assert next(issue for issue in report.issues if issue.code == "time_gaps").severity == "warning"
    assert len(frame) == 2  # No resampling or filling by validation.


def test_gap_row_samples_refer_to_original_positions(synthetic_candles, synthetic_provenance):
    frame = synthetic_candles.iloc[[2, 0]]
    frame.index = [7, 7]  # Labels must not affect diagnostics.
    report = validate_candles(frame, synthetic_provenance, allow_gaps=True)
    gap = next(issue for issue in report.issues if issue.code == "time_gaps")
    assert gap.row_samples == [0]


def test_duplicate_dataframe_columns_rejected(synthetic_candles, synthetic_provenance):
    frame = pd.concat([synthetic_candles, synthetic_candles[["open"]]], axis=1)
    report = validate_candles(frame, synthetic_provenance)
    assert not report.valid
    assert "duplicate_columns" in codes(report)


def test_unknown_quote_side_remains_explicit(synthetic_candles):
    source = Provenance("SYNTHETIC", "test", "synthetic", "unknown")
    assert "unknown_price_side" in codes(validate_candles(synthetic_candles, source))


def test_missing_timestamp_and_wrong_timezone(synthetic_candles, synthetic_provenance):
    frame = synthetic_candles.copy()
    frame.loc[1, "timestamp"] = pd.NaT
    assert "invalid_timestamp" in codes(validate_candles(frame, synthetic_provenance))
    frame["timestamp"] = frame.timestamp.dt.tz_convert("Europe/London")
    assert "timestamp_timezone" in codes(validate_candles(frame, synthetic_provenance))


def test_empty_missing_and_unexpected_columns(synthetic_candles, synthetic_provenance):
    assert not validate_candles(synthetic_candles.iloc[:0], synthetic_provenance).valid
    assert not validate_candles(synthetic_candles.drop(columns="close"), synthetic_provenance).valid
    assert not validate_candles(synthetic_candles.assign(volume=1), synthetic_provenance).valid


def test_bid_ask_schema_and_crossed_prices(synthetic_candles):
    frame = synthetic_candles.drop(columns="timestamp")
    combined = pd.concat(
        [
            synthetic_candles[["timestamp"]],
            frame.add_prefix("bid_"),
            (frame + 0.5).add_prefix("ask_"),
        ],
        axis=1,
    )
    source = Provenance("SYNTHETIC", "test", "synthetic", "bid_ask")
    assert validate_candles(combined, source).valid
    combined.loc[0, "ask_open"] = combined.loc[0, "bid_open"] - 0.1
    assert "crossed_quotes" in codes(validate_candles(combined, source))
    assert not validate_candles(combined.drop(columns="ask_close"), source).valid


@pytest.mark.parametrize(
    "kwargs",
    [
        {"source": " "},
        {"reference": ""},
        {"data_kind": "fake"},
        {"price_side": "last"},
        {"symbol": "EURUSD"},
        {"timeframe": "H1"},
    ],
)
def test_invalid_provenance_rejected(kwargs):
    values = dict(source="SYNTHETIC", reference="test", data_kind="synthetic", price_side="bid")
    with pytest.raises(ValueError):
        Provenance(**(values | kwargs))
