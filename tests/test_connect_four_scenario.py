"""Tests for the connect_four board-game cartridge."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.connect_four import ConnectFourScenario
from llove.events import Event, EventKind
from llove.i18n import t


def test_connect_four_registered() -> None:
    assert SCENARIOS.get("connect_four") is ConnectFourScenario
    assert isinstance(get_scenario("connect_four"), ConnectFourScenario)


async def _run(scenario: ConnectFourScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _fixed_asker(value: str | None) -> Callable[..., Coroutine[Any, Any, str]]:
    """Asker that always returns ``value`` (or the default when None)."""

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        return default_id if value is None else value

    return asker


@pytest.mark.asyncio
async def test_default_branch_is_finite_and_terminates() -> None:
    seen = await _run(get_scenario("connect_four"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds
    # A terminal result narration must be reached (win / lose / draw).
    titles = [e.payload.get("title") for e in seen if e.kind == EventKind.NARRATION]
    assert t("scenario.connect_four.result_title") in titles
    # Hard cap: never more plies than cells on the board.
    moves = [e for e in seen if e.kind == EventKind.AUDIT]
    assert 0 < len(moves) <= 42


@pytest.mark.asyncio
async def test_scripted_default_asker_completes() -> None:
    s = ConnectFourScenario()
    s._asker = _fixed_asker(None)  # always take the offered default move.
    seen = await _run(s)
    titles = [e.payload.get("title") for e in seen if e.kind == EventKind.NARRATION]
    assert t("scenario.connect_four.result_title") in titles


@pytest.mark.asyncio
async def test_scripted_fixed_column_completes() -> None:
    s = ConnectFourScenario()
    s._asker = _fixed_asker("4")  # always aim for column 4 (falls back if full).
    seen = await _run(s)
    titles = [e.payload.get("title") for e in seen if e.kind == EventKind.NARRATION]
    assert t("scenario.connect_four.result_title") in titles


def test_connect_four_i18n_resolves() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("ja")
        s_ja = get_scenario("connect_four")
        assert s_ja.title != "scenario.connect_four.title"
        assert s_ja.description != "scenario.connect_four.description"
        assert "ボードゲーム" in s_ja.title
        set_locale("en")
        s_en = get_scenario("connect_four")
        assert s_en.title != "scenario.connect_four.title"
        assert "play" in s_en.description.lower()
    finally:
        set_locale(orig)
