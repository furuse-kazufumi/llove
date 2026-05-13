"""F25 (a) — Timeline MCP client の単体テスト.

外部 HTTP を踏まずに transport 注入で fake response を返してテストする。
ネットワーク / SSL / urllib の動作は本質ではない (それは透過的に通すだけ)。
"""

from __future__ import annotations

import json
from typing import Any

from llove.mcp.client import (
    MCPClientError,
    TimelineClient,
    TimelineEvent,
    UrllibTransport,
    make_fake_transport,
)

# ---------------------------------------------------------------------------
# URL 組立
# ---------------------------------------------------------------------------


def test_url_joins_base_and_path() -> None:
    captured: dict[str, str] = {}

    def handler(method, url, headers, body):
        captured["method"] = method
        captured["url"] = url
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://localhost:8000",
        transport=make_fake_transport(handler),
    )
    client.fetch_recent()
    assert captured["method"] == "GET"
    assert captured["url"].startswith("http://localhost:8000/timeline/recent")


def test_url_handles_trailing_slash_in_base() -> None:
    captured: dict[str, str] = {}

    def handler(method, url, headers, body):
        captured["url"] = url
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://localhost:8000/",
        transport=make_fake_transport(handler),
    )
    client.fetch_recent()
    # ダブルスラッシュにならないこと
    assert "//timeline" not in captured["url"]


def test_query_string_includes_limit_and_node_id() -> None:
    captured: dict[str, str] = {}

    def handler(method, url, headers, body):
        captured["url"] = url
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    client.fetch_recent(limit=10, node_id="llive-1")
    assert "limit=10" in captured["url"]
    assert "node_id=llive-1" in captured["url"]


def test_empty_node_id_not_included_in_query() -> None:
    """空フィルタを送ると llmesh は全件返す挙動なので、空値は送らない."""
    captured: dict[str, str] = {}

    def handler(method, url, headers, body):
        captured["url"] = url
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    client.fetch_recent(limit=5, node_id="")
    assert "node_id=" not in captured["url"]


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------


def test_sends_x_node_id_header() -> None:
    captured: dict[str, str] = {}

    def handler(method, url, headers, body):
        captured.update(headers)
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://h:8000",
        transport=make_fake_transport(handler),
        node_id_header="llove-tui-1",
    )
    client.fetch_recent()
    assert captured.get("X-Node-Id") == "llove-tui-1"


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _make_response(events: list[dict[str, Any]]) -> bytes:
    return json.dumps({"count": len(events), "events": events}).encode("utf-8")


def test_fetch_recent_parses_events_into_dataclasses() -> None:
    payload = _make_response(
        [
            {
                "event_id": "e1",
                "task_id": "t1",
                "node_id": "llive-1",
                "event_type": "bwt_summary",
                "timestamp_utc": "2026-05-14T08:30:00Z",
                "metadata": {"bwt": -0.008, "n_tasks": 5},
            }
        ]
    )

    def handler(method, url, headers, body):
        return 200, payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert len(events) == 1
    ev = events[0]
    assert isinstance(ev, TimelineEvent)
    assert ev.event_type == "bwt_summary"
    assert ev.metadata == {"bwt": -0.008, "n_tasks": 5}


def test_fetch_recent_filters_by_event_type_client_side() -> None:
    """llmesh は filter を未実装なのでクライアント側で絞る."""
    payload = _make_response(
        [
            {
                "event_id": "e1",
                "task_id": "t1",
                "node_id": "llive-1",
                "event_type": "bwt_summary",
                "timestamp_utc": "2026-05-14T08:30:00Z",
                "metadata": {},
            },
            {
                "event_id": "e2",
                "task_id": "t2",
                "node_id": "llive-1",
                "event_type": "route_trace",
                "timestamp_utc": "2026-05-14T08:30:01Z",
                "metadata": {},
            },
        ]
    )

    def handler(method, url, headers, body):
        return 200, payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent(event_type="bwt_summary")
    assert len(events) == 1
    assert events[0].event_type == "bwt_summary"


def test_fetch_recent_skips_non_dict_rows() -> None:
    """events に dict 以外が混ざっていても無視 (forward-compat)."""

    def handler(method, url, headers, body):
        body_payload = json.dumps(
            {
                "count": 3,
                "events": [
                    "garbage",
                    123,
                    {
                        "event_id": "e1",
                        "task_id": "t1",
                        "node_id": "n",
                        "event_type": "bwt_summary",
                        "timestamp_utc": "x",
                        "metadata": {},
                    },
                ],
            }
        ).encode("utf-8")
        return 200, body_payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert len(events) == 1


def test_fetch_recent_tolerates_missing_metadata() -> None:
    """metadata が None でも dict にリセットされる (lenient parser)."""

    def handler(method, url, headers, body):
        body_payload = json.dumps(
            {
                "count": 1,
                "events": [
                    {
                        "event_id": "e1",
                        "task_id": "t1",
                        "node_id": "n",
                        "event_type": "bwt_summary",
                        "timestamp_utc": "x",
                        # metadata 欠落
                    }
                ],
            }
        ).encode("utf-8")
        return 200, body_payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert len(events) == 1
    assert events[0].metadata == {}


# ---------------------------------------------------------------------------
# Error handling — UI を凍結させない fail-closed
# ---------------------------------------------------------------------------


def test_http_error_returns_empty_list_and_records_last_error() -> None:
    def handler(method, url, headers, body):
        return 503, b'{"detail":"timeline_not_configured"}'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert events == []
    assert client.last_error == "http_503"


def test_json_parse_error_returns_empty_list() -> None:
    def handler(method, url, headers, body):
        return 200, b"not json"

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert events == []
    assert client.last_error is not None
    assert "json_parse_error" in client.last_error


def test_connection_error_returns_empty_list() -> None:
    def handler(method, url, headers, body):
        raise MCPClientError("connection refused")

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert events == []
    assert client.last_error is not None
    assert "connection refused" in client.last_error


def test_unexpected_top_level_type_handled() -> None:
    """list ではなく dict が想定される top-level. list が返ったらエラー扱い."""

    def handler(method, url, headers, body):
        return 200, b'["array", "not", "dict"]'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    events = client.fetch_recent()
    assert events == []
    assert client.last_error is not None


def test_successful_call_clears_last_error() -> None:
    """連続呼び出しで前回の error が残らないこと."""
    state = {"i": 0}

    def handler(method, url, headers, body):
        state["i"] += 1
        if state["i"] == 1:
            return 503, b""
        return 200, b'{"count": 0, "events": []}'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    client.fetch_recent()
    assert client.last_error == "http_503"
    client.fetch_recent()
    assert client.last_error is None


# ---------------------------------------------------------------------------
# fetch_task
# ---------------------------------------------------------------------------


def test_fetch_task_returns_full_timeline() -> None:
    payload = json.dumps(
        {
            "task_id": "t1",
            "node_id": "llive-1",
            "started": "2026-05-14T08:30:00Z",
            "terminal": True,
            "resumable": False,
            "events": [
                {
                    "event_id": "e1",
                    "event_type": "received",
                    "timestamp_utc": "2026-05-14T08:30:00Z",
                    "delta_ms": 0,
                    "metadata": {},
                },
                {
                    "event_id": "e2",
                    "event_type": "completed",
                    "timestamp_utc": "2026-05-14T08:30:01Z",
                    "delta_ms": 1000,
                    "metadata": {"bwt": -0.008},
                },
            ],
        }
    ).encode("utf-8")

    def handler(method, url, headers, body):
        assert "/timeline/task/t1" in url
        return 200, payload

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    tl = client.fetch_task("t1")
    assert tl is not None
    assert tl.task_id == "t1"
    assert tl.terminal is True
    assert len(tl.events) == 2
    assert tl.events[1].metadata == {"bwt": -0.008}
    # event の task_id / node_id は上位 doc から埋め込まれる
    assert tl.events[0].task_id == "t1"
    assert tl.events[0].node_id == "llive-1"


def test_fetch_task_404_returns_none() -> None:
    def handler(method, url, headers, body):
        return 404, b'{"detail":"task_not_found:t1"}'

    client = TimelineClient(
        base_url="http://h:8000", transport=make_fake_transport(handler)
    )
    tl = client.fetch_task("t1")
    assert tl is None
    assert client.last_error == "http_404"


# ---------------------------------------------------------------------------
# UrllibTransport (default) は smoke-test のみ — 実 HTTP は本ファイルでは
# 踏まないが、構築時にエラーが出ないこと / interface を満たすことだけ確認。
# ---------------------------------------------------------------------------


def test_urllib_transport_constructs_with_defaults() -> None:
    t = UrllibTransport()
    assert t.timeout == 5.0


def test_default_transport_used_when_not_passed() -> None:
    client = TimelineClient(base_url="http://h:8000")
    assert isinstance(client.transport, UrllibTransport)
