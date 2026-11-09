"""Fail-closed candle checks. No sorting, filling or deduplication repairs."""

from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from .schema import OHLC, Provenance, price_columns


@dataclass
class Issue:
    code: str
    severity: Literal["error", "warning"]
    message: str
    count: int
    row_samples: list[int] = field(default_factory=list)


@dataclass
class ValidationReport:
    rows: int
    provenance: dict
    coverage_start_utc: str | None = None
    coverage_end_utc: str | None = None
    issues: list[Issue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict:
        return {**asdict(self), "valid": self.valid, "timestamp_semantics": "bar_open_utc"}


def normalize_timestamps(values: pd.Series) -> pd.Series:
    """Require explicit offsets; naive, numeric and invalid timestamps become NaT."""

    def parse(value: object) -> pd.Timestamp:
        if not isinstance(value, str) or not value.strip():
            return pd.NaT
        try:
            stamp = pd.Timestamp(value)
            if stamp.tzinfo is None:
                return pd.NaT
            # Limit to ns range so malformed extremes become validation errors.
            return stamp.tz_convert("UTC").as_unit("ns")
        except (ValueError, TypeError, OverflowError):
            return pd.NaT

    return pd.Series(pd.to_datetime(values.map(parse), utc=True), index=values.index)


def validate_candles(
    frame: pd.DataFrame, provenance: Provenance, *, allow_gaps: bool = False
) -> ValidationReport:
    # Diagnostics always refer to zero-based input row positions, independent of labels.
    frame = frame.reset_index(drop=True)
    report = ValidationReport(rows=len(frame), provenance=provenance.to_dict())

    def add(code: str, message: str, mask=None, *, warning: bool = False) -> None:
        positions = [] if mask is None else np.flatnonzero(np.asarray(mask)).tolist()
        report.issues.append(
            Issue(
                code,
                "warning" if warning else "error",
                message,
                len(positions) if mask is not None else 1,
                positions[:10],
            )
        )

    required = ["timestamp", *price_columns(provenance.price_side)]
    if frame.columns.duplicated().any():
        add("duplicate_columns", "Repeated column names are not allowed")
        return report
    missing = sorted(set(required) - set(frame.columns))
    extra = sorted(set(frame.columns) - set(required))
    if missing:
        add("missing_columns", f"Missing columns: {', '.join(missing)}")
    if extra:
        add("unexpected_columns", f"Unsupported columns: {', '.join(extra)}")
    if frame.empty:
        add("empty_data", "No candles supplied")
    if missing or frame.empty:
        return report

    stamps = frame["timestamp"]
    if not isinstance(stamps.dtype, pd.DatetimeTZDtype) or str(stamps.dt.tz) != "UTC":
        add("timestamp_timezone", "Normalized timestamps must use UTC")
        return report
    add_mask = stamps.isna()
    if add_mask.any():
        add(
            "invalid_timestamp",
            "Timestamp missing, invalid or lacking an explicit offset",
            add_mask,
        )
    valid_stamps = stamps.dropna()
    if not valid_stamps.empty:
        report.coverage_start_utc = valid_stamps.min().isoformat()
        report.coverage_end_utc = valid_stamps.max().isoformat()
    duplicates = stamps.notna() & stamps.duplicated(keep=False)
    if duplicates.any():
        add("duplicate_candles", "Repeated UTC bar-open timestamps", duplicates)
    if not valid_stamps.is_monotonic_increasing:
        add("unordered_candles", "Candles must already be in chronological order")
    misaligned = stamps.notna() & stamps.ne(stamps.dt.floor("5min"))
    if misaligned.any():
        add("m5_alignment", "Timestamps must align to UTC five-minute boundaries", misaligned)
    # Sort a copy for diagnostics only. Never change the supplied dataset.
    unique = valid_stamps.drop_duplicates().sort_values()
    gaps = unique.diff() > pd.Timedelta(minutes=5)
    if gaps.any():
        add(
            "time_gaps",
            "Intervals exceed M5; review market closures and missing data",
            frame.index.isin(unique.index[gaps]),
            warning=allow_gaps,
        )

    for prefix in ("bid_", "ask_") if provenance.price_side == "bid_ask" else ("",):
        columns = [prefix + name for name in OHLC]
        prices = frame[columns].apply(pd.to_numeric, errors="coerce")
        invalid = (~np.isfinite(prices) | (prices <= 0)).any(axis=1)
        if invalid.any():
            add(
                "invalid_prices", f"{prefix or 'quote'} prices must be finite and positive", invalid
            )
        o, h, low, c = (prices[prefix + name] for name in OHLC)
        inconsistent = ~invalid & ((h < low) | (h < o) | (h < c) | (low > o) | (low > c))
        if inconsistent.any():
            add("ohlc_inconsistent", f"{prefix or 'quote'} OHLC bounds violated", inconsistent)
    if provenance.price_side == "bid_ask":
        crossed = pd.Series(False, index=frame.index)
        for name in OHLC:
            crossed |= pd.to_numeric(frame[f"ask_{name}"], errors="coerce") < pd.to_numeric(
                frame[f"bid_{name}"], errors="coerce"
            )
        if crossed.any():
            add(
                "crossed_quotes",
                "Ask OHLC values must not be below corresponding bid values",
                crossed,
            )
    else:
        add(
            "spread_unavailable",
            "Single-side OHLC cannot establish executable spreads",
            warning=True,
        )
    if provenance.price_side == "unknown":
        add(
            "unknown_price_side",
            "Quote side is unverified; unsuitable for cost modeling",
            warning=True,
        )
    if provenance.data_kind == "synthetic":
        add("synthetic_data", "Code-validation fixture only; never market evidence", warning=True)
    return report
