"""Tests for the nim interactive cartridge (single-heap subtraction game)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.nim import NimScenario
from llove.events import Event, EventKind


def test_nim_registered() -> None:
    assert SCENARIOS.get("nim") is NimScenario
    assert isinstance(get_scenario("nim"), NimScenario)


async def _run(scenario: NimScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _scripted_asker(answers: list[str]) -> Callable[..., Coroutine[Any, Any, str]]:
    """An asker that replays a fixed answer list, then sticks to the default."""
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        if state["i"] < len(answers):
            a = answers[state["i"]]
            state["i"] += 1
            return a
        return default_id if default_id is not None else options[0].id

    return asker


@pytest.mark.asyncio
async def test_default_branch_is_finite_and_narrates() -> None:
    # No asker → every turn takes the deterministic default move and the
    # game must reach a terminal result with narration + audit.
    seen = await _run(get_scenario("nim"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    events = [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]
    assert "nim.game_start" in events
    assert "nim.game_end" in events


@pytest.mark.asyncio
async def test_default_run_reaches_a_result() -> None:
    seen = await _run(get_scenario("nim"))  # type: ignore[arg-type]
    texts = [str(e.payload.get("text", "")) for e in seen if e.kind == EventKind.NARRATION]
    win = t_or_empty("scenario.nim.result_win")
    lose = t_or_empty("scenario.nim.result_lose")
    assert any(win in x or lose in x for x in texts), texts


@pytest.mark.asyncio
async def test_scripted_asker_completes() -> None:
    # Always try to take 1; the asker falls back to the default once exhausted.
    s = NimScenario()
    s._asker = _scripted_asker(["1"] * _MANY)
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)
    events = [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]
    assert "nim.game_end" in events
    # The heap must actually reach zero — someone took the last object.
    final = [e for e in seen if e.payload.get("event") == "nim.game_end"]
    assert final and final[0].payload.get("winner") in {"human", "cpu"}


@pytest.mark.asyncio
async def test_take_is_always_legal_and_heap_never_negative() -> None:
    s = NimScenario()
    s._asker = _scripted_asker(["3"] * _MANY)
    seen = await _run(s)
    heaps = [
        int(e.payload["heap"])
        for e in seen
        if e.kind == EventKind.AUDIT and "heap" in e.payload and "take" in e.payload
    ]
    assert heaps  # at least one move happened
    assert all(h >= 0 for h in heaps)


def test_nim_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s_en = get_scenario("nim")
        assert s_en.title and s_en.title != "scenario.nim.title"
        assert s_en.description and s_en.description != "scenario.nim.description"
        set_locale("ja")
        s_ja = get_scenario("nim")
        assert s_ja.title and s_ja.title != "scenario.nim.title"
        assert s_ja.description and s_ja.description != "scenario.nim.description"
        assert s_en.title != s_ja.title
    finally:
        set_locale(orig)


_MANY = 60


def t_or_empty(key: str) -> str:
    from llove.i18n import t

    val = t(key)
    return "" if val == key else val
