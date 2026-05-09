"""Tests for view widgets — exercise the feed() path without spinning a TUI."""
from __future__ import annotations

from llove.events import Event, EventKind
from llove.views.audit_log import AuditLogView
from llove.views.sensor_stream import SensorStreamView
from llove.views.spc_chart import SPCChartView


def test_sensor_stream_accepts_sensor_event_and_ignores_others() -> None:
    v = SensorStreamView(limit=5)
    v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": 12.5}))
    v.feed(Event(kind=EventKind.AUDIT, payload={"event": "noop"}))  # ignored
    assert len(v._rows) == 1


def test_sensor_stream_handles_garbage_payload_without_crash() -> None:
    v = SensorStreamView()
    v.feed(Event(kind=EventKind.SENSOR, payload={"value": "not a number"}))
    v.feed(Event(kind=EventKind.SENSOR, payload={}))
    # No assertion; the test passes if no exception was raised.


def test_spc_chart_records_alarms() -> None:
    v = SPCChartView(limit=2)
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"sensor_id": "s1", "cusum": 7.0}))
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"sensor_id": "s1", "cusum": 9.0}))
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"sensor_id": "s1", "cusum": 11.0}))
    # limit=2 means we kept only the most recent two.
    assert len(v._alarms) == 2


def test_audit_log_filters_to_interesting_kinds() -> None:
    v = AuditLogView(limit=10)
    v.feed(Event(kind=EventKind.AUDIT, payload={"event": "a"}))
    v.feed(Event(kind=EventKind.LLM_CALL, payload={"tokens": 100, "latency_ms": 50}))
    v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": 1}))  # ignored
    v.feed(Event(kind=EventKind.SPC_ALARM, payload={"sensor_id": "s1", "cusum": 5}))  # ignored
    assert len(v._rows) == 2
