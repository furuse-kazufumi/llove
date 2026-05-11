"""Tests for TaskGraphView + TimelineView — Phase 0c minimum research views."""

from __future__ import annotations

from datetime import UTC, datetime

from llove.events import Event, EventKind
from llove.views.task_graph import TaskGraphView
from llove.views.timeline import TimelineView

# ---------------------------------------------------------------------------
# TaskGraphView
# ---------------------------------------------------------------------------


def _trace_span(**payload: object) -> Event:
    return Event(kind=EventKind.TRACE_SPAN, payload=dict(payload))


class TestTaskGraphView:
    def test_empty_by_default(self) -> None:
        v = TaskGraphView()
        assert v._status == {}
        assert v._task_nodes == []

    def test_set_graph_initialises_all_pending(self) -> None:
        v = TaskGraphView()
        v.set_graph(
            [
                {"id": "a", "kind": "agent", "target": "lit", "depends_on": ()},
                {"id": "b", "kind": "agent", "target": "hyp", "depends_on": ("a",)},
                {"id": "c", "kind": "agent", "target": "rev", "depends_on": ("b",)},
            ]
        )
        assert v._status == {"a": "pending", "b": "pending", "c": "pending"}

    def test_duplicate_id_rejected(self) -> None:
        v = TaskGraphView()
        try:
            v.set_graph([{"id": "a"}, {"id": "a"}])
        except ValueError as exc:
            assert "duplicate" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    def test_missing_id_rejected(self) -> None:
        v = TaskGraphView()
        try:
            v.set_graph([{"target": "x"}])
        except ValueError as exc:
            assert "id" in str(exc)
        else:
            raise AssertionError("expected ValueError")

    def test_update_status_changes_state(self) -> None:
        v = TaskGraphView()
        v.set_graph([{"id": "a"}, {"id": "b", "depends_on": ("a",)}])
        v.update_status("a", "running")
        v.update_status("a", "done")
        v.update_status("b", "running")
        assert v._status == {"a": "done", "b": "running"}

    def test_update_status_ignores_unknown_node(self) -> None:
        v = TaskGraphView()
        v.set_graph([{"id": "a"}])
        v.update_status("ghost", "running")  # silently ignored
        assert v._status == {"a": "pending"}

    def test_update_status_ignores_unknown_status(self) -> None:
        v = TaskGraphView()
        v.set_graph([{"id": "a"}])
        v.update_status("a", "exploded")  # unknown -> no-op
        assert v._status == {"a": "pending"}

    def test_feed_trace_span_updates_status(self) -> None:
        v = TaskGraphView()
        v.set_graph([{"id": "a"}, {"id": "b", "depends_on": ("a",)}])
        v.feed(_trace_span(node_id="a", status="running"))
        v.feed(_trace_span(node_id="a", status="done"))
        v.feed(_trace_span(node_id="b", status="running"))
        assert v._status == {"a": "done", "b": "running"}

    def test_feed_ignores_non_trace_events(self) -> None:
        v = TaskGraphView()
        v.set_graph([{"id": "a"}])
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "x", "value": 1}))
        v.feed(Event(kind=EventKind.AUDIT, payload={"event": "x"}))
        assert v._status == {"a": "pending"}

    def test_feed_garbage_payload_no_crash(self) -> None:
        v = TaskGraphView()
        v.set_graph([{"id": "a"}])
        v.feed(_trace_span())  # no node_id / status
        v.feed(_trace_span(node_id=123, status="running"))  # wrong type
        v.feed(_trace_span(node_id="a", status=None))
        # passes if no exception raised
        assert v._status == {"a": "pending"}

    def test_layers_linear(self) -> None:
        v = TaskGraphView()
        v.set_graph(
            [
                {"id": "a"},
                {"id": "b", "depends_on": ("a",)},
                {"id": "c", "depends_on": ("b",)},
            ]
        )
        layers = v._layers()
        assert layers == [["a"], ["b"], ["c"]]

    def test_layers_fan_out_in(self) -> None:
        v = TaskGraphView()
        v.set_graph(
            [
                {"id": "root"},
                {"id": "l", "depends_on": ("root",)},
                {"id": "r", "depends_on": ("root",)},
                {"id": "join", "depends_on": ("l", "r")},
            ]
        )
        layers = v._layers()
        assert layers[0] == ["root"]
        assert set(layers[1]) == {"l", "r"}
        assert layers[-1] == ["join"]

    def test_layers_handle_cycle_gracefully(self) -> None:
        v = TaskGraphView()
        v.set_graph(
            [
                {"id": "a", "depends_on": ("b",)},
                {"id": "b", "depends_on": ("a",)},
            ]
        )
        # render must not raise; both nodes surface in a final cycle layer
        layers = v._layers()
        flat = [nid for layer in layers for nid in layer]
        assert sorted(flat) == ["a", "b"]


# ---------------------------------------------------------------------------
# TimelineView
# ---------------------------------------------------------------------------


class TestTimelineView:
    def test_empty_by_default(self) -> None:
        v = TimelineView()
        assert len(v._rows) == 0
        assert v._count == 0

    def test_appends_trace_spans(self) -> None:
        v = TimelineView(limit=10)
        v.feed(_trace_span(seq=0, trace_kind="agent.run", actor="agent.lit"))
        v.feed(_trace_span(seq=1, trace_kind="tool.call", actor="search", duration_ms=42))
        assert len(v._rows) == 2
        assert v._count == 2

    def test_ignores_non_trace_events(self) -> None:
        v = TimelineView()
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "x", "value": 1}))
        v.feed(Event(kind=EventKind.AUDIT, payload={"event": "noop"}))
        assert len(v._rows) == 0
        assert v._count == 0

    def test_respects_limit(self) -> None:
        v = TimelineView(limit=3)
        for i in range(5):
            v.feed(_trace_span(seq=i, trace_kind="tool.call", actor=f"t{i}"))
        assert len(v._rows) == 3
        # the rolling tail kept the last three (seq 2, 3, 4)
        joined = "\n".join(v._rows)
        assert "t4" in joined
        assert "t0" not in joined
        # but the running counter is over the full feed
        assert v._count == 5

    def test_garbage_payload_no_crash(self) -> None:
        v = TimelineView()
        v.feed(_trace_span())  # everything missing
        v.feed(_trace_span(seq="not-int", trace_kind=None))
        v.feed(_trace_span(seq=3, duration_ms=-1))  # negative duration ignored
        # passes if no exception raised
        assert len(v._rows) == 3

    def test_renders_node_id_when_present(self) -> None:
        v = TimelineView()
        v.feed(
            _trace_span(seq=0, trace_kind="agent.run", actor="planner", node_id="b"),
        )
        joined = "\n".join(v._rows)
        assert "[b]" in joined

    def test_ts_format(self) -> None:
        v = TimelineView()
        ev = Event(
            kind=EventKind.TRACE_SPAN,
            ts=datetime(2026, 5, 11, 12, 34, 56, tzinfo=UTC),
            payload={"seq": 0, "trace_kind": "tool.call", "actor": "t"},
        )
        v.feed(ev)
        joined = "\n".join(v._rows)
        assert "12:34:56" in joined
