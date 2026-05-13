"""F25 (e) — Dispatch helper + TimelinePollDriver の単体テスト.

全テストは外部 HTTP / 実 viewer mount 無しで完結 (BWTDashboard 等は
mount せずに API レベルで使う)。
"""

from __future__ import annotations

from llove.mcp.client import (
    TimelineClient,
    TimelineEvent,
    make_fake_transport,
)
from llove.views.llive.bwt_dashboard import (
    BWTDashboard,
    make_mock_bwt_events,
)
from llove.views.llive.dispatch import (
    DispatchResult,
    TimelinePollDriver,
    dispatch_events,
)
from llove.views.llive.memory_link_panel import (
    MemoryLinkVizPanel,
    make_mock_concept_events,
)
from llove.views.llive.route_trace_viewer import (
    RouteTraceViewer,
    make_mock_route_trace_events,
)

# ---------------------------------------------------------------------------
# dispatch_events
# ---------------------------------------------------------------------------


def test_dispatch_routes_each_event_type_to_correct_viewer() -> None:
    bwt = BWTDashboard()
    trace = RouteTraceViewer()
    link = MemoryLinkVizPanel()

    events = [
        *make_mock_bwt_events(n=3),
        *make_mock_route_trace_events(n=2),
        *make_mock_concept_events(n=4),
    ]
    result = dispatch_events(events, bwt=bwt, trace=trace, link=link)

    assert isinstance(result, DispatchResult)
    assert result.bwt_added == 3
    assert result.trace_added == 2
    assert result.link_added == 4
    assert result.unrouted == 0
    assert result.unknown == 0
    assert result.total_added == 9

    assert bwt.run_count() == 3
    assert trace.trace_count() == 2
    assert link.concept_count() == 4


def test_dispatch_with_no_viewers_counts_all_as_unrouted() -> None:
    events = [
        *make_mock_bwt_events(n=2),
        *make_mock_route_trace_events(n=1),
    ]
    result = dispatch_events(events)  # 全 viewer = None
    assert result.bwt_added == 0
    assert result.trace_added == 0
    assert result.unrouted == 3
    assert result.unknown == 0


def test_dispatch_partial_viewers_only_route_active_ones() -> None:
    bwt = BWTDashboard()
    # trace / link = None
    events = [
        *make_mock_bwt_events(n=2),
        *make_mock_route_trace_events(n=3),
    ]
    result = dispatch_events(events, bwt=bwt)
    assert result.bwt_added == 2
    assert result.trace_added == 0
    assert result.unrouted == 3  # route_trace は捨てられる


def test_dispatch_unknown_event_type_counted_separately() -> None:
    """KNOWN_EVENT_TYPES に無い event_type は unknown."""
    bwt = BWTDashboard()
    events = [
        *make_mock_bwt_events(n=1),
        TimelineEvent(
            event_id="x",
            task_id="t",
            node_id="n",
            event_type="something_new",
            timestamp_utc="x",
            metadata={},
        ),
        TimelineEvent(
            event_id="y",
            task_id="t",
            node_id="n",
            event_type="another_new",
            timestamp_utc="x",
            metadata={},
        ),
    ]
    result = dispatch_events(events, bwt=bwt)
    assert result.bwt_added == 1
    assert result.unknown == 2
    assert result.unrouted == 0  # known event_type の missing viewer は無し


def test_dispatch_empty_events_returns_zero_counts() -> None:
    bwt = BWTDashboard()
    result = dispatch_events([], bwt=bwt)
    assert result.total_added == 0
    assert result.unknown == 0
    assert result.unrouted == 0


# ---------------------------------------------------------------------------
# DispatchResult.status_line
# ---------------------------------------------------------------------------


def test_status_line_for_no_events() -> None:
    assert DispatchResult().status_line() == "no new events"


def test_status_line_shows_non_zero_buckets() -> None:
    r = DispatchResult(bwt_added=3, link_added=2, unknown=1)
    line = r.status_line()
    assert "bwt+3" in line
    assert "link+2" in line
    assert "unknown=1" in line
    assert "trace" not in line  # trace_added=0 は表示しない


def test_status_line_includes_unrouted_when_set() -> None:
    r = DispatchResult(unrouted=5)
    assert "unrouted=5" in r.status_line()


# ---------------------------------------------------------------------------
# TimelinePollDriver
# ---------------------------------------------------------------------------


def test_driver_poll_once_fetches_and_dispatches() -> None:
    import json

    payload = json.dumps(
        {
            "count": 3,
            "events": [
                ev.__dict__
                if hasattr(ev, "__dict__")
                else ev
                for ev in [
                    {
                        "event_id": "e1",
                        "task_id": "t1",
                        "node_id": "n",
                        "event_type": "bwt_summary",
                        "timestamp_utc": "x",
                        "metadata": {"bwt": 0.0, "n_tasks": 1},
                    },
                    {
                        "event_id": "e2",
                        "task_id": "550e8400-e29b-41d4-a716-446655440000",
                        "node_id": "n",
                        "event_type": "route_trace",
                        "timestamp_utc": "x",
                        "metadata": {"subblocks": [], "metrics": {}},
                    },
                    {
                        "event_id": "e3",
                        "task_id": "t3",
                        "node_id": "n",
                        "event_type": "concept_update",
                        "timestamp_utc": "x",
                        "metadata": {"concept_id": "c1"},
                    },
                ]
            ],
        }
    ).encode("utf-8")

    def handler(method, url, headers, body):
        return 200, payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    bwt = BWTDashboard()
    trace = RouteTraceViewer()
    link = MemoryLinkVizPanel()
    driver = TimelinePollDriver(
        client=client, bwt=bwt, trace=trace, link=link
    )
    result = driver.poll_once()
    assert result.bwt_added == 1
    assert result.trace_added == 1
    assert result.link_added == 1


def test_driver_status_line_appends_client_error() -> None:
    def handler(method, url, headers, body):
        return 503, b""

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    driver = TimelinePollDriver(client=client, bwt=BWTDashboard())
    driver.poll_once()
    line = driver.status_line()
    # last_error が status line に併記される
    assert "err:" in line
    assert "http_503" in line


def test_driver_uses_configured_limit_and_node_id() -> None:
    captured: dict[str, str] = {}

    def handler(method, url, headers, body):
        captured["url"] = url
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    driver = TimelinePollDriver(
        client=client, bwt=BWTDashboard(), limit=200, node_id="llive-prod"
    )
    driver.poll_once()
    assert "limit=200" in captured["url"]
    assert "node_id=llive-prod" in captured["url"]


def test_driver_repeated_poll_is_idempotent_on_same_events() -> None:
    """同じ events を polling し直しても event_id dedup で追加されない."""
    import json

    payload = json.dumps(
        {
            "count": 1,
            "events": [
                {
                    "event_id": "e1",
                    "task_id": "t1",
                    "node_id": "n",
                    "event_type": "bwt_summary",
                    "timestamp_utc": "x",
                    "metadata": {"bwt": 0.0, "n_tasks": 1},
                }
            ],
        }
    ).encode("utf-8")

    def handler(method, url, headers, body):
        return 200, payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    bwt = BWTDashboard()
    driver = TimelinePollDriver(client=client, bwt=bwt)
    r1 = driver.poll_once()
    r2 = driver.poll_once()
    assert r1.bwt_added == 1
    assert r2.bwt_added == 0  # dedup
    assert bwt.run_count() == 1


# ---------------------------------------------------------------------------
# total_added property
# ---------------------------------------------------------------------------


def test_total_added_sums_three_viewer_counts() -> None:
    r = DispatchResult(bwt_added=2, trace_added=3, link_added=5, unrouted=4)
    assert r.total_added == 10  # unrouted / unknown は除外


def test_total_added_zero_for_empty() -> None:
    assert DispatchResult().total_added == 0
