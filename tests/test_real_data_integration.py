"""Opt-in ingestion integration: genuine local data only, never HTTP or synthetic fallback."""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from gold_ai_trader.data.csv_io import load_csv, write_bundle
from gold_ai_trader.data.quality import inspect_bundle
from gold_ai_trader.data.schema import Provenance


@pytest.mark.integration
def test_real_one_hour_csv_ingestion_round_trip(tmp_path):
    configured = os.environ.get("GOLD_REAL_DATA_BUNDLE")
    if not configured:
        pytest.skip("GOLD_REAL_DATA_BUNDLE unset; genuine market data integration not executed")
    bundle = Path(configured)
    metadata = json.loads((bundle / "metadata.json").read_text())
    assert metadata["data_kind"] == "historical", "Synthetic bundles cannot run this integration"
    assert metadata["price_side"] == "bid_ask", "Both quote sides are required"
    assert "synthetic" not in (metadata["source"] + metadata["reference"]).lower()
    start_text = os.environ.get("GOLD_REAL_DATA_START", "2024-01-02T12:00:00Z")
    report = inspect_bundle(bundle, datetime.fromisoformat(start_text.replace("Z", "+00:00")))
    assert report["valid"], report
    assert report["actual_candles"] == 12
    source = Provenance(**report["provenance"])
    frame, digest = load_csv(bundle / "candles.csv", source)
    output = tmp_path / "real-round-trip"
    assert write_bundle(frame, source, output, source_sha256=digest).valid
    restored, _ = load_csv(output / "candles.csv", source)
    pd.testing.assert_frame_equal(frame, restored)
