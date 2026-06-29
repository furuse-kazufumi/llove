"""Tests for InteractiveScenario.ask — asker injection + deterministic default."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.term.choice import ChoiceOption


class _Branch(InteractiveScenario):
    """Minimal interactive scenario: asks once, records the branch taken."""

    name = "branch"
    i18n_key = "scenario"

    async def events(self) -> AsyncIterator[Event]:
        opts = [ChoiceOption("a", "A"), ChoiceOption("b", "B")]
        choice = await self.ask("pick", opts, default_id="a")
        yield Event(kind=EventKind.AUDIT, payload={"event": "chose", "id": choice})


@pytest.mark.asyncio
async def test_ask_falls_back_to_default_without_asker() -> None:
    s = _Branch()
    s.default_pause = 0.0
    seen = [ev async for ev in s.events()]
    assert seen[-1].payload["id"] == "a"


@pytest.mark.asyncio
async def test_ask_uses_injected_asker() -> None:
    s = _Branch()
    s.default_pause = 0.0

    async def fake(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return "b"

    s._asker = fake
    seen = [ev async for ev in s.events()]
    assert seen[-1].payload["id"] == "b"


@pytest.mark.asyncio
async def test_ask_validates_empty_options() -> None:
    s = _Branch()
    with pytest.raises(ValueError):
        await s.ask("q", [])


@pytest.mark.asyncio
async def test_ask_default_id_none_picks_first() -> None:
    s = _Branch()
    chosen = await s.ask("q", [ChoiceOption("x", "X"), ChoiceOption("y", "Y")])
    assert chosen == "x"
