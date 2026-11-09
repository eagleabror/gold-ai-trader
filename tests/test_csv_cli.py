"""End-to-end imports of clearly synthetic local CSV only."""

import hashlib
import json

import pandas as pd
import pytest

from gold_ai_trader.data.cli import main
from gold_ai_trader.data.csv_io import load_csv, write_bundle


def import_args(path, output):
    return [
        "import-csv",
        str(path),
        "--source",
        "SYNTHETIC test fixture",
        "--reference",
        "tests/fixtures/README.md",
        "--data-kind",
        "synthetic",
        "--price-side",
        "bid",
        "--output",
        str(output),
    ]


def test_csv_hash_and_utc_round_trip(synthetic_csv, synthetic_provenance, tmp_path):
    frame, digest = load_csv(synthetic_csv, synthetic_provenance)
    output = tmp_path / "bundle"
    report = write_bundle(frame, synthetic_provenance, output, source_sha256=digest)
    assert report.valid
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["data_kind"] == "synthetic"
    assert metadata["source_sha256"] == hashlib.sha256(synthetic_csv.read_bytes()).hexdigest()
    assert (
        metadata["candles_sha256"]
        == hashlib.sha256((output / "candles.csv").read_bytes()).hexdigest()
    )
    restored, _ = load_csv(output / "candles.csv", synthetic_provenance)
    pd.testing.assert_frame_equal(frame, restored)
    with pytest.raises(FileExistsError):
        write_bundle(frame, synthetic_provenance, output)


def test_cli_success_and_no_overwrite(synthetic_csv, tmp_path, capsys):
    output = tmp_path / "bundle"
    args = import_args(synthetic_csv, output)
    assert main(args) == 0
    assert json.loads(capsys.readouterr().out)["valid"]
    assert main(args) == 2
    assert "already exists" in capsys.readouterr().err


def test_cli_invalid_input_never_persisted(synthetic_csv, tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text(synthetic_csv.read_text().replace("2000,2002", "0,2002"))
    output = tmp_path / "must-not-exist"
    assert main(import_args(bad, output)) == 1
    assert not output.exists()
    assert not json.loads(capsys.readouterr().out)["valid"]


@pytest.mark.parametrize(
    "content",
    [
        "",
        "timestamp,open,open\n2024-01-02T12:00:00Z,1,1\n",
        "timestamp,open,high,low,close\n2024-01-02 12:00:00,1,1,1,1\n",
    ],
)
def test_bad_csv_rejected(content, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(content)
    output = tmp_path / "bundle"
    assert main(import_args(bad, output)) in {1, 2}
    assert not output.exists()


def test_missing_file_has_actionable_exit(tmp_path, capsys):
    assert main(import_args(tmp_path / "absent.csv", tmp_path / "out")) == 2
    assert "rejected" in capsys.readouterr().err


def test_partial_bundle_removed_on_write_failure(
    synthetic_candles, synthetic_provenance, tmp_path, monkeypatch
):
    from pathlib import Path

    def fail(*args, **kwargs):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(Path, "write_text", fail)
    output = tmp_path / "bundle"
    with pytest.raises(OSError, match="synthetic disk failure"):
        write_bundle(synthetic_candles, synthetic_provenance, output)
    assert not output.exists()


def test_download_cli_rejects_bad_window_without_network(tmp_path, capsys):
    output = tmp_path / "out"
    assert (
        main(
            [
                "download-dukascopy",
                "--start",
                "2024-01-02T12:00:00Z",
                "--hours",
                "7",
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()
    assert "Small samples only" in capsys.readouterr().err


def test_download_cli_does_not_persist_invalid_data(
    synthetic_candles, synthetic_provenance, tmp_path, monkeypatch, capsys
):
    import gold_ai_trader.data.cli as cli

    frame = synthetic_candles.copy()
    frame.loc[0, "close"] = 0
    monkeypatch.setattr(cli, "download_sample", lambda *args: (frame, synthetic_provenance, {}))
    output = tmp_path / "out"
    assert (
        main(["download-dukascopy", "--start", "2024-01-02T12:00:00Z", "--output", str(output)])
        == 1
    )
    assert not output.exists()
    assert not json.loads(capsys.readouterr().out)["valid"]
