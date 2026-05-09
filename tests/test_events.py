"""Tests for the unified Event model."""
from __future__ import annotations

from llove.events import Event, EventKind


def test_event_short_for_sensor() -> None:
    ev = Event(
        kind=EventKind.SENSOR,
        source_id="t",
        payload={"sensor_id": "s1", "value": 12.3, "quality": "good"},
    )
    out = ev.short()
    assert "s1=12.3" in out
    assert "sensor" in out


def test_event_short_for_alarm() -> None:
    ev = Event(
        kind=EventKind.SPC_ALARM,
        source_id="t",
        payload={"sensor_id": "s1", "cusum": 9.4, "threshold": 5.0},
    )
    out = ev.short()
    assert "ALARM" in out
    assert "cusum=9.4" in out


def test_event_short_for_audit() -> None:
    ev = Event(
        kind=EventKind.AUDIT,
        source_id="t",
        payload={"event": "firewall.allow", "layer": "L2"},
    )
    assert "firewall.allow" in ev.short()


def test_event_short_for_llm_call() -> None:
    ev = Event(
        kind=EventKind.LLM_CALL,
        source_id="t",
        payload={"tokens": 200, "latency_ms": 350},
    )
    out = ev.short()
    assert "tokens=200" in out
    assert "latency=350ms" in out


def test_event_extra_payload_keys_allowed() -> None:
    ev = Event(kind=EventKind.INFO, payload={"foo": 1, "bar": "baz"})
    assert ev.payload == {"foo": 1, "bar": "baz"}
