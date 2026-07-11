"""Smoke tests for every demo scenario."""

from __future__ import annotations

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.events import EventKind


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(SCENARIOS))
async def test_scenario_yields_events(name: str, llm_backends_offline) -> None:
    scenario = get_scenario(name)
    if name == "backends":
        # backends now performs real LLM calls — keep the smoke test offline.
        llm_backends_offline(scenario)
    # Override pause to make the test fast.
    scenario.default_pause = 0.0
    seen = []
    async for ev in scenario.events():
        seen.append(ev)
    assert len(seen) > 0
    # Every scenario must include at least one narration event so users see
    # what is happening in the dedicated pane.
    assert any(e.kind == EventKind.NARRATION for e in seen), f"{name} produced no narration events"


def test_get_scenario_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        get_scenario("definitely-not-a-scenario")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["firewall", "scada", "audit"])
async def test_scenario_includes_audit_events(name: str) -> None:
    """A few representative scenarios should leave traceable audit entries."""
    scenario = get_scenario(name)
    scenario.default_pause = 0.0
    kinds = []
    async for ev in scenario.events():
        kinds.append(ev.kind)
    assert EventKind.AUDIT in kinds, f"{name} did not emit audit events"


@pytest.mark.asyncio
async def test_rag_scenario_includes_rag_hits() -> None:
    scenario = get_scenario("rag")
    scenario.default_pause = 0.0
    kinds = []
    async for ev in scenario.events():
        kinds.append(ev.kind)
    assert EventKind.RAG_HIT in kinds


@pytest.mark.asyncio
async def test_backends_scenario_includes_llm_calls() -> None:
    scenario = get_scenario("backends")
    scenario.default_pause = 0.0
    kinds = []
    async for ev in scenario.events():
        kinds.append(ev.kind)
    assert kinds.count(EventKind.LLM_CALL) >= 3


@pytest.mark.asyncio
async def test_scada_scenario_emits_alarm() -> None:
    scenario = get_scenario("scada")
    scenario.default_pause = 0.0
    kinds = []
    async for ev in scenario.events():
        kinds.append(ev.kind)
    assert EventKind.SPC_ALARM in kinds
    assert EventKind.LLM_CALL in kinds


def test_narration_view_renders_lite_markdown() -> None:
    from llove.events import Event
    from llove.events import EventKind as EK
    from llove.views.narration import NarrationView

    v = NarrationView()
    v.feed(Event(kind=EK.NARRATION, payload={"text": "hello **world** and `code`", "title": "T"}))
    rendered = v.last_render
    assert "[bold]world[/bold]" in rendered
    assert "[reverse]code[/reverse]" in rendered


def test_narration_view_ignores_other_kinds() -> None:
    from llove.events import Event
    from llove.events import EventKind as EK
    from llove.views.narration import NarrationView

    v = NarrationView()
    v.feed(Event(kind=EK.SENSOR, payload={"sensor_id": "x", "value": 1.0}))
    assert "no narration yet" in v.last_render
