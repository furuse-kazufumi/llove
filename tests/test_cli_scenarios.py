"""CLI tests for demo --list / --scenario."""
from __future__ import annotations

from click.testing import CliRunner

from llove.cli import main


def test_demo_list_shows_all_scenarios() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["demo", "--list"])
    assert res.exit_code == 0
    for name in ("firewall", "scada", "multimodal", "rag", "backends", "audit", "reliability"):
        assert name in res.output


def test_demo_unknown_scenario_returns_error() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["demo", "--scenario", "no-such-thing"])
    assert res.exit_code == 2
    assert "unknown scenario" in res.output
