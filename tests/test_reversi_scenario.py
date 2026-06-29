"""Tests for the reversi 6x6 board-game cartridge (interactive, offline)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.reversi import ReversiScenario
from llove.events import Event, EventKind


def test_reversi_registered() -> None:
    assert SCENARIOS.get("reversi") is ReversiScenario
    assert isinstance(get_scenario("reversi"), ReversiScenario)


async def _run(scenario: ReversiScenario) -> list[Event]:
    scenario.default_pause = 0.0
    out: list[Event] = []
    async for ev in scenario.events():
        out.append(ev)
        # Safety net: the engine is hard-capped, so a runaway loop is a bug.
        assert len(out) < 5000, "reversi.events() did not terminate"
    return out


def _asker(pick: Callable[[list[Any], str | None], str]) -> Callable[..., Coroutine[Any, Any, str]]:
    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return pick(options, default_id)

    return asker


def _game_end(events: list[Event]) -> dict[str, Any]:
    ends = [e.payload for e in events if e.payload.get("event") == "reversi.game_end"]
    assert ends, "no reversi.game_end audit event was emitted"
    return ends[-1]


@pytest.mark.asyncio
async def test_default_branch_completes_with_narration() -> None:
    # No asker wired → deterministic default move every turn; the game still
    # plays itself to a final result.
    seen = await _run(get_scenario("reversi"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    end = _game_end(seen)
    # Disc conservation: a 6x6 board holds at most 36 discs.
    assert 0 <= end["black"] + end["white"] <= _SIZE_TOTAL


@pytest.mark.asyncio
async def test_scripted_asker_default_completes() -> None:
    s = ReversiScenario()
    s._asker = _asker(lambda opts, default: default if default is not None else opts[0].id)
    seen = await _run(s)
    assert any(e.kind == EventKind.NARRATION for e in seen)
    _game_end(seen)


@pytest.mark.asyncio
async def test_scripted_asker_last_move_completes() -> None:
    # Always pick the *last* presented legal move — a different (still legal)
    # path than the default — and confirm the game still terminates cleanly.
    s = ReversiScenario()
    s._asker = _asker(lambda opts, default: opts[-1].id)
    seen = await _run(s)
    _game_end(seen)


@pytest.mark.asyncio
async def test_every_audit_move_is_legal_and_terminates() -> None:
    seen = await _run(get_scenario("reversi"))  # type: ignore[arg-type]
    moves = [e.payload for e in seen if e.payload.get("event") == "reversi.move"]
    # A reversi move must always flip at least one opponent disc.
    assert moves, "no moves were played"
    assert all(int(m["flips"]) >= 1 for m in moves)


@pytest.mark.asyncio
async def test_en_locale_resolves_every_referenced_key() -> None:
    # Under en, no narration text/title should still be a raw i18n key — that
    # would mean a key referenced by the scenario is missing from the catalog.
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        seen = await _run(get_scenario("reversi"))  # type: ignore[arg-type]
        for ev in seen:
            if ev.kind != EventKind.NARRATION:
                continue
            text = str(ev.payload.get("text", ""))
            title = str(ev.payload.get("title", ""))
            assert "scenario.reversi." not in text
            assert "scenario.reversi." not in title
    finally:
        set_locale(orig)


def test_i18n_title_and_description_resolve_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s_en = get_scenario("reversi")
        assert s_en.title and s_en.title != "scenario.reversi.title"
        assert "board game" in s_en.title.lower()
        assert "play" in s_en.description.lower()
        set_locale("ja")
        s_ja = get_scenario("reversi")
        assert s_ja.title and s_ja.title != "scenario.reversi.title"
        assert "ボードゲーム" in s_ja.title
        assert s_ja.description != "scenario.reversi.description"
    finally:
        set_locale(orig)


# 6x6 board → 36 cells total (used for the disc-conservation assertion).
_SIZE_TOTAL = 36
