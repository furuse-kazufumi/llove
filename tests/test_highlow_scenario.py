"""Smoke + branch + i18n tests for the highlow (Higher-Lower) scenario."""

from __future__ import annotations

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.highlow import HighLowScenario
from llove.events import EventKind
from llove.i18n import active_locale, set_locale
from llove.term.choice import ChoiceOption


def test_highlow_registered() -> None:
    assert SCENARIOS.get("highlow") is HighLowScenario
    scenario = get_scenario("highlow")  # no-arg construction (seed defaulted)
    assert isinstance(scenario, HighLowScenario)


@pytest.mark.asyncio
async def test_highlow_default_branch_completes() -> None:
    """No asker wired → deterministic default branch, finite, with narration."""
    scenario = get_scenario("highlow")
    scenario.default_pause = 0.0
    seen = []
    async for ev in scenario.events():
        seen.append(ev)
    assert 0 < len(seen) < 500  # bounded → terminates
    assert any(e.kind == EventKind.NARRATION for e in seen)
    assert any(e.kind == EventKind.AUDIT for e in seen)
    # The final event is the result narration.
    assert seen[-1].kind == EventKind.NARRATION


@pytest.mark.asyncio
@pytest.mark.parametrize("forced", ["higher", "lower"])
async def test_highlow_scripted_asker_completes(forced: str) -> None:
    """A scripted asker that always returns one move still completes."""
    scenario = HighLowScenario(seed=7)
    scenario.default_pause = 0.0

    async def asker(
        prompt: str,
        options: list[ChoiceOption],
        *,
        default_id: str | None = None,
    ) -> str:
        assert {o.id for o in options} == {"higher", "lower"}
        return forced

    scenario._asker = asker
    kinds = [ev.kind async for ev in scenario.events()]
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds


def test_highlow_i18n_title_description() -> None:
    """title/description resolve to real strings (not the raw i18n key)."""
    saved = active_locale()
    try:
        for loc in ("ja", "en"):
            set_locale(loc)
            scenario = get_scenario("highlow")
            assert scenario.title != "scenario.highlow.title"
            assert scenario.description != "scenario.highlow.description"
            assert scenario.title  # non-empty
    finally:
        set_locale(saved)
