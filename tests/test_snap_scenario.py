"""Tests for the Snap card-game scenario (interactive cartridge)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.snap import SnapScenario
from llove.events import Event, EventKind


def test_snap_registered() -> None:
    assert SCENARIOS.get("snap") is SnapScenario
    assert isinstance(get_scenario("snap"), SnapScenario)


async def _run(scenario: SnapScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _scripted_asker(move: str) -> Callable[..., Coroutine[Any, Any, str]]:
    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return move

    return asker


def _audit_events(seen: list[Event]) -> list[str]:
    return [str(e.payload.get("event")) for e in seen if e.kind == EventKind.AUDIT]


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    # No asker → deterministic default (``pass`` every turn). The run must be
    # finite, narrate, and declare a result.
    seen = await _run(get_scenario("snap"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    assert "game.end" in _audit_events(seen)


@pytest.mark.asyncio
async def test_bounded_flip_count() -> None:
    # A 16-card deck pops exactly one card per turn → far under the hard cap.
    s = SnapScenario()
    s._asker = _scripted_asker("snap")
    flips = [e for e in await _run(s) if e.payload.get("event") == "card.flip"]
    assert 0 < len(flips) <= 16


@pytest.mark.asyncio
@pytest.mark.parametrize("move", ["snap", "pass"])
async def test_scripted_asker_completes_and_narrates(move: str) -> None:
    s = SnapScenario()
    s._asker = _scripted_asker(move)
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)
    assert "game.end" in _audit_events(seen), move


@pytest.mark.asyncio
async def test_game_end_reports_scores() -> None:
    s = SnapScenario()
    s._asker = _scripted_asker("pass")
    seen = await _run(s)
    end = next(e for e in seen if e.payload.get("event") == "game.end")
    assert "you" in end.payload and "ai" in end.payload
    assert isinstance(end.payload["you"], int)
    assert isinstance(end.payload["ai"], int)


def test_snap_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s = get_scenario("snap")
        assert s.title and s.title != "scenario.snap.title"
        assert s.description and s.description != "scenario.snap.description"
        assert s.title.endswith("(card game)")
        assert "play" in s.description.lower()
        set_locale("ja")
        s_ja = get_scenario("snap")
        assert s_ja.title and s_ja.title != "scenario.snap.title"
        assert "スナップ" in s_ja.title
        assert "(カードゲーム)" in s_ja.title
    finally:
        set_locale(orig)
