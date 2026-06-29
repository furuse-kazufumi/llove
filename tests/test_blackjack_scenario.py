"""Tests for the blackjack interactive scenario (card-game cartridge)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.blackjack import BlackjackScenario
from llove.events import Event, EventKind


def test_blackjack_registered() -> None:
    assert SCENARIOS.get("blackjack") is BlackjackScenario
    assert isinstance(get_scenario("blackjack"), BlackjackScenario)


async def _run(scenario: BlackjackScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _cycling_asker(answers: list[str]) -> Callable[..., Coroutine[Any, Any, str]]:
    """Return ``answers`` in order, cycling once exhausted (hit can repeat)."""
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        a = answers[state["i"] % len(answers)]
        state["i"] += 1
        return a

    return asker


def _audit_events(seen: list[Event]) -> list[str]:
    return [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]


@pytest.mark.asyncio
async def test_default_branch_completes_with_result() -> None:
    # No asker → deterministic default path: stand on the opening hand.
    seen = await _run(get_scenario("blackjack"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    assert "result" in _audit_events(seen)  # the hand always reaches a verdict


@pytest.mark.asyncio
async def test_always_hit_busts_and_terminates() -> None:
    s = BlackjackScenario(seed=0)
    s._asker = _cycling_asker(["hit"])
    seen = await _run(s)
    assert "player_hit" in _audit_events(seen)
    assert "result" in _audit_events(seen)  # terminates despite always hitting
    assert EventKind.NARRATION in [e.kind for e in seen]


@pytest.mark.asyncio
async def test_always_stand_lets_dealer_play() -> None:
    s = BlackjackScenario(seed=7)
    s._asker = _cycling_asker(["stand"])
    seen = await _run(s)
    events = _audit_events(seen)
    assert "player_stand" in events
    assert "result" in events
    # Standing on the opener hands the turn to the dealer.
    assert "deal" in events


@pytest.mark.asyncio
@pytest.mark.parametrize("answers", [["stand"], ["hit"], ["hit", "stand"]])
async def test_every_path_emits_narration_and_result(answers: list[str]) -> None:
    s = BlackjackScenario(seed=3)
    s._asker = _cycling_asker(answers)
    seen = await _run(s)
    assert EventKind.NARRATION in [e.kind for e in seen], answers
    assert "result" in _audit_events(seen), answers


def test_blackjack_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s = get_scenario("blackjack")
        assert s.title and s.title != "scenario.blackjack.title"
        assert "(card game)" in s.title
        assert "play" in s.description.lower()
        set_locale("ja")
        s_ja = get_scenario("blackjack")
        assert s_ja.title and s_ja.title != "scenario.blackjack.title"
        assert "(カードゲーム)" in s_ja.title
    finally:
        set_locale(orig)
