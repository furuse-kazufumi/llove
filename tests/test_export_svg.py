"""Tests for the animated-SVG exporter (SMIL thought-factor ring chart).

The ring chart is the export path used to embed llove visuals inside
``<img>`` on Qiita / GitHub. Those surfaces strip ``<script>`` (Camo proxy)
and the CSS-in-SVG ``@keyframes`` path is unverified there, so the contract
this suite locks down is:

  * animation is driven by **SMIL** (``<animateTransform>``),
  * the file is **self-contained** (no external ``http`` / ``cdnjs`` refs
    besides the SVG xmlns namespace identifier, which is never fetched),
  * the document is **well-formed XML** (parses via ``minidom``).
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.dom import minidom

import pytest

from llove.export import (
    SvgExportConfig,
    sample_persona_factors,
    thought_factor_ring_svg,
)

# Every external resource reference, *excluding* the SVG namespace URI which
# is an identifier (never fetched) and is mandatory on the root <svg>.
_EXTERNAL_URL_RE = re.compile(r"https?://(?!www\.w3\.org/2000/svg)")


def _assert_self_contained_smil_svg(svg: str) -> None:
    # SMIL drives the animation (no CSS @keyframes / animation: / <script>).
    assert "<animateTransform" in svg
    assert "@keyframes" not in svg
    assert "animation:" not in svg
    assert "<script" not in svg
    # Scalable: declares a viewBox.
    assert "viewBox=" in svg
    # Self-contained: zero external refs and zero CDN refs.
    assert "cdnjs" not in svg
    assert _EXTERNAL_URL_RE.search(svg) is None
    # Well-formed XML (fail-closed gate mirror).
    minidom.parseString(svg.encode("utf-8"))


def test_ring_svg_is_self_contained_smil() -> None:
    svg = thought_factor_ring_svg(sample_persona_factors("feynman"))
    _assert_self_contained_smil_svg(svg)


def test_ring_svg_balanced_default_vector() -> None:
    svg = thought_factor_ring_svg((0.5,) * 10)
    _assert_self_contained_smil_svg(svg)


def test_ring_svg_honours_duration() -> None:
    svg = thought_factor_ring_svg((0.5,) * 10, config=SvgExportConfig(duration_s=9.0))
    assert 'dur="9.0s"' in svg


def test_ring_svg_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        thought_factor_ring_svg((1.5,) * 10)


def test_ring_svg_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        thought_factor_ring_svg((0.5, 0.5))  # labels default to 10 entries


def test_export_svg_cli_writes_file(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from llove.cli import main

    out = tmp_path / "ring.svg"
    runner = CliRunner()
    result = runner.invoke(main, ["export-svg", "--out", str(out), "--persona", "newton"])
    assert result.exit_code == 0, result.output
    assert out.exists()
    _assert_self_contained_smil_svg(out.read_text(encoding="utf-8"))


def test_export_svg_cli_rejects_both_persona_and_factors(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from llove.cli import main

    out = tmp_path / "ring.svg"
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["export-svg", "--out", str(out), "--persona", "newton", "--factors", "0.5,0.5"],
    )
    assert result.exit_code != 0
    assert not out.exists()
