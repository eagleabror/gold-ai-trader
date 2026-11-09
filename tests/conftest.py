"""Every fixture is synthetic; none represents historical market observations."""

from pathlib import Path

import pandas as pd
import pytest

from gold_ai_trader.data.schema import Provenance


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    """An accidental HTTP request must fail; downloader tests replace requests.get."""
    import requests

    def reject(*args, **kwargs):
        raise AssertionError("Tests must not access real HTTP sources")

    monkeypatch.setattr(requests.sessions.Session, "request", reject)


@pytest.fixture
def synthetic_provenance() -> Provenance:
    return Provenance("SYNTHETIC unit-test generator", "tests/conftest.py", "synthetic", "bid")


@pytest.fixture
def synthetic_candles() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-02T12:00:00Z", periods=3, freq="5min"),
            "open": [2000.0, 2001.0, 2002.0],
            "high": [2002.0, 2003.0, 2004.0],
            "low": [1999.0, 2000.0, 2001.0],
            "close": [2001.0, 2002.0, 2003.0],
        }
    )


@pytest.fixture
def synthetic_csv() -> Path:
    return Path(__file__).parent / "fixtures" / "synthetic_xauusd_m5.csv"
