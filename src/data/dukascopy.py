"""Optional, bounded Dukascopy hourly BI5 tick downloader and M5 aggregation.

Feed conventions require verification against genuine downloaded XAUUSD data.
Tests exercise only synthetic BI5 records and mocked network responses.
"""

import hashlib
import lzma
import math
import struct
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pandas as pd

from .schema import Provenance

BASE_URL = "https://datafeed.dukascopy.com/datafeed/XAUUSD"
PRICE_SCALE = 1000  # Dukascopy XAUUSD integer quote convention, not Exness contract specs.
MAX_COMPRESSED_BYTES = 8 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 32 * 1024 * 1024
RECORD = struct.Struct(">3I2f")  # millisecond offset, ask, bid, ask volume, bid volume


class DownloadError(ValueError):
    """A complete and trustworthy sample could not be obtained."""


def validate_window(start: datetime, hours: int) -> datetime:
    if start.tzinfo is None or start.utcoffset() is None:
        raise DownloadError("Start must have an explicit UTC offset")
    start = start.astimezone(UTC)
    if start.minute or start.second or start.microsecond:
        raise DownloadError("Start must align to a UTC hour")
    if not 1 <= hours <= 6:
        raise DownloadError("Small samples only: hours must be between 1 and 6")
    if start + timedelta(hours=hours) > datetime.now(UTC).replace(
        minute=0, second=0, microsecond=0
    ):
        raise DownloadError("Only fully completed historical hours may be requested")
    return start


def hour_url(hour: datetime) -> str:
    # Dukascopy archive months are zero-based (January = 00).
    return f"{BASE_URL}/{hour.year}/{hour.month - 1:02d}/{hour.day:02d}/{hour.hour:02d}h_ticks.bi5"


def fetch_hour(url: str) -> bytes:
    try:
        import requests
    except ImportError as exc:
        raise DownloadError("Install optional dependencies: pip install -e '.[download]'") from exc
    try:
        # Redirects are rejected so the fixed source cannot silently change hosts.
        with requests.get(url, timeout=(10, 30), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise DownloadError(f"Dukascopy returned HTTP {response.status_code}: {url}")
            payload = bytearray()
            for chunk in response.iter_content(chunk_size=65536):
                payload.extend(chunk)
                if len(payload) > MAX_COMPRESSED_BYTES:
                    raise DownloadError("Compressed hourly response exceeds size limit")
            if not payload:
                raise DownloadError(f"Empty hourly response: {url}")
            return bytes(payload)
    except requests.RequestException as exc:
        raise DownloadError(f"Dukascopy request failed ({type(exc).__name__}): {url}") from exc


def decode_ticks(payload: bytes, hour: datetime) -> pd.DataFrame:
    """Decode a single LZMA stream; reject corrupt, crossed or unordered ticks."""
    if len(payload) > MAX_COMPRESSED_BYTES:
        raise DownloadError("Compressed hourly response exceeds size limit")
    decoder = lzma.LZMADecompressor(memlimit=64 * 1024 * 1024)
    try:
        raw = decoder.decompress(payload, max_length=MAX_DECOMPRESSED_BYTES + 1)
    except lzma.LZMAError as exc:
        raise DownloadError("Invalid BI5 LZMA payload") from exc
    if len(raw) > MAX_DECOMPRESSED_BYTES:
        raise DownloadError("Decompressed hourly response exceeds size limit")
    if not decoder.eof or decoder.unused_data or not raw or len(raw) % RECORD.size:
        raise DownloadError("Empty, truncated or trailing BI5 data")
    records = list(RECORD.iter_unpack(raw))
    previous = -1
    for offset, ask, bid, ask_volume, bid_volume in records:
        if not previous <= offset < 3_600_000:
            raise DownloadError("Invalid or unordered tick millisecond offset")
        if bid <= 0 or ask < bid:
            raise DownloadError("Nonpositive or crossed tick prices")
        if not all(math.isfinite(v) and v >= 0 for v in (ask_volume, bid_volume)):
            raise DownloadError("Invalid tick volume")
        previous = offset
    ticks = pd.DataFrame(records, columns=["offset", "ask", "bid", "ask_volume", "bid_volume"])
    ticks["timestamp"] = pd.Timestamp(hour) + pd.to_timedelta(ticks["offset"], unit="ms")
    ticks["ask"] = ticks["ask"] / PRICE_SCALE
    ticks["bid"] = ticks["bid"] / PRICE_SCALE
    return ticks[["timestamp", "bid", "ask"]]


def download_sample(
    start: datetime, hours: int = 1, *, fetch: Callable[[str], bytes] = fetch_hour
) -> tuple[pd.DataFrame, Provenance, dict]:
    start = validate_window(start, hours)
    ticks = []
    sources = []
    for offset in range(hours):
        hour = start + timedelta(hours=offset)
        url = hour_url(hour)
        payload = fetch(url)
        ticks.append(decode_ticks(payload, hour))
        sources.append(
            {"url": url, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        )
    quotes = pd.concat(ticks, ignore_index=True).set_index("timestamp")
    sides = []
    for side in ("bid", "ask"):
        candles = quotes[side].resample("5min", closed="left", label="left").ohlc()
        sides.append(candles.add_prefix(f"{side}_"))
    # Missing bins remain missing, never filled. Require the entire requested window.
    candles = (
        pd.concat(sides, axis=1)
        .reindex(pd.date_range(start, periods=hours * 12, freq="5min", name="timestamp"))
        .reset_index()
    )
    provenance = Provenance("Dukascopy public tick archive", BASE_URL, "historical", "bid_ask")
    acquisition = {
        "requested_start_utc": start.isoformat(),
        "requested_end_exclusive_utc": (start + timedelta(hours=hours)).isoformat(),
        "price_scale": PRICE_SCALE,
        "tick_files": sources,
        "aggregation": "independent bid/ask OHLC; left-closed M5; no forward fill",
    }
    return candles, provenance, acquisition
