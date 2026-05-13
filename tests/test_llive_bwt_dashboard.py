"""F25 (b) — BWTDashboard の単体テスト.

UI 部分 (Textual `Static` の `update()` 呼び出し) は pure render 関数を
直接呼ぶことで分離テスト。実際の widget も mount せずに `feed_events` /
`run_count` / `latest` の API レベルだけ確認する。
"""

from __future__ import annotations

from llove.mcp.client import TimelineEvent
from llove.views.llive.bwt_dashboard import (
    BWTDashboard,
    BWTRun,
    make_mock_bwt_events,
    render_dashboard,
    render_per_task_drop,
    render_sparkline,
)

# ---------------------------------------------------------------------------
# BWTRun.from_event — 防御的パース
# ---------------------------------------------------------------------------


def test_from_event_returns_run_for_valid_payload() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t1",
        node_id="llive-1",
        event_type="bwt_summary",
        timestamp_utc="2026-05-14T08:30:00Z",
        metadata={
            "bwt": -0.008,
            "avg_accuracy": 0.78,
            "n_tasks": 5,
            "per_task_drop": {"t1": -0.01, "t2": -0.006},
            "task_order": ["t1", "t2"],
        },
    )
    run = BWTRun.from_event(ev)
    assert run is not None
    assert run.bwt == -0.008
    assert run.n_tasks == 5
    assert run.per_task_drop == {"t1": -0.01, "t2": -0.006}
    assert run.task_order == ("t1", "t2")


def test_from_event_returns_none_for_wrong_event_type() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t1",
        node_id="n",
        event_type="route_trace",
        timestamp_utc="x",
        metadata={"bwt": 0.0},
    )
    assert BWTRun.from_event(ev) is None


def test_from_event_returns_none_for_malformed_bwt() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t1",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={"bwt": "not a number"},
    )
    assert BWTRun.from_event(ev) is None


def test_from_event_tolerates_missing_optional_fields() -> None:
    """metadata に bwt 以外何も無くてもデフォルトでパースされる."""
    ev = TimelineEvent(
        event_id="e1",
        task_id="t1",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={"bwt": -0.005},
    )
    run = BWTRun.from_event(ev)
    assert run is not None
    assert run.bwt == -0.005
    assert run.n_tasks == 0
    assert run.per_task_drop == {}
    assert run.task_order == ()


def test_from_event_skips_invalid_per_task_drop_entries() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t1",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={
            "bwt": 0.0,
            "per_task_drop": {"t1": -0.01, "t2": "bad", "t3": -0.02},
        },
    )
    run = BWTRun.from_event(ev)
    assert run is not None
    # 文字列はスキップ、float に変換できたものだけ残る
    assert "t1" in run.per_task_drop
    assert "t2" not in run.per_task_drop
    assert "t3" in run.per_task_drop


def test_from_event_returns_none_when_per_task_drop_is_not_dict() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t1",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={"bwt": 0.0, "per_task_drop": [1, 2, 3]},
    )
    assert BWTRun.from_event(ev) is None


# ---------------------------------------------------------------------------
# render_sparkline
# ---------------------------------------------------------------------------


def test_sparkline_empty_for_single_sample() -> None:
    assert render_sparkline([0.5]) == ""


def test_sparkline_flat_for_equal_samples() -> None:
    out = render_sparkline([0.5, 0.5, 0.5])
    assert len(out) == 3
    # mid-band の単一文字で埋められる
    assert len(set(out)) == 1


def test_sparkline_has_extremes_for_varying_samples() -> None:
    out = render_sparkline([0.0, 1.0, 0.0, 1.0])
    assert len(out) == 4
    # min/max それぞれの最両端文字を含む
    assert out[0] == "▁"
    assert out[1] == "█"


# ---------------------------------------------------------------------------
# render_per_task_drop
# ---------------------------------------------------------------------------


def test_per_task_drop_placeholder_for_empty() -> None:
    out = render_per_task_drop({}, ())
    assert "(no per-task drop data)" in out


def test_per_task_drop_uses_task_order_when_provided() -> None:
    out = render_per_task_drop(
        {"t1": -0.01, "t2": -0.005, "t3": -0.008},
        task_order=("t3", "t1", "t2"),
    )
    lines = out.splitlines()
    # 各タスク 1 行ずつ、task_order の順で並ぶ
    assert "t3" in lines[0]
    assert "t1" in lines[1]
    assert "t2" in lines[2]


def test_per_task_drop_shows_sign_and_magnitude() -> None:
    out = render_per_task_drop({"t1": -0.01, "t2": 0.005}, ("t1", "t2"))
    assert "-0.010" in out
    assert "+0.005" in out


def test_per_task_drop_adds_unordered_keys_at_end() -> None:
    """task_order に無い key も忘れずに表示 (forward-compat)."""
    out = render_per_task_drop({"t1": 0.0, "t99": 0.5}, task_order=("t1",))
    lines = out.splitlines()
    assert "t1" in lines[0]
    assert "t99" in lines[1]


# ---------------------------------------------------------------------------
# render_dashboard
# ---------------------------------------------------------------------------


def test_dashboard_placeholder_for_empty_runs() -> None:
    out = render_dashboard([])
    assert "no bwt runs" in out


def test_dashboard_includes_latest_run_header() -> None:
    events = make_mock_bwt_events(n=3)
    runs = [r for ev in events if (r := BWTRun.from_event(ev)) is not None]
    out = render_dashboard(runs)
    assert "Latest run:" in out
    assert "bwt=" in out
    assert "acc=" in out


def test_dashboard_includes_sparkline_with_enough_runs() -> None:
    events = make_mock_bwt_events(n=4)
    runs = [r for ev in events if (r := BWTRun.from_event(ev)) is not None]
    out = render_dashboard(runs)
    assert "BWT trend" in out


def test_dashboard_notes_insufficient_runs_for_sparkline() -> None:
    events = make_mock_bwt_events(n=1)
    runs = [r for ev in events if (r := BWTRun.from_event(ev)) is not None]
    out = render_dashboard(runs)
    assert "need >=2 runs" in out


# ---------------------------------------------------------------------------
# BWTDashboard widget — mount せず API レベルでテスト
# ---------------------------------------------------------------------------


def test_widget_starts_empty() -> None:
    w = BWTDashboard()
    assert w.run_count() == 0
    assert w.latest() is None


def test_widget_feed_events_ingests_bwt_only() -> None:
    w = BWTDashboard()
    events = make_mock_bwt_events(n=3) + [
        TimelineEvent(
            event_id="other",
            task_id="t",
            node_id="n",
            event_type="route_trace",
            timestamp_utc="x",
            metadata={},
        )
    ]
    added = w.feed_events(events)
    assert added == 3
    assert w.run_count() == 3
    assert w.latest() is not None
    assert w.latest().event_id.startswith("mock-bwt-")


def test_widget_feed_events_dedups_by_event_id() -> None:
    w = BWTDashboard()
    events = make_mock_bwt_events(n=3)
    w.feed_events(events)
    # 同じ events を再投入 → 0 件追加
    added = w.feed_events(events)
    assert added == 0
    assert w.run_count() == 3


def test_widget_feed_events_appends_new_runs() -> None:
    w = BWTDashboard()
    w.feed_events(make_mock_bwt_events(n=2))
    # 別 batch の event を追加
    new_events = [
        TimelineEvent(
            event_id="mock-bwt-100",
            task_id="t100",
            node_id="llive-1",
            event_type="bwt_summary",
            timestamp_utc="2026-05-14T09:00:00Z",
            metadata={"bwt": 0.001, "n_tasks": 5},
        )
    ]
    added = w.feed_events(new_events)
    assert added == 1
    assert w.run_count() == 3
    latest = w.latest()
    assert latest is not None
    assert latest.event_id == "mock-bwt-100"


def test_widget_clear_resets_state() -> None:
    w = BWTDashboard()
    w.feed_events(make_mock_bwt_events(n=3))
    w.clear()
    assert w.run_count() == 0
    assert w.latest() is None
    # 同じ event_id でも clear 後は再受信できる
    added = w.feed_events(make_mock_bwt_events(n=3))
    assert added == 3


def test_widget_silently_skips_malformed_events() -> None:
    """metadata 不正な event はスキップして UI を壊さない."""
    w = BWTDashboard()
    bad = TimelineEvent(
        event_id="bad-1",
        task_id="t",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={"bwt": "not a number"},
    )
    good = make_mock_bwt_events(n=1)[0]
    added = w.feed_events([bad, good])
    assert added == 1  # bad はスキップ、good のみ追加
    assert w.run_count() == 1


# ---------------------------------------------------------------------------
# make_mock_bwt_events — fixture 自体の sanity check
# ---------------------------------------------------------------------------


def test_mock_events_generate_correct_count_and_shape() -> None:
    events = make_mock_bwt_events(n=4)
    assert len(events) == 4
    for ev in events:
        assert ev.event_type == "bwt_summary"
        assert "bwt" in ev.metadata
        assert "per_task_drop" in ev.metadata


def test_mock_events_are_distinct_by_event_id() -> None:
    events = make_mock_bwt_events(n=5)
    ids = [ev.event_id for ev in events]
    assert len(ids) == len(set(ids))
