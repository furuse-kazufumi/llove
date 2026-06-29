"""F25 / M8.1 — CognitiveMeshPanel skeleton + dispatch 配線テスト."""

from __future__ import annotations

from llove.mcp.client import TimelineEvent
from llove.views.llive.cognitive_mesh_panel import (
    COG_EVENT_TYPES,
    CogEntry,
    CognitiveMeshPanel,
    make_mock_cog_events,
    render_panel,
)
from llove.views.llive.dispatch import (
    KNOWN_EVENT_TYPES,
    DispatchResult,
    dispatch_events,
)


def test_cog_event_types_in_known() -> None:
    """dispatch の既知 event_type 集合に cog 3 種が含まれる."""
    assert "cog_proactive_utterance" in KNOWN_EVENT_TYPES
    assert "cog_risk_alert" in KNOWN_EVENT_TYPES
    assert "cog_quarantine_pending" in KNOWN_EVENT_TYPES
    assert COG_EVENT_TYPES.issubset(KNOWN_EVENT_TYPES)


def test_cog_entry_from_proactive_event() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="",
        node_id="",
        event_type="cog_proactive_utterance",
        timestamp_utc="2026-05-19T10:00:00+09:00",
        metadata={"content": "build done", "mode": "timer", "gift_value": 0.75},
    )
    entry = CogEntry.from_event(ev)
    assert entry is not None
    assert entry.kind == "proactive"
    assert "build done" in entry.summary
    assert "timer" in entry.summary
    assert "0.75" in entry.summary


def test_cog_entry_from_risk_event() -> None:
    ev = TimelineEvent(
        event_id="e2",
        task_id="",
        node_id="",
        event_type="cog_risk_alert",
        timestamp_utc="2026-05-19T10:00:00+09:00",
        metadata={"model_name": "critical_logs", "score": 0.85},
    )
    entry = CogEntry.from_event(ev)
    assert entry is not None
    assert entry.kind == "risk"
    assert "critical_logs" in entry.summary
    assert "0.85" in entry.summary


def test_cog_entry_from_quarantine_event_verified() -> None:
    ev = TimelineEvent(
        event_id="e3",
        task_id="",
        node_id="",
        event_type="cog_quarantine_pending",
        timestamp_utc="2026-05-19T10:00:00+09:00",
        metadata={"signer_id": "trusted-rss", "verified": True, "summary": "x"},
    )
    entry = CogEntry.from_event(ev)
    assert entry is not None
    assert entry.kind == "quarantine"
    assert "active" in entry.summary


def test_cog_entry_from_quarantine_event_unsigned() -> None:
    ev = TimelineEvent(
        event_id="e4",
        task_id="",
        node_id="",
        event_type="cog_quarantine_pending",
        timestamp_utc="2026-05-19T10:00:00+09:00",
        metadata={"signer_id": "unsigned", "verified": False},
    )
    entry = CogEntry.from_event(ev)
    assert entry is not None
    assert entry.kind == "quarantine"
    assert "pending" in entry.summary


def test_cog_entry_returns_none_for_unrelated_event() -> None:
    ev = TimelineEvent(
        event_id="e5",
        task_id="",
        node_id="",
        event_type="bwt_summary",
        timestamp_utc="2026-05-19T10:00:00+09:00",
        metadata={},
    )
    assert CogEntry.from_event(ev) is None


def test_render_panel_empty_returns_placeholder() -> None:
    assert "(no cognitive mesh events" in render_panel([])


def test_render_panel_orders_newest_first() -> None:
    entries = [
        CogEntry(event_id="a", timestamp_utc="2026-05-19T08:00:00+09:00",
                 kind="proactive", summary="old"),
        CogEntry(event_id="b", timestamp_utc="2026-05-19T10:00:00+09:00",
                 kind="risk", summary="new"),
    ]
    text = render_panel(entries)
    # newer (10:00) は old (08:00) より上に
    assert text.index("10:00:00") < text.index("08:00:00")


def test_panel_feed_events_idempotent() -> None:
    panel = CognitiveMeshPanel()
    events = make_mock_cog_events(3)
    added1 = panel.feed_events(events)
    added2 = panel.feed_events(events)  # 同じ events を再投入
    assert added1 == 3
    assert added2 == 0  # dedup で再カウントされない
    assert panel.entry_count() == 3


def test_panel_latest() -> None:
    panel = CognitiveMeshPanel()
    panel.feed_events(make_mock_cog_events(3))
    latest = panel.latest()
    assert latest is not None
    assert latest.event_id == "cog-mock-002"


def test_panel_clear_resets_state() -> None:
    panel = CognitiveMeshPanel()
    panel.feed_events(make_mock_cog_events(3))
    assert panel.entry_count() == 3
    panel.clear()
    assert panel.entry_count() == 0
    assert panel.latest() is None
    # clear 後に再 feed しても dedup 復活なしで全件入る
    added = panel.feed_events(make_mock_cog_events(3))
    assert added == 3


def test_dispatch_routes_cog_events_to_panel() -> None:
    panel = CognitiveMeshPanel()
    events = make_mock_cog_events(3)
    result = dispatch_events(events, cog=panel)
    assert result.cog_added == 3
    assert result.bwt_added == 0
    assert result.trace_added == 0
    assert result.link_added == 0
    assert result.unrouted == 0
    assert result.unknown == 0
    assert "cog+3" in result.status_line()
    assert panel.entry_count() == 3


def test_dispatch_unrouted_when_cog_panel_missing() -> None:
    events = make_mock_cog_events(3)
    result = dispatch_events(events, cog=None)
    assert result.cog_added == 0
    assert result.unrouted == 3
    assert result.unknown == 0


def test_dispatch_result_total_added_includes_cog() -> None:
    r = DispatchResult(bwt_added=1, trace_added=2, link_added=3, cog_added=4)
    assert r.total_added == 10


def test_make_mock_cog_events_count() -> None:
    assert len(make_mock_cog_events(5)) == 5
    assert len(make_mock_cog_events(0)) == 0
