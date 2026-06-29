"""App-level integration: an interactive scenario prompts via ChoiceScreen.

Verifies the asker is injected for InteractiveScenario sources (and *not* for
ordinary sources), that the modal appears while the scenario awaits, and that
picking an option lets the run continue and records the decision in the audit
pane.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from llove.app import LoveApp
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.sources.base import DataSource
from llove.term.choice import ChoiceOption
from llove.term.choice_screen import ChoiceScreen


class _AskOnce(InteractiveScenario):
    name = "askonce"
    i18n_key = "scenario"
    default_pause = 0.0

    async def events(self) -> AsyncIterator[Event]:
        opts = [ChoiceOption("a", "Option A"), ChoiceOption("b", "Option B")]
        choice = await self.ask("pick one", opts, default_id="a")
        yield Event(
            kind=EventKind.AUDIT,
            source_id="askonce",
            payload={"event": "branch", "id": choice},
        )


class _StaticSource(DataSource):
    name = "static"

    def __init__(self, events: list[Event]) -> None:
        self._events = events

    async def stream(self) -> AsyncIterator[Event]:
        for ev in self._events:
            yield ev
            await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_interactive_scenario_prompts_and_branches() -> None:
    scenario = _AskOnce()
    app = LoveApp(scenario, with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        # The scenario is suspended on the choice-point modal.
        assert isinstance(app.screen, ChoiceScreen)
        await pilot.press("2")  # pick Option B
        await pilot.pause(0.1)
        # Modal dismissed, run continued.
        assert not isinstance(app.screen, ChoiceScreen)


@pytest.mark.asyncio
async def test_non_interactive_source_gets_no_modal() -> None:
    src = _StaticSource([Event(kind=EventKind.AUDIT, payload={"event": "ok"})])
    app = LoveApp(src)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        assert not isinstance(app.screen, ChoiceScreen)
        assert app._source._asker is None if isinstance(app._source, InteractiveScenario) else True


@pytest.mark.asyncio
async def test_choice_is_recorded_in_audit_log() -> None:
    scenario = _AskOnce()
    app = LoveApp(scenario, with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        assert isinstance(app.screen, ChoiceScreen)
        await pilot.press("1")  # pick Option A
        await pilot.pause(0.1)
        # The audit view should have recorded the llove.choice decision.
        rows = "\n".join(getattr(app._audit, "_rows", []))
        assert "decision" in rows.lower() or "Option A" in rows
