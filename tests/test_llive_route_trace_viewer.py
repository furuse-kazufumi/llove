"""F25 (c) — RouteTraceViewer の単体テスト.

BWTDashboard と同じ哲学 (pure render 関数を直接テスト + widget API は
mount せずに API レベルだけ確認)。
"""

from __future__ import annotations

from llove.mcp.client import TimelineEvent
from llove.views.llive.route_trace_viewer import (
    MemoryAccess,
    RouteTrace,
    RouteTraceViewer,
    SubBlock,
    make_mock_route_trace_events,
    render_memory_access,
    render_subblock_bars,
    render_trace,
)

# ---------------------------------------------------------------------------
# RouteTrace.from_event — 防御的パース
# ---------------------------------------------------------------------------


def test_from_event_returns_trace_for_valid_payload() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="req-1",
        node_id="llive-1",
        event_type="route_trace",
        timestamp_utc="2026-05-14T08:30:00Z",
        metadata={
            "container": "adaptive_v1",
            "subblocks": [
                {"name": "pre_norm", "type": "pre_norm", "duration_ms": 0.12},
                {"name": "memory_read", "type": "memory_read", "duration_ms": 1.4},
            ],
            "memory_accesses": [
                {"op": "read", "layer": "semantic",
                 "hits": [{"id": "h1", "score": 0.83}]},
            ],
            "metrics": {"latency_ms": 2.12, "subblock_count": 2},
        },
    )
    trace = RouteTrace.from_event(ev)
    assert trace is not None
    assert trace.request_id == "req-1"
    assert trace.container == "adaptive_v1"
    assert len(trace.subblocks) == 2
    assert trace.subblocks[0].name == "pre_norm"
    assert trace.subblocks[1].duration_ms == 1.4
    assert len(trace.memory_accesses) == 1
    assert trace.memory_accesses[0].op == "read"
    assert trace.latency_ms == 2.12
    assert trace.subblock_count == 2


def test_from_event_returns_none_for_wrong_event_type() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={"subblocks": []},
    )
    assert RouteTrace.from_event(ev) is None


def test_from_event_tolerates_missing_metadata() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="r",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata={},
    )
    trace = RouteTrace.from_event(ev)
    assert trace is not None
    assert trace.subblocks == ()
    assert trace.memory_accesses == ()
    assert trace.latency_ms == 0.0


def test_from_event_skips_invalid_subblocks() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="r",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata={
            "subblocks": [
                "garbage",
                {"name": "good", "duration_ms": 1.0},
                {"name": "bad", "duration_ms": "not a number"},
            ],
        },
    )
    trace = RouteTrace.from_event(ev)
    assert trace is not None
    # "good" のみ通過 ("garbage" は dict でない、"bad" は float 変換失敗)
    assert len(trace.subblocks) == 1
    assert trace.subblocks[0].name == "good"


def test_from_event_handles_invalid_subblocks_type() -> None:
    """subblocks が list でなければ空タプルに."""
    ev = TimelineEvent(
        event_id="e1",
        task_id="r",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata={"subblocks": "not a list"},
    )
    trace = RouteTrace.from_event(ev)
    assert trace is not None
    assert trace.subblocks == ()


def test_from_event_parses_memory_access_with_hits() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="r",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata={
            "memory_accesses": [
                {"op": "read", "layer": "episodic",
                 "hits": [
                     {"id": "h1", "score": 0.5},
                     {"id": "h2", "score": 0.9},
                     {"id": "h3", "score": "bad"},  # 無視される
                 ]},
                {"op": "write", "layer": "episodic", "surprise": 0.42},
            ],
        },
    )
    trace = RouteTrace.from_event(ev)
    assert trace is not None
    assert len(trace.memory_accesses) == 2
    read_acc = trace.memory_accesses[0]
    assert read_acc.op == "read"
    assert len(read_acc.hits) == 2  # 不正なものはスキップ
    write_acc = trace.memory_accesses[1]
    assert write_acc.op == "write"
    assert write_acc.surprise == 0.42


def test_from_event_returns_none_when_metadata_is_not_dict() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="r",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata={"subblocks": [], "memory_accesses": []},
    )
    # metadata 自体は dict なので OK
    assert RouteTrace.from_event(ev) is not None


# ---------------------------------------------------------------------------
# render_subblock_bars
# ---------------------------------------------------------------------------


def test_subblock_bars_placeholder_for_empty() -> None:
    out = render_subblock_bars(())
    assert "(no subblocks)" in out


def test_subblock_bars_shows_percentage_and_duration() -> None:
    subs = (
        SubBlock(name="a", type="x", duration_ms=1.0),
        SubBlock(name="b", type="y", duration_ms=3.0),
    )
    out = render_subblock_bars(subs, bar_width=4)
    # a は 25%, b は 75%
    lines = out.splitlines()
    assert "25.0%" in lines[0]
    assert "75.0%" in lines[1]
    assert "1.00 ms" in lines[0]
    assert "3.00 ms" in lines[1]


def test_subblock_bars_handles_zero_total() -> None:
    """全部 0 ms でも crash しない."""
    subs = (
        SubBlock(name="a", type="x", duration_ms=0.0),
        SubBlock(name="b", type="y", duration_ms=0.0),
    )
    out = render_subblock_bars(subs)
    # 100% にしないように total fallback で 1.0 → 全 0% 表示
    assert "0.0%" in out
    assert "a" in out and "b" in out


# ---------------------------------------------------------------------------
# render_memory_access
# ---------------------------------------------------------------------------


def test_memory_access_placeholder_for_empty() -> None:
    out = render_memory_access(())
    assert "(no memory accesses)" in out


def test_memory_access_read_shows_hit_count_and_best_score() -> None:
    mems = (
        MemoryAccess(
            op="read",
            layer="semantic",
            hits=(("h1", 0.5), ("h2", 0.9)),
        ),
    )
    out = render_memory_access(mems)
    assert "hits=2" in out
    assert "0.900" in out  # best score


def test_memory_access_write_shows_surprise() -> None:
    mems = (
        MemoryAccess(op="write", layer="episodic", surprise=0.71),
    )
    out = render_memory_access(mems)
    assert "surprise=0.710" in out


def test_memory_access_read_with_no_hits() -> None:
    mems = (
        MemoryAccess(op="read", layer="semantic", hits=()),
    )
    out = render_memory_access(mems)
    assert "hits=0" in out


def test_memory_access_unknown_op_still_rendered() -> None:
    mems = (
        MemoryAccess(op="invalidate", layer="semantic"),
    )
    out = render_memory_access(mems)
    assert "invalidate" in out
    assert "semantic" in out


# ---------------------------------------------------------------------------
# render_trace
# ---------------------------------------------------------------------------


def test_render_trace_none_returns_placeholder() -> None:
    out = render_trace(None)
    assert "no route traces" in out


def test_render_trace_includes_request_id_and_latency() -> None:
    events = make_mock_route_trace_events(n=1)
    trace = RouteTrace.from_event(events[0])
    out = render_trace(trace)
    assert "Request:" in out
    assert "latency:" in out
    assert "Subblocks:" in out
    assert "Memory access:" in out


def test_render_trace_handles_missing_container() -> None:
    trace = RouteTrace(
        event_id="e1",
        request_id="r",
        timestamp_utc="x",
        container="",  # 空
    )
    out = render_trace(trace)
    assert "(unknown)" in out


# ---------------------------------------------------------------------------
# RouteTraceViewer widget API
# ---------------------------------------------------------------------------


def test_widget_starts_empty() -> None:
    w = RouteTraceViewer()
    assert w.trace_count() == 0
    assert w.latest() is None


def test_widget_feed_events_ingests_route_traces_only() -> None:
    w = RouteTraceViewer()
    events = [
        *make_mock_route_trace_events(n=3),
        TimelineEvent(
            event_id="other",
            task_id="t",
            node_id="n",
            event_type="bwt_summary",
            timestamp_utc="x",
            metadata={},
        ),
    ]
    added = w.feed_events(events)
    assert added == 3
    assert w.trace_count() == 3
    latest = w.latest()
    assert latest is not None
    assert latest.event_id.startswith("mock-trace-")


def test_widget_dedups_by_event_id() -> None:
    w = RouteTraceViewer()
    events = make_mock_route_trace_events(n=2)
    w.feed_events(events)
    added = w.feed_events(events)
    assert added == 0
    assert w.trace_count() == 2


def test_widget_clear_resets_state() -> None:
    w = RouteTraceViewer()
    w.feed_events(make_mock_route_trace_events(n=3))
    w.clear()
    assert w.trace_count() == 0
    assert w.latest() is None


def test_widget_skips_malformed_events() -> None:
    w = RouteTraceViewer()
    bad = TimelineEvent(
        event_id="bad-1",
        task_id="t",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata="not a dict",  # type: ignore[arg-type]
    )
    good = make_mock_route_trace_events(n=1)[0]
    added = w.feed_events([bad, good])
    assert added == 1


def test_widget_history_limit() -> None:
    """history パラメータで deque サイズが効く."""
    w = RouteTraceViewer(history=2)
    w.feed_events(make_mock_route_trace_events(n=5))
    # deque(maxlen=2) なので最新 2 件のみ保持される
    assert w.trace_count() == 2


# ---------------------------------------------------------------------------
# Mock fixture sanity
# ---------------------------------------------------------------------------


def test_mock_events_have_correct_event_type() -> None:
    events = make_mock_route_trace_events(n=3)
    assert len(events) == 3
    for ev in events:
        assert ev.event_type == "route_trace"
        assert "subblocks" in ev.metadata
        assert "memory_accesses" in ev.metadata


def test_mock_events_are_unique_by_event_id() -> None:
    events = make_mock_route_trace_events(n=5)
    ids = [ev.event_id for ev in events]
    assert len(set(ids)) == len(ids)
