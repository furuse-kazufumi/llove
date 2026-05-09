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
