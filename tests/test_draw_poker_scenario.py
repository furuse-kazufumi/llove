"""Tests for the draw_poker interactive card-game cartridge."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.draw_poker import (
    DrawPokerScenario,
    _hand_rank,
    _recommended_discards,
    _worst_indices,
)
from llove.events import Event, EventKind


def test_draw_poker_registered() -> None:
    assert SCENARIOS.get("draw_poker") is DrawPokerScenario
    assert isinstance(get_scenario("draw_poker"), DrawPokerScenario)


async def _run(scenario: DrawPokerScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _scripted_asker(answers: list[str]) -> Callable[..., Coroutine[Any, Any, str]]:
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        a = answers[state["i"] % len(answers)]
        state["i"] += 1
        return a

    return asker


def _audit_events(seen: list[Event]) -> list[str]:
    return [str(e.payload.get("event")) for e in seen if e.kind == EventKind.AUDIT]


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    # No asker → deterministic recommended discard each round; must finish.
    seen = await _run(get_scenario("draw_poker"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    assert "draw_poker.match_result" in _audit_events(seen)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answers",
    [["discard_0"], ["discard_1"], ["discard_2"], ["discard_3"],
     ["discard_3", "discard_0", "discard_2"]],
)
async def test_scripted_play_completes(answers: list[str]) -> None:
    s = DrawPokerScenario()
    s._asker = _scripted_asker(answers)
    seen = await _run(s)
    assert EventKind.NARRATION in [e.kind for e in seen], answers
    rounds = [e for e in seen if e.payload.get("event") == "draw_poker.round_result"]
    assert len(rounds) == 3, answers  # exactly _MAX_TURNS rounds
    assert _audit_events(seen).count("draw_poker.match_result") == 1


@pytest.mark.asyncio
async def test_match_is_decided_consistently() -> None:
    s = DrawPokerScenario(seed=7)
    seen = await _run(s)
    match = next(e for e in seen if e.payload.get("event") == "draw_poker.match_result")
    you, cpu = match.payload["score"]
    final_narr = [e for e in seen if e.kind == EventKind.NARRATION][-1]
    text = str(final_narr.payload.get("text", "")).lower()
    if you > cpu:
        assert "win" in text or "勝ち" in text
    elif you < cpu:
        assert "cpu" in text or "勝ち" in text


def test_hand_rank_ladder() -> None:
    h, s, d, c = "♥", "♠", "♦", "♣"
    quads = [(9, h), (9, s), (9, d), (9, c), (2, h)]
    full = [(3, h), (3, s), (3, d), (6, c), (6, h)]
    flush = [(2, h), (5, h), (9, h), (11, h), (13, h)]
    straight = [(5, h), (6, s), (7, d), (8, c), (9, h)]
    wheel = [(14, h), (2, s), (3, d), (4, c), (5, h)]
    trips = [(4, h), (4, s), (4, d), (9, c), (2, h)]
    two_pair = [(4, h), (4, s), (9, d), (9, c), (2, h)]
    pair = [(4, h), (4, s), (9, d), (7, c), (2, h)]
    high = [(4, h), (11, s), (9, d), (7, c), (2, h)]
    assert _hand_rank(quads)[0] == 7
    assert _hand_rank(full)[0] == 6
    assert _hand_rank(flush)[0] == 5
    assert _hand_rank(straight)[0] == 4
    assert _hand_rank(wheel)[0] == 4  # A-2-3-4-5
    assert _hand_rank(trips)[0] == 3
    assert _hand_rank(two_pair)[0] == 2
    assert _hand_rank(pair)[0] == 1
    assert _hand_rank(high)[0] == 0
    # strict ordering across the whole ladder
    ladder = [high, pair, two_pair, trips, straight, flush, full, quads]
    keys = [_hand_rank(x) for x in ladder]
    assert keys == sorted(keys)
    # higher pair beats lower pair (tiebreak)
    big = [(13, h), (13, s), (9, d), (7, c), (2, h)]
    assert _hand_rank(big) > _hand_rank(pair)


def test_discard_helpers_keep_made_combos() -> None:
    h, s, d, c = "♥", "♠", "♦", "♣"
    pair = [(4, h), (4, s), (9, d), (7, c), (2, h)]
    # worst three are the singletons 2, 7, 9 — the pair of 4s survives.
    discarded = sorted(pair[i][0] for i in _worst_indices(pair, 3))
    assert discarded == [2, 7, 9]
    assert _recommended_discards(pair) == 3
    straight = [(5, h), (6, s), (7, d), (8, c), (9, h)]
    assert _recommended_discards(straight) == 0  # stand pat on a made hand


def test_draw_poker_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s_en = get_scenario("draw_poker")
        assert s_en.title and s_en.title != "scenario.draw_poker.title"
        assert "card game" in s_en.title.lower()
        assert "play" in s_en.description.lower()
        set_locale("ja")
        s_ja = get_scenario("draw_poker")
        assert s_ja.title and s_ja.title != "scenario.draw_poker.title"
        assert "カードゲーム" in s_ja.title
    finally:
        set_locale(orig)
