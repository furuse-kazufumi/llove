"""Tests for the War card-game scenario."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.war import WarScenario
from llove.events import Event, EventKind


def test_war_registered() -> None:
    assert SCENARIOS.get("war") is WarScenario
    assert isinstance(get_scenario("war"), WarScenario)


async def _run(scenario: WarScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _fixed_asker(choice: str | None) -> Callable[..., Coroutine[Any, Any, str]]:
    """An asker that always picks ``choice`` (or the default when None / absent)."""

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        if choice is not None:
            for o in options:
                if o.id == choice:
                    return choice
        return default_id if default_id is not None else options[0].id

    return asker


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    # No asker wired -> deterministic default path (flip; ties settled by war).
    seen = await _run(get_scenario("war"))  # type: ignore[arg-type]
    assert len(seen) > 0
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    # The run must terminate on a result narration.
    assert kinds[-1] == EventKind.NARRATION


@pytest.mark.asyncio
async def test_finite_under_hard_cap() -> None:
    # Even a pathological asker that always keeps the peace (no card ever
    # changes hands) must still terminate via the _MAX_TURNS hard cap.
    s = WarScenario()
    s._asker = _fixed_asker("peace")
    seen = await _run(s)
    assert len(seen) < 2000


@pytest.mark.asyncio
async def test_scripted_war_choice_completes() -> None:
    s = WarScenario()
    s._asker = _fixed_asker("war")
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)
    end = [
        e
        for e in seen
        if e.kind == EventKind.AUDIT and e.payload.get("event") == "war.game_end"
    ]
    assert end, "game must record a war.game_end audit"


@pytest.mark.asyncio
async def test_default_asker_branch_completes() -> None:
    # A scripted asker that always returns the default option also completes.
    s = WarScenario()
    s._asker = _fixed_asker(None)
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)


def test_war_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s = get_scenario("war")
        assert s.title and s.title != "scenario.war.title"
        assert "play" in s.description.lower()
        set_locale("ja")
        s_ja = get_scenario("war")
        assert s_ja.title and s_ja.title != "scenario.war.title"
        assert s_ja.description and s_ja.description != "scenario.war.description"
    finally:
        set_locale(orig)
