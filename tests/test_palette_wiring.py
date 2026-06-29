"""Command Palette wiring — the ':' palette is a working launcher in LoveApp.

Before this, LoveApp pushed CommandPaletteScreen() with no registry/ctx, so the
registry was empty (``:help`` errored) and every command was inert. These tests
pin that ``:help`` / ``:demo`` / ``:theme`` / ``:identity`` are now live.
"""

from __future__ import annotations

import pytest
from textual.widgets import Input

from llove.app import LoveApp
from llove.demo.scenarios import get_scenario
from llove.demo.scenarios.incident import IncidentScenario
from llove.term.palette import CommandPaletteScreen, CommandPaletteWidget


async def _run_cmd(pilot, app, command: str) -> CommandPaletteWidget:  # type: ignore[no-untyped-def]
    """Open the palette (':') and submit ``command`` (set value to allow spaces)."""
    await pilot.press(":")
    await pilot.pause(0.05)
    assert isinstance(app.screen, CommandPaletteScreen)
    widget = app.screen.query_one(CommandPaletteWidget)
    inp = widget.query_one("#cp-input", Input)
    inp.focus()
    inp.value = command
    await pilot.press("enter")
    await pilot.pause(0.05)
    return widget


@pytest.mark.asyncio
async def test_palette_help_lists_commands_without_error() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "help")
        out = widget.last_output_text
        assert "[core]" in out  # registry wired -> :help lists categories
        assert "registry hook 未設定" not in out


@pytest.mark.asyncio
async def test_palette_demo_switches_scenario() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        await _run_cmd(pilot, app, "demo incident")
        assert isinstance(app._source, IncidentScenario)


@pytest.mark.asyncio
async def test_palette_demo_unknown_reports_error() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "demo nope_not_a_scenario")
        assert "demo 起動失敗" in widget.last_output_text


@pytest.mark.asyncio
async def test_palette_theme_is_wired() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "theme")
        out = widget.last_output_text
        assert "current theme:" in out
        assert "hook 未配線" not in out


@pytest.mark.asyncio
async def test_palette_identity_is_ok() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "identity")
        assert "did:key" in widget.last_output_text


@pytest.mark.asyncio
async def test_palette_open_stays_honestly_unwired() -> None:
    # :open has no hook bound -> it must still respond gracefully (not crash).
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "open image:///tmp/x.png")
        assert "hook 未配線" in widget.last_output_text
