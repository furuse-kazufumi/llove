"""Tests for the tictactoe interactive board-game scenario."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.tictactoe import TicTacToeScenario
from llove.events import Event, EventKind
from llove.i18n import t


def test_tictactoe_registered() -> None:
    assert SCENARIOS.get("tictactoe") is TicTacToeScenario
    assert isinstance(get_scenario("tictactoe"), TicTacToeScenario)


async def _run(scenario: TicTacToeScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _default_asker() -> Callable[..., Coroutine[Any, Any, str]]:
    """Always pick the deterministic default cell."""

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return default_id if default_id is not None else options[0].id

    return asker


def _scripted_asker(
    answers: list[str],
) -> Callable[..., Coroutine[Any, Any, str]]:
    """Play the given cell ids in order, skipping any that are not legal."""
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        ids = {o.id for o in options}
        while state["i"] < len(answers):
            a = answers[state["i"]]
            state["i"] += 1
            if a in ids:
                return a
        return default_id if default_id is not None else options[0].id

    return asker


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    # No asker → deterministic default cell each turn; must finish on its own.
    seen = await _run(get_scenario("tictactoe"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    moves = [
        e
        for e in seen
        if e.kind == EventKind.AUDIT and e.payload.get("event") == "tictactoe.move"
    ]
    # Bounded: a 3x3 game can never place more than nine pieces.
    assert 1 <= len(moves) <= 9


@pytest.mark.asyncio
async def test_default_asker_reaches_a_result() -> None:
    s = TicTacToeScenario()
    s._asker = _default_asker()
    seen = await _run(s)
    results = {
        t("scenario.tictactoe.result_win"),
        t("scenario.tictactoe.result_lose"),
        t("scenario.tictactoe.result_draw"),
    }
    texts = [str(e.payload.get("text", "")) for e in seen if e.kind == EventKind.NARRATION]
    assert any(txt in results for txt in texts)


@pytest.mark.asyncio
async def test_scripted_moves_terminate_with_result_title() -> None:
    s = TicTacToeScenario()
    s._asker = _scripted_asker([str(i) for i in range(1, 10)])
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)
    titles = [e.payload.get("title") for e in seen if e.kind == EventKind.NARRATION]
    assert t("scenario.tictactoe.result_title") in titles
    # X always moves into a legal empty cell — never overwrites a piece.
    x_cells = [
        e.payload.get("cell")
        for e in seen
        if e.kind == EventKind.AUDIT and e.payload.get("player") == "X"
    ]
    assert len(x_cells) == len(set(x_cells))


def test_tictactoe_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s = get_scenario("tictactoe")
        assert s.title and s.title != "scenario.tictactoe.title"
        assert s.description and s.description != "scenario.tictactoe.description"
        en_title = s.title
        set_locale("ja")
        s_ja = get_scenario("tictactoe")
        assert s_ja.title and s_ja.title != "scenario.tictactoe.title"
        assert s_ja.title != en_title
    finally:
        set_locale(orig)
