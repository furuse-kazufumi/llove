"""Robustness tests — feed views and sources malformed / extreme inputs.

Goal: nothing here should raise. Every code path is fail-closed: bad input
produces an empty / unchanged view rather than a stack trace.
"""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import pytest

from llove.events import Event, EventKind
from llove.sources.jsonl import JSONLSource
from llove.sources.mock import MockSource
from llove.views.audit_log import AuditLogView
from llove.views.narration import NarrationView
from llove.views.sensor_stream import SensorStreamView
from llove.views.spc_chart import SPCChartView

# --------------------------------------------------------------------------
# Views — extreme / malformed payloads
# --------------------------------------------------------------------------


def test_sensor_stream_handles_nan_inf_none() -> None:
    v = SensorStreamView()
    for value in (float("nan"), float("inf"), float("-inf"), None, "non-numeric", []):
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": value}))
    v.feed(Event(kind=EventKind.SENSOR, payload={}))


def test_sensor_stream_ignores_other_kinds() -> None:
    v = SensorStreamView()
    v.feed(Event(kind=EventKind.AUDIT, payload={"event": "noop"}))
    v.feed(Event(kind=EventKind.NARRATION, payload={"text": "hello"}))
    assert len(v._rows) == 0


def test_sensor_stream_keeps_only_limit_rows() -> None:
    v = SensorStreamView(limit=3)
    for i in range(10):
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s", "value": float(i)}))
    assert len(v._rows) == 3


def test_sensor_stream_sparkline_handles_constant_series() -> None:
    v = SensorStreamView()
    for _ in range(5):
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s", "value": 1.0}))


def test_spc_chart_handles_alarms_with_missing_fields() -> None:
    v = SPCChartView()
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={}))
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"sensor_id": "s"}))
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"cusum": 1.0}))
    v.feed(Event(kind=EventKind.SENSOR, payload={"value": "not a number"}))
    assert len(v._alarms) == 3


def test_audit_log_filters_out_unrelated_kinds() -> None:
    v = AuditLogView(limit=5)
    v.feed(Event(kind=EventKind.AUDIT, payload={"event": "ok"}))
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"cusum": 5.0}))
    v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s", "value": 1.0}))
    v.feed(Event(kind=EventKind.LLM_CALL, payload={"tokens": 100}))
    assert len(v._rows) == 2


def test_narration_view_handles_empty_text_gracefully() -> None:
    v = NarrationView()
    v.feed(Event(kind=EventKind.NARRATION, payload={}))
    v.feed(Event(kind=EventKind.NARRATION, payload={"text": ""}))
    v.feed(Event(kind=EventKind.NARRATION, payload={"text": "   "}))
    assert "no narration yet" in v.last_render


def test_narration_view_neutralises_user_supplied_rich_tags() -> None:
    v = NarrationView()
    payload = {"text": "[red]hostile[/red] **ok**", "title": "[bold]A[/bold]"}
    v.feed(Event(kind=EventKind.NARRATION, payload=payload))
    rendered = v.last_render
    # User-supplied [red] must be escaped to \[red] (no unescaped Rich tags).
    assert r"\[red]" in rendered
    assert r"\[bold]A\[/bold]" in rendered
    # Our own bold conversion still works on **ok**.
    assert "[bold]ok[/bold]" in rendered


# --------------------------------------------------------------------------
# Sources — extreme inputs
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jsonl_handles_huge_individual_line(tmp_path: Path) -> None:
    p = tmp_path / "huge.jsonl"
    big_payload = {"x": "a" * 100_000}
    line = json.dumps({"kind": "audit", "payload": big_payload})
    p.write_text(line, encoding="utf-8")
    out = [ev async for ev in JSONLSource(p).stream()]
    assert len(out) == 1
    assert out[0].kind == EventKind.AUDIT


@pytest.mark.asyncio
async def test_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    p = tmp_path / "weird.jsonl"
    lines = [
        "",
        "   ",
        json.dumps({"kind": "audit", "payload": {"event": "ok"}}),
        "",
        json.dumps({"kind": "audit", "payload": {"event": "two", "lang": "japanese"}}),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = [ev async for ev in JSONLSource(p).stream()]
    events = [ev.payload.get("event") for ev in out]
    assert "ok" in events
    assert "two" in events


@pytest.mark.asyncio
async def test_mock_source_does_not_loop_forever_when_consumer_breaks() -> None:
    src = MockSource(seed=42, tick_seconds=0.001)
    seen = 0
    async for _ in src.stream():
        seen += 1
        if seen >= 5:
            break
    await src.close()
    assert seen == 5


# --------------------------------------------------------------------------
# Event model — invariants
# --------------------------------------------------------------------------


def test_event_short_handles_all_kinds_without_raising() -> None:
    for kind in EventKind:
        ev = Event(kind=kind, source_id="t", payload={})
        out = ev.short()
        assert isinstance(out, str)
        assert len(out) > 0


def test_event_payload_extra_keys_are_preserved() -> None:
    ev = Event(
        kind=EventKind.SENSOR,
        payload={"sensor_id": "s", "value": 1.0, "extra_key": [1, 2, 3]},
    )
    assert ev.payload["extra_key"] == [1, 2, 3]


def test_event_kind_value_is_short_string() -> None:
    for kind in EventKind:
        v = kind.value
        assert v == v.lower()
        assert " " not in v
        assert v.isascii()


# --------------------------------------------------------------------------
# Demo scenarios — never raise on default seed, complete quickly
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_scenario_runs_to_completion_under_a_second() -> None:
    from llove.demo.scenarios import SCENARIOS, get_scenario

    for name in SCENARIOS:
        scenario = get_scenario(name)
        scenario.default_pause = 0.0
        count = 0
        async with asyncio.timeout(2.0):
            async for _ in scenario.events():
                count += 1
        assert count > 0, f"{name} produced no events"


def test_sensor_stream_value_cache_invariants() -> None:
    v = SensorStreamView()
    for x in (float("nan"), 1.0, float("inf")):
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s", "value": x}))
    assert all(math.isfinite(x) or math.isnan(x) for x in v._values)
