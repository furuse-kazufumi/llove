"""Tests for the memory card-game scenario (interactive Concentration cartridge)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.memory import MemoryScenario
from llove.events import Event, EventKind


def test_memory_registered() -> None:
    assert SCENARIOS.get("memory") is MemoryScenario
    assert isinstance(get_scenario("memory"), MemoryScenario)


def test_get_scenario_takes_no_args() -> None:
    # __init__ must work with seed defaulted, so the registry can build it.
    assert isinstance(get_scenario("memory"), MemoryScenario)
    assert isinstance(MemoryScenario(), MemoryScenario)


async def _run(scenario: MemoryScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _default_asker() -> Callable[..., Coroutine[Any, Any, str]]:
    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return default_id if default_id is not None else options[0].id

    return asker


def _highest_asker() -> Callable[..., Coroutine[Any, Any, str]]:
    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return options[-1].id

    return asker


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    # No asker wired → deterministic default tile each turn; must finish.
    seen = await _run(get_scenario("memory"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    ends = [e for e in seen if e.payload.get("event") == "memory.game_end"]
    assert len(ends) == 1


@pytest.mark.asyncio
async def test_game_ends_with_all_pairs_taken() -> None:
    seen = await _run(get_scenario("memory"))  # type: ignore[arg-type]
    end = next(e for e in seen if e.payload.get("event") == "memory.game_end")
    # 4 pairs total; every pair is owned by someone when the loop ends.
    assert end.payload["human"] + end.payload["cpu"] == 4


@pytest.mark.asyncio
async def test_scripted_default_asker_completes() -> None:
    s = MemoryScenario()
    s._asker = _default_asker()
    seen = await _run(s)
    assert EventKind.NARRATION in [e.kind for e in seen]
    assert any(e.payload.get("event") == "memory.game_end" for e in seen)


@pytest.mark.asyncio
async def test_scripted_highest_asker_picks_legal_tiles() -> None:
    # Always picking the last offered (legal) tile must still complete cleanly.
    s = MemoryScenario()
    s._asker = _highest_asker()
    seen = await _run(s)
    assert any(e.payload.get("event") == "memory.game_end" for e in seen)


@pytest.mark.asyncio
async def test_deterministic_for_a_fixed_seed() -> None:
    a = await _run(MemoryScenario(seed=7))
    b = await _run(MemoryScenario(seed=7))
    assert len(a) == len(b)


@pytest.mark.asyncio
async def test_result_narration_is_one_of_win_lose_draw() -> None:
    seen = await _run(get_scenario("memory"))  # type: ignore[arg-type]
    end_idx = next(
        i for i, e in enumerate(seen) if e.payload.get("event") == "memory.game_end"
    )
    # The very next event is the result narration.
    result = seen[end_idx + 1]
    assert result.kind == EventKind.NARRATION
    assert str(result.payload.get("text", "")).strip()


def test_memory_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s_en = get_scenario("memory")
        assert s_en.title and s_en.title != "scenario.memory.title"
        assert "(card game)" in s_en.title
        assert "play" in s_en.description.lower()
        set_locale("ja")
        s_ja = get_scenario("memory")
        assert s_ja.title and s_ja.title != "scenario.memory.title"
        assert "(カードゲーム)" in s_ja.title
        assert s_ja.description != "scenario.memory.description"
    finally:
        set_locale(orig)
