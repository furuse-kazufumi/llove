"""Tests for the HTML exporter."""

from __future__ import annotations

from pathlib import Path

import pytest

from llove.export.html import export_html


def test_export_html_writes_self_contained_file(tmp_path: Path) -> None:
    out = tmp_path / "snapshot.html"
    export_html(source_uri="mock://demo", output_path=out, duration_s=0.5)
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    # Self-contained: no <script src=...> or <link href=...>
    assert "<script src=" not in text
    assert "<link href=" not in text
    # Has the brand mark.
    assert "llove" in text
    # Generated at least the table scaffold.
    assert "<table" in text


def test_export_html_rejects_unknown_scheme(tmp_path: Path) -> None:
    out = tmp_path / "x.html"
    with pytest.raises(ValueError):
        export_html(source_uri="ftp://nope", output_path=out, duration_s=0.1)


def _write_events(p: Path) -> None:
    """A minimal valid llove-event JSONL (each line carries a ``kind``)."""
    p.write_text(
        '{"kind":"sensor","sensor_id":"best_score","value":1.0}\n'
        '{"kind":"narration","text":"hello"}\n',
        encoding="utf-8",
    )


def test_export_html_accepts_jsonl_uri(tmp_path: Path) -> None:
    """jsonl:/// URI must work even when the path is a Windows drive (D:/...)."""
    src = tmp_path / "events.jsonl"
    _write_events(src)
    out = tmp_path / "o.html"
    uri = "jsonl:///" + str(src).replace("\\", "/")
    export_html(source_uri=uri, output_path=out, duration_s=1.0)
    text = out.read_text(encoding="utf-8")
    # events were actually read (not the "(no events)" empty snapshot)
    assert "sensor" in text
    assert "(no events)" not in text


def test_export_html_accepts_plain_local_path(tmp_path: Path) -> None:
    """A raw local path (not a URI) must be accepted, incl. Windows 'D:\\...'."""
    src = tmp_path / "events.jsonl"
    _write_events(src)
    out = tmp_path / "o.html"
    export_html(source_uri=str(src), output_path=out, duration_s=1.0)
    text = out.read_text(encoding="utf-8")
    assert "sensor" in text
    assert "(no events)" not in text


def test_export_html_missing_source_raises(tmp_path: Path) -> None:
    """A missing source file is fail-closed (FileNotFoundError), not an empty file."""
    out = tmp_path / "o.html"
    with pytest.raises(FileNotFoundError):
        export_html(source_uri=str(tmp_path / "nope.jsonl"), output_path=out, duration_s=0.1)
