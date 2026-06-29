"""Tests for the triage branching scenario (second interactive cartridge)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.triage import TriageScenario
from llove.events import Event, EventKind


def test_triage_registered() -> None:
    assert SCENARIOS.get("triage") is TriageScenario
    assert isinstance(get_scenario("triage"), TriageScenario)


async def _run(scenario: TriageScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _scripted_asker(answers: list[str]) -> Callable[..., Coroutine[Any, Any, str]]:
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        a = answers[state["i"]]
        state["i"] += 1
        return a

    return asker


@pytest.mark.asyncio
async def test_default_branch_is_llm_send() -> None:
    seen = await _run(get_scenario("triage"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.RAG_HIT in kinds  # always retrieves first
    assert EventKind.LLM_CALL in kinds  # default path synthesises
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds


@pytest.mark.asyncio
async def test_kb_branch_has_no_llm_call() -> None:
    s = TriageScenario()
    s._asker = _scripted_asker(["kb"])
    seen = await _run(s)
    assert not any(e.kind == EventKind.LLM_CALL for e in seen)
    events = [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]
    assert "answer.from_kb" in events


@pytest.mark.asyncio
async def test_llm_branch_then_cite() -> None:
    s = TriageScenario()
    s._asker = _scripted_asker(["llm", "cite"])
    seen = await _run(s)
    assert any(e.kind == EventKind.LLM_CALL for e in seen)
    events = [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]
    assert "answer.with_citation" in events


@pytest.mark.asyncio
async def test_escalate_branch_routes_to_human() -> None:
    s = TriageScenario()
    s._asker = _scripted_asker(["escalate"])
    seen = await _run(s)
    assert not any(e.kind == EventKind.LLM_CALL for e in seen)
    events = [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]
    assert "ticket.escalate" in events


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answers",
    [["kb"], ["llm", "send"], ["llm", "cite"], ["llm", "escalate"], ["escalate"]],
)
async def test_every_branch_emits_narration(answers: list[str]) -> None:
    s = TriageScenario()
    s._asker = _scripted_asker(answers)
    kinds = [e.kind for e in await _run(s)]
    assert EventKind.NARRATION in kinds, answers


def test_triage_i18n_resolves() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("ja")
        s = get_scenario("triage")
        assert "分岐" in s.title
        set_locale("en")
        s_en = get_scenario("triage")
        assert "branch" in s_en.description.lower()
    finally:
        set_locale(orig)
