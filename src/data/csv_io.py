"""Strict CSV loading and traceable, non-overwriting dataset bundles."""

import csv
import hashlib
import io
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .schema import Provenance, price_columns
from .validation import ValidationReport, normalize_timestamps, validate_candles


def load_csv(path: Path, provenance: Provenance) -> tuple[pd.DataFrame, str]:
    """Read once so the source hash describes exactly the parsed bytes."""
    payload = path.read_bytes()
    # Read the header independently: pandas would otherwise rename duplicate headers.
    header = next(csv.reader(io.StringIO(payload.decode("utf-8-sig"))), [])
    if len(header) != len(set(header)):
        raise ValueError("Duplicate CSV column names")
    frame = pd.read_csv(io.BytesIO(payload), dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if "timestamp" in frame:
        frame["timestamp"] = normalize_timestamps(frame["timestamp"])
    for column in price_columns(provenance.price_side):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame, hashlib.sha256(payload).hexdigest()


def write_bundle(
    frame: pd.DataFrame,
    provenance: Provenance,
    output: Path,
    *,
    source_sha256: str | None = None,
    allow_gaps: bool = False,
    acquisition: dict | None = None,
) -> ValidationReport:
    """Only valid datasets are persisted; an existing bundle is never replaced."""
    report = validate_candles(frame, provenance, allow_gaps=allow_gaps)
    if not report.valid:
        return report
    output.mkdir(parents=True, exist_ok=False)
    try:
        canonical = frame[["timestamp", *price_columns(provenance.price_side)]].copy()
        canonical["timestamp"] = canonical["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        csv_bytes = canonical.to_csv(index=False, lineterminator="\n").encode("utf-8")
        (output / "candles.csv").write_bytes(csv_bytes)
        metadata = {
            "schema_version": 1,
            **provenance.to_dict(),
            "created_at_utc": datetime.now(UTC).isoformat(),
            "source_sha256": source_sha256,
            "candles_sha256": hashlib.sha256(csv_bytes).hexdigest(),
            "provenance_verification": "source-declared; not independent authentication",
            "gap_policy": "review_required" if allow_gaps else "reject",
            "acquisition": acquisition,
            "validation": report.to_dict(),
        }
        (output / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
    except BaseException:
        shutil.rmtree(output)
        raise
    return report
