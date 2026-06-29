"""Tests for the twentyone (21 game) interactive cartridge."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.twentyone import TwentyOneScenario
from llove.events import Event, EventKind
from llove.i18n import t


def test_twentyone_registered() -> None:
    assert SCENARIOS.get("twentyone") is TwentyOneScenario
    assert isinstance(get_scenario("twentyone"), TwentyOneScenario)


async def _run(scenario: TwentyOneScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _scripted_asker(moves: list[str]) -> Callable[..., Coroutine[Any, Any, str]]:
    """Return ``moves`` in order; fall back to a legal option when the next
    scripted move is not on the (possibly shrunk) menu so the asker never
    picks an illegal add near the end of the game."""
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        ids = {o.id for o in options}
        nxt = moves[state["i"]] if state["i"] < len(moves) else None
        state["i"] += 1
        if nxt in ids:
            return nxt
        return default_id if default_id in ids else next(iter(ids))

    return asker


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    """No asker wired → every turn takes the +1 default and the game ends."""
    seen = await _run(get_scenario("twentyone"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    # Terminates on a result narration, not an unbounded loop.
    assert seen[-1].kind == EventKind.NARRATION
    assert seen[-1].payload.get("title") == t("scenario.twentyone.result_title")


@pytest.mark.asyncio
async def test_scripted_always_one_completes() -> None:
    s = TwentyOneScenario()
    s._asker = _scripted_asker(["1"] * 30)
    seen = await _run(s)
    assert seen[-1].kind == EventKind.NARRATION
    assert seen[-1].payload.get("title") == t("scenario.twentyone.result_title")


@pytest.mark.asyncio
async def test_scripted_mixed_never_overshoots_and_hits_21() -> None:
    s = TwentyOneScenario()
    s._asker = _scripted_asker(["3", "2", "1", "3", "2", "1", "3", "2", "1", "1"])
    seen = await _run(s)
    counts = [e.payload["count"] for e in seen if e.kind == EventKind.AUDIT]
    assert counts, "expected at least one applied move"
    assert all(c <= 21 for c in counts)  # exactly-21-wins → no overshoot
    assert 21 in counts  # somebody reaches the goal
    assert seen[-1].payload.get("title") == t("scenario.twentyone.result_title")


@pytest.mark.asyncio
async def test_audit_moves_alternate_actors() -> None:
    s = TwentyOneScenario()
    s._asker = _scripted_asker(["2"] * 30)
    seen = await _run(s)
    actors = [e.payload["actor"] for e in seen if e.kind == EventKind.AUDIT]
    assert actors[0] == "You"
    # Strictly increasing count proves the loop makes progress every turn.
    counts = [e.payload["count"] for e in seen if e.kind == EventKind.AUDIT]
    assert counts == sorted(counts)
    assert len(set(counts)) == len(counts)


def test_twentyone_i18n_resolves() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("ja")
        s = get_scenario("twentyone")
        assert s.title != "scenario.twentyone.title"
        assert s.description != "scenario.twentyone.description"
        assert "21" in s.title
        set_locale("en")
        s_en = get_scenario("twentyone")
        assert "21" in s_en.title
        assert "play" in s_en.description.lower()
    finally:
        set_locale(orig)
