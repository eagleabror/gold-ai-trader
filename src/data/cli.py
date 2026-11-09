"""Command line interface with nonzero exits on rejected datasets or acquisition failure."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from .csv_io import load_csv, write_bundle
from .dukascopy import download_sample
from .quality import inspect_bundle
from .schema import Provenance


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="XAUUSD M5 data only; no trading functionality")
    sub = root.add_subparsers(dest="command", required=True)
    csv_parser = sub.add_parser(
        "import-csv", help="Validate a source CSV and write an auditable bundle"
    )
    csv_parser.add_argument("input", type=Path)
    csv_parser.add_argument("--source", required=True, help="Provider name; no credentials")
    csv_parser.add_argument(
        "--reference", required=True, help="Source URL or local provenance note"
    )
    csv_parser.add_argument("--data-kind", required=True, choices=["historical", "synthetic"])
    csv_parser.add_argument(
        "--price-side", required=True, choices=["bid", "ask", "mid", "unknown", "bid_ask"]
    )
    csv_parser.add_argument(
        "--allow-gaps", action="store_true", help="Retain gaps as review warnings"
    )
    downloader = sub.add_parser(
        "download-dukascopy", help="Optional: fetch only 1–6 historical hours"
    )
    downloader.add_argument("--start", required=True, help="ISO timestamp with explicit offset")
    downloader.add_argument("--hours", type=int, default=1)
    for command in (csv_parser, downloader):
        command.add_argument(
            "--output", type=Path, required=True, help="New directory; never overwritten"
        )
    quality = sub.add_parser("quality-report", help="Recheck a local bundle; no network access")
    quality.add_argument("bundle", type=Path)
    quality.add_argument("--start", required=True, help="Expected bar-open UTC hour with offset")
    quality.add_argument("--hours", type=int, default=1)
    quality.add_argument("--output", required=True, type=Path, help="New JSON report file")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError(f"Output already exists: {args.output}")
        if args.command == "quality-report":
            start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
            result = inspect_bundle(args.bundle, start, args.hours)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0 if result["valid"] else 1
        if args.command == "import-csv":
            provenance = Provenance(args.source, args.reference, args.data_kind, args.price_side)
            frame, digest = load_csv(args.input, provenance)
            report = write_bundle(
                frame, provenance, args.output, source_sha256=digest, allow_gaps=args.allow_gaps
            )
        else:
            start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
            frame, provenance, acquisition = download_sample(start, args.hours)
            report = write_bundle(frame, provenance, args.output, acquisition=acquisition)
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.valid else 1
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        print(f"Data operation rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
