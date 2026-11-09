"""Synthetic BI5 streams and mocked HTTP only. No real market validation here."""

import lzma
import sys
from datetime import UTC, datetime

import pandas as pd
import pytest
import requests

from gold_ai_trader.data.dukascopy import (
    RECORD,
    DownloadError,
    decode_ticks,
    download_sample,
    fetch_hour,
    hour_url,
    validate_window,
)
from gold_ai_trader.data.validation import validate_candles

HOUR = datetime(2024, 1, 2, 12, tzinfo=UTC)


def synthetic_bi5(records=None):
    if records is None:
        records = [
            (i * 300_000, 2_000_500 + i * 1000, 2_000_000 + i * 1000, 1.0, 1.0) for i in range(12)
        ]
    return lzma.compress(b"".join(RECORD.pack(*record) for record in records))


def test_zero_based_month_and_symbol_fixed():
    assert hour_url(HOUR).endswith("/XAUUSD/2024/00/02/12h_ticks.bi5")


def test_synthetic_bid_ask_prices_scaling_and_all_ohlc():
    records = [
        (0, 2_000_500, 2_000_000, 1, 1),
        (1000, 2_002_500, 2_002_000, 1, 1),
        (2000, 1_999_500, 1_999_000, 1, 1),
        (299999, 2_001_500, 2_001_000, 1, 1),
        (300000, 2_003_500, 2_003_000, 1, 1),
    ]
    frame, _, _ = download_sample(HOUR, fetch=lambda _: synthetic_bi5(records))
    assert frame.loc[0, ["bid_open", "bid_high", "bid_low", "bid_close"]].tolist() == [
        2000,
        2002,
        1999,
        2001,
    ]
    assert frame.loc[0, "ask_close"] == 2001.5
    assert frame.loc[1, "bid_open"] == 2003
    assert frame.loc[1, "timestamp"] == pd.Timestamp("2024-01-02T12:05:00Z")


def test_full_window_and_source_manifest_are_preserved():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return synthetic_bi5()

    frame, source, acquisition = download_sample(HOUR, 2, fetch=fake_fetch)
    assert len(calls) == 2
    assert len(frame) == 24
    assert validate_candles(frame, source).valid
    assert len(acquisition["tick_files"]) == 2
    assert len(acquisition["tick_files"][0]["sha256"]) == 64
    # This provenance describes the production downloader. Input in this test is synthetic.
    assert source.price_side == "bid_ask"


def test_missing_bins_not_filled_and_boundary_coverage_enforced():
    frame, source, _ = download_sample(
        HOUR, fetch=lambda _: synthetic_bi5([(300000, 2000500, 2000000, 1, 1)])
    )
    assert len(frame) == 12
    assert frame.loc[0, "bid_open"] != frame.loc[0, "bid_open"]  # NaN
    assert not validate_candles(frame, source).valid


@pytest.mark.parametrize(
    "start,hours",
    [
        (datetime(2024, 1, 2, 12), 1),
        (HOUR.replace(minute=1), 1),
        (HOUR, 0),
        (HOUR, 7),
        (datetime(2099, 1, 1, tzinfo=UTC), 1),
    ],
)
def test_bad_windows_fail_before_fetch(start, hours):
    with pytest.raises(DownloadError):
        validate_window(start, hours)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"bad",
        lzma.compress(b""),
        lzma.compress(b"123"),
        synthetic_bi5()[:-2],
        synthetic_bi5() + b"trailing",
    ],
)
def test_corrupt_compression_or_record_length_rejected(payload):
    with pytest.raises(DownloadError):
        decode_ticks(payload, HOUR)


@pytest.mark.parametrize(
    "records",
    [
        [(3600000, 2000500, 2000000, 1, 1)],
        [(0, 1999000, 2000000, 1, 1)],
        [(0, 0, 0, 1, 1)],
        [(0, 2000500, 2000000, float("nan"), 1)],
        [(0, 2000500, 2000000, -1, 1)],
        [(10, 2000500, 2000000, 1, 1), (0, 2000500, 2000000, 1, 1)],
    ],
)
def test_invalid_tick_values_rejected(records):
    with pytest.raises(DownloadError):
        decode_ticks(synthetic_bi5(records), HOUR)


def test_size_limits(monkeypatch):
    import gold_ai_trader.data.dukascopy as module

    monkeypatch.setattr(module, "MAX_COMPRESSED_BYTES", 1)
    with pytest.raises(DownloadError, match="Compressed"):
        decode_ticks(synthetic_bi5(), HOUR)
    monkeypatch.setattr(module, "MAX_COMPRESSED_BYTES", 10000)
    monkeypatch.setattr(module, "MAX_DECOMPRESSED_BYTES", 1)
    with pytest.raises(DownloadError, match="Decompressed"):
        decode_ticks(synthetic_bi5(), HOUR)


class FakeResponse:
    def __init__(self, status, body):
        self.status_code, self.body = status, body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, chunk_size):
        yield self.body


@pytest.mark.parametrize(
    "status,body", [(403, b"denied"), (404, b""), (302, b"redirect"), (200, b"")]
)
def test_http_failures_and_empty_responses_fail_closed(monkeypatch, status, body):
    monkeypatch.setattr(requests, "get", lambda *a, **k: FakeResponse(status, body))
    with pytest.raises(DownloadError):
        fetch_hour(hour_url(HOUR))


def test_http_success_and_response_limit(monkeypatch):
    import gold_ai_trader.data.dukascopy as module

    def fake_get(url, **kwargs):
        assert kwargs == {"timeout": (10, 30), "stream": True, "allow_redirects": False}
        return FakeResponse(200, synthetic_bi5())

    monkeypatch.setattr(requests, "get", fake_get)
    assert fetch_hour(hour_url(HOUR)) == synthetic_bi5()
    monkeypatch.setattr(module, "MAX_COMPRESSED_BYTES", 1)
    with pytest.raises(DownloadError, match="size limit"):
        fetch_hour(hour_url(HOUR))


def test_network_error_is_clear_without_leaking_credentials(monkeypatch):
    def fail(*args, **kwargs):
        raise requests.ConnectionError("potentially sensitive proxy detail")

    monkeypatch.setattr(requests, "get", fail)
    with pytest.raises(DownloadError, match="ConnectionError") as error:
        fetch_hour(hour_url(HOUR))
    assert "sensitive" not in str(error.value)


def test_missing_optional_dependency_is_actionable(monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", None)
    with pytest.raises(DownloadError, match="optional dependencies"):
        fetch_hour(hour_url(HOUR))
