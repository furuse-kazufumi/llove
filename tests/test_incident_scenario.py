"""Tests for the incident branching scenario (the flagship interactive demo)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.incident import IncidentScenario
from llove.events import Event, EventKind
from llove.term.choice import ChoiceOption


def test_incident_registered() -> None:
    assert SCENARIOS.get("incident") is IncidentScenario
    assert isinstance(get_scenario("incident"), IncidentScenario)


async def _run(scenario: IncidentScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _scripted_asker(
    answers: list[str],
) -> Callable[..., Coroutine[Any, Any, str]]:
    state = {"i": 0}

    async def asker(prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
        a = answers[state["i"]]
        state["i"] += 1
        return a

    return asker


@pytest.mark.asyncio
async def test_default_branch_is_explain_apply_fix() -> None:
    # No asker → deterministic default path (explain → apply_fix).
    seen = await _run(get_scenario("incident"))  # type: ignore[arg-type]
    kinds = [e.kind for e in seen]
    assert EventKind.SPC_ALARM in kinds  # the initial CUSUM alarm
    assert EventKind.LLM_CALL in kinds  # explain branch invokes the LLM
    assert EventKind.NARRATION in kinds
    assert EventKind.AUDIT in kinds


@pytest.mark.asyncio
async def test_explain_branch_emits_exactly_one_llm_call() -> None:
    s = IncidentScenario()
    s._asker = _scripted_asker(["explain", "apply_fix"])
    kinds = [e.kind for e in await _run(s)]
    assert kinds.count(EventKind.LLM_CALL) == 1


@pytest.mark.asyncio
async def test_observe_branch_escalates_to_second_alarm() -> None:
    s = IncidentScenario()
    s._asker = _scripted_asker(["observe"])
    kinds = [e.kind for e in await _run(s)]
    assert kinds.count(EventKind.SPC_ALARM) >= 2  # initial + escalated
    assert EventKind.LLM_CALL not in kinds  # observing never calls the LLM


@pytest.mark.asyncio
async def test_quarantine_branch_records_quarantine_audit() -> None:
    s = IncidentScenario()
    s._asker = _scripted_asker(["quarantine"])
    seen = await _run(s)
    audit_events = [e.payload.get("event") for e in seen if e.kind == EventKind.AUDIT]
    assert "line.quarantine" in audit_events
    assert "line.quarantine_confirmed" in audit_events
    assert not any(e.kind == EventKind.LLM_CALL for e in seen)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answers",
    [
        ["explain", "apply_fix"],
        ["explain", "rollback"],
        ["explain", "escalate"],
        ["observe"],
        ["quarantine"],
    ],
)
async def test_every_branch_emits_narration(answers: list[str]) -> None:
    s = IncidentScenario()
    s._asker = _scripted_asker(answers)
    kinds = [e.kind for e in await _run(s)]
    assert EventKind.NARRATION in kinds, answers


def test_incident_i18n_resolves_under_en_and_ja() -> None:
    from llove.i18n import active_locale, set_locale

    orig = active_locale()
    try:
        set_locale("en")
        s = get_scenario("incident")
        assert s.title and s.title != "scenario.incident.title"
        assert "branch" in s.description.lower()
        set_locale("ja")
        s_ja = get_scenario("incident")
        assert s_ja.title and s_ja.title != "scenario.incident.title"
        assert "分岐" in s_ja.title
    finally:
        set_locale(orig)


@pytest.mark.asyncio
async def test_chosen_option_is_narrated() -> None:
    s = IncidentScenario()
    s._asker = _scripted_asker(["observe"])
    seen = await _run(s)
    narrations = [
        str(e.payload.get("text", "")) for e in seen if e.kind == EventKind.NARRATION
    ]
    # The "You chose: <label>" narration should carry the observe label.
    assert any("観測" in n or "observ" in n.lower() for n in narrations)
