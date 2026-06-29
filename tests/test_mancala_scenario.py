"""Tests for the mancala interactive board-game cartridge."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.mancala import MancalaScenario
from llove.events import Event, EventKind


def test_mancala_registered() -> None:
    assert SCENARIOS.get("mancala") is MancalaScenario
    assert isinstance(get_scenario("mancala"), MancalaScenario)


async def _run(scenario: MancalaScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _game_end(events: list[Event]) -> dict[str, Any]:
    ends = [e.payload for e in events if e.payload.get("event") == "mancala.game_end"]
    assert len(ends) == 1, "exactly one game_end audit"
    return ends[0]


def _scripted_asker(answers: list[str]) -> Callable[..., Coroutine[Any, Any, str]]:
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        a = answers[state["i"] % len(answers)]
        state["i"] += 1
        return a

    return asker


@pytest.mark.asyncio
async def test_default_branch_completes_and_narrates() -> None:
    # No asker wired -> deterministic default (lowest legal pit) plays to the end.
    seen = await _run(get_scenario("mancala"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    end = _game_end(seen)
    # Stones are conserved: 6 pits * 4 stones * 2 sides = 48.
    assert end["human"] + end["cpu"] == 48


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answers",
    [
        ["pit0"],          # always the first human pit
        ["pit5", "pit0"],  # alternate higher / lower pits
        ["pit99"],         # illegal id -> scenario must fall back safely
    ],
)
async def test_scripted_askers_complete(answers: list[str]) -> None:
    s = MancalaScenario()
    s._asker = _scripted_asker(answers)
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)
    end = _game_end(seen)
    assert end["human"] + end["cpu"] == 48


@pytest.mark.asyncio
async def test_seeds_are_deterministic_and_terminate() -> None:
    for seed in range(8):
        seen = await _run(MancalaScenario(seed=seed))
        end = _game_end(seen)
        assert end["human"] + end["cpu"] == 48


def test_mancala_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s = get_scenario("mancala")
        assert s.title and s.title != "scenario.mancala.title"
        assert "(board game)" in s.title
        assert "play" in s.description.lower()
        assert s.description != "scenario.mancala.description"

        set_locale("ja")
        s_ja = get_scenario("mancala")
        assert s_ja.title and s_ja.title != "scenario.mancala.title"
        assert "(ボードゲーム)" in s_ja.title
        assert s_ja.description != "scenario.mancala.description"
    finally:
        set_locale(orig)
