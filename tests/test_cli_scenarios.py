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


def test_demo_list_resolves_titles_and_descriptions() -> None:
    """Regression: SCENARIOS values are classes, so cls.title returns a property
    object (not a string). The list view must instantiate them so i18n resolves.
    """
    runner = CliRunner()
    res = runner.invoke(main, ["demo", "--list"])
    assert res.exit_code == 0
    assert "<property object" not in res.output
    assert "Firewall — 4-layer prompt screening" in res.output
    assert "L0/L1/L1.5/L2" in res.output


def test_demo_list_japanese_locale() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["--lang", "ja", "demo", "--list"])
    assert res.exit_code == 0
    assert "<property object" not in res.output


def test_demo_unknown_scenario_returns_error() -> None:
    runner = CliRunner()
    res = runner.invoke(main, ["demo", "--scenario", "no-such-thing"])
    assert res.exit_code == 2
    assert "unknown scenario" in res.output
