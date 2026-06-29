"""App-level integration: an interactive scenario prompts via ChoiceScreen.

Verifies the asker is injected for InteractiveScenario sources, that the modal
appears while the scenario awaits a decision, that picking an option lets the
run continue, and that the decision is recorded in the JSONL log (so a --log
run replays the exact path taken).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

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
    app = LoveApp(_AskOnce(), with_narration=True)
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


@pytest.mark.asyncio
async def test_choice_is_recorded_in_jsonl_log(tmp_path: Path) -> None:
    log = tmp_path / "run.jsonl"
    app = LoveApp(_AskOnce(), with_narration=True, log_path=log)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        assert isinstance(app.screen, ChoiceScreen)
        await pilot.press("1")  # pick Option A
        await pilot.pause(0.1)

    lines = [
        json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    events = [rec.get("payload", {}).get("event") for rec in lines]
    assert "llove.choice" in events  # the decision was logged
    assert "branch" in events  # the scenario continued past the choice
    choice_rec = next(
        rec for rec in lines if rec.get("payload", {}).get("event") == "llove.choice"
    )
    assert choice_rec["payload"]["chosen"] == "a"
    assert choice_rec["payload"]["chosen_label"] == "Option A"
