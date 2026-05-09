"""CLI smoke tests using Click's test runner."""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from llove import __version__
from llove.cli import main


def test_version_command() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["version"])
    assert res.exit_code == 0
    assert __version__ in res.output


def test_help_lists_main_commands() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["--help"])
    assert res.exit_code == 0
    for cmd in ("demo", "tail", "export", "version"):
        assert cmd in res.output


def test_export_writes_file(tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "snap.html"
    res = runner.invoke(
        main,
        ["export", "--source", "mock://demo", "--html", str(out), "--duration", "0.3"],
    )
    assert res.exit_code == 0, res.output
    assert out.exists()
