"""Quality-report code validation uses synthetic candles only."""

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from gold_ai_trader.data.cli import main
from gold_ai_trader.data.csv_io import write_bundle
from gold_ai_trader.data.quality import inspect_bundle
from gold_ai_trader.data.schema import Provenance

START = datetime(2024, 1, 2, 12, tzinfo=UTC)


@pytest.fixture
def synthetic_full_bundle(tmp_path, synthetic_candles, synthetic_provenance):
    frame = pd.concat([synthetic_candles] * 4, ignore_index=True)
    frame["timestamp"] = pd.date_range(START, periods=12, freq="5min")
    bundle = tmp_path / "synthetic-bundle"
    assert write_bundle(frame, synthetic_provenance, bundle).valid
    return bundle


def test_complete_synthetic_bundle_is_never_market_evidence(synthetic_full_bundle):
    report = inspect_bundle(synthetic_full_bundle, START)
    assert report["valid"]
    assert report["actual_candles"] == report["expected_m5_candles"] == 12
    assert report["provenance"]["data_kind"] == "synthetic"
    assert report["gap_count"] == report["missing_expected_bars"] == 0
    assert report["price_ranges_usd_per_ounce"]["open"]["minimum"] == 2000
    assert report["quote_differences_usd"] is None
    assert not report["market_session_review"]["calendar_verified"]


def test_incomplete_endpoints_detected_without_internal_gaps(
    tmp_path, synthetic_candles, synthetic_provenance
):
    bundle = tmp_path / "bundle"
    assert write_bundle(synthetic_candles, synthetic_provenance, bundle).valid
    report = inspect_bundle(bundle, START)
    assert not report["valid"]
    assert report["missing_expected_bars"] == 9
    assert report["gap_count"] == 0


def test_changed_csv_hash_and_missing_bar_both_detected(synthetic_full_bundle):
    csv = synthetic_full_bundle / "candles.csv"
    lines = csv.read_text().splitlines()
    del lines[5]
    csv.write_text("\n".join(lines) + "\n")
    report = inspect_bundle(synthetic_full_bundle, START)
    assert not report["valid"]
    assert report["missing_expected_bars"] == report["gap_count"] == 1
    assert "sha256" in report["integrity_and_coverage_errors"][0]
    assert report["gap_samples"][0]["missing_m5_bars"] == 1
    assert "unverified" in report["gap_samples"][0]["closure_classification"]


def test_incorrect_window_rejected(synthetic_full_bundle):
    report = inspect_bundle(synthetic_full_bundle, START.replace(hour=13))
    assert not report["valid"]
    assert report["unexpected_bars"] == report["missing_expected_bars"] == 12


@pytest.mark.parametrize("metadata", [{}, [], {"schema_version": 1, "source": 42}])
def test_bad_metadata_rejected(synthetic_full_bundle, metadata):
    (synthetic_full_bundle / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        inspect_bundle(synthetic_full_bundle, START)


def test_cli_report_persistence_and_no_overwrite(synthetic_full_bundle, tmp_path, capsys):
    output = tmp_path / "report.json"
    args = [
        "quality-report",
        str(synthetic_full_bundle),
        "--start",
        START.isoformat(),
        "--output",
        str(output),
    ]
    assert main(args) == 0
    assert json.loads(output.read_text())["valid"]
    assert main(args) == 2
    assert "already exists" in capsys.readouterr().err


def test_synthetic_bid_ask_differences_are_reported(tmp_path, synthetic_candles):
    base = pd.concat([synthetic_candles] * 4, ignore_index=True)
    base["timestamp"] = pd.date_range(START, periods=12, freq="5min")
    prices = base.drop(columns="timestamp")
    frame = pd.concat(
        [base[["timestamp"]], prices.add_prefix("bid_"), (prices + 0.5).add_prefix("ask_")], axis=1
    )
    source = Provenance("SYNTHETIC", "test", "synthetic", "bid_ask")
    bundle = tmp_path / "both"
    assert write_bundle(frame, source, bundle).valid
    report = inspect_bundle(bundle, START)
    assert report["valid"]
    assert report["quote_differences_usd"]["open"] == {"minimum": 0.5, "maximum": 0.5}


def test_weekend_gap_is_reviewed_separately_never_auto_exempted(
    tmp_path, synthetic_candles, synthetic_provenance
):
    frame = synthetic_candles.iloc[:2].copy()
    frame["timestamp"] = pd.to_datetime(["2024-01-05T21:55:00Z", "2024-01-07T23:00:00Z"])
    bundle = tmp_path / "weekend"
    assert write_bundle(frame, synthetic_provenance, bundle, allow_gaps=True).valid
    report = inspect_bundle(bundle, datetime(2024, 1, 5, 21, tzinfo=UTC))
    assert not report["valid"]
    assert report["gap_count"] == 1
    assert "unverified" in report["gap_samples"][0]["closure_classification"]
    assert any(
        issue["code"] == "time_gaps" and issue["severity"] == "error"
        for issue in report["validation"]["issues"]
    )
