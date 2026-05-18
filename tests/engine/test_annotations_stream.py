# SPDX-License-Identifier: Apache-2.0
"""F25 Phase h.2 — integration tests for GET /api/v1/annotations/stream.

SSE is tested by:
1. Setting a very short heartbeat interval (env) so the stream produces
   bytes within the test budget even without prior emits.
2. Pre-emitting events into the default bus, then opening the stream so
   the replay buffer kicks in.
3. Reading via ``TestClient.stream(...)`` and parsing SSE messages until
   an expected count is reached, then closing the response.
"""
from __future__ import annotations

import json
from typing import Iterator

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from llove.engine.brief_event_bus import (
    BriefEventBus,
    get_default_bus,
    reset_default_bus,
)


@pytest.fixture(autouse=True)
def _fast_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Speed up heartbeat so tests don't wait 15 s."""
    monkeypatch.setenv("LLOVE_BRIEF_HEARTBEAT_S", "0.1")
    reset_default_bus()
    yield
    reset_default_bus()


@pytest.fixture()
def client() -> TestClient:
    from llove.engine import make_http_app

    return TestClient(make_http_app())


def _parse_sse_messages(raw_iter: Iterator[bytes], stop_at: int) -> list[dict]:
    """Read SSE byte-blocks until ``stop_at`` messages have been parsed."""
    messages: list[dict] = []
    buffer = b""
    for chunk in raw_iter:
        buffer += chunk
        while b"\n\n" in buffer:
            block, _, buffer = buffer.partition(b"\n\n")
            msg: dict = {}
            for line in block.decode("utf-8").splitlines():
                if line.startswith("event: "):
                    msg["event"] = line[len("event: "):]
                elif line.startswith("id: "):
                    msg["id"] = line[len("id: "):]
                elif line.startswith("data: "):
                    msg["data"] = json.loads(line[len("data: "):])
            if msg:
                messages.append(msg)
                if len(messages) >= stop_at:
                    return messages
    return messages


def test_stream_replays_buffered_events_on_connect(client: TestClient) -> None:
    """Events emitted before subscription appear in the replay phase."""
    bus = get_default_bus()
    bus.emit("annotation", {"summary": "hi"}, namespace="oka", target_layer="llove", brief_id="b1")
    bus.emit("brief_done", {"status": "ok"}, brief_id="b1")

    with client.stream("GET", "/api/v1/annotations/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        msgs = _parse_sse_messages(resp.iter_bytes(), stop_at=2)

    assert [m["event"] for m in msgs[:2]] == ["annotation", "brief_done"]
    assert msgs[0]["data"]["namespace"] == "oka"
    assert msgs[0]["data"]["target_layer"] == "llove"
    assert msgs[0]["data"]["brief_id"] == "b1"
    assert msgs[0]["data"]["summary"] == "hi"
    assert msgs[1]["data"]["status"] == "ok"
    assert msgs[0]["id"] == "1"
    assert msgs[1]["id"] == "2"


def test_stream_heartbeat_when_idle(client: TestClient) -> None:
    """Idle stream emits ``heartbeat`` events at LLOVE_BRIEF_HEARTBEAT_S."""
    with client.stream("GET", "/api/v1/annotations/stream") as resp:
        msgs = _parse_sse_messages(resp.iter_bytes(), stop_at=1)
    assert msgs[0]["event"] == "heartbeat"


def test_stream_filters_by_brief_id(client: TestClient) -> None:
    bus = get_default_bus()
    bus.emit("brief_done", {"status": "ok"}, brief_id="keep")
    bus.emit("brief_done", {"status": "ok"}, brief_id="drop")
    bus.emit("brief_done", {"status": "ok"}, brief_id="keep")

    with client.stream("GET", "/api/v1/annotations/stream?brief_id=keep") as resp:
        msgs = _parse_sse_messages(resp.iter_bytes(), stop_at=2)
    assert all(m["data"]["brief_id"] == "keep" for m in msgs[:2])


def test_stream_filters_by_namespace_only_for_annotations(client: TestClient) -> None:
    bus = get_default_bus()
    bus.emit("annotation", {"k": 1}, namespace="oka")
    bus.emit("annotation", {"k": 2}, namespace="cog")
    bus.emit("brief_done", {"status": "ok"}, brief_id="x")  # not an annotation, must pass

    with client.stream("GET", "/api/v1/annotations/stream?namespaces=oka") as resp:
        msgs = _parse_sse_messages(resp.iter_bytes(), stop_at=2)
    events = [m["event"] for m in msgs[:2]]
    assert events == ["annotation", "brief_done"]
    assert msgs[0]["data"]["namespace"] == "oka"


def test_stream_resume_via_last_event_id(client: TestClient) -> None:
    """Last-Event-ID header replays only events with seq > id."""
    bus = get_default_bus()
    bus.emit("annotation", {"i": 1}, namespace="oka")  # seq=1
    bus.emit("annotation", {"i": 2}, namespace="oka")  # seq=2
    bus.emit("annotation", {"i": 3}, namespace="oka")  # seq=3

    with client.stream(
        "GET",
        "/api/v1/annotations/stream",
        headers={"Last-Event-ID": "2"},
    ) as resp:
        msgs = _parse_sse_messages(resp.iter_bytes(), stop_at=1)
    assert msgs[0]["id"] == "3"
    assert msgs[0]["data"]["i"] == 3


def test_submit_brief_emits_brief_done_event_on_bus(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/v1/brief/submit must publish a brief_done event afterwards."""
    import sys
    import types
    from unittest import mock

    fake_tool = mock.MagicMock(
        return_value={
            "brief": {"brief_id": "auto-bid"},
            "result": {
                "brief_id": "auto-bid",
                "status": "ok",
                "rationale": "r",
                "artifacts": [],
                "ledger_entries": [],
                "error": None,
            },
        }
    )
    fake_tools_mod = types.ModuleType("llive.mcp.tools")
    fake_tools_mod.tool_submit_brief = fake_tool  # type: ignore[attr-defined]
    fake_mcp_mod = types.ModuleType("llive.mcp")
    fake_mcp_mod.tools = fake_tools_mod  # type: ignore[attr-defined]
    fake_llive = types.ModuleType("llive")
    fake_llive.mcp = fake_mcp_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "llive", fake_llive)
    monkeypatch.setitem(sys.modules, "llive.mcp", fake_mcp_mod)
    monkeypatch.setitem(sys.modules, "llive.mcp.tools", fake_tools_mod)

    resp = client.post("/api/v1/brief/submit", json={"goal": "g"})
    assert resp.status_code == 200

    bus = get_default_bus()
    assert bus.buffer_size >= 1
    # Last emitted event should be brief_done
    last = bus.replay_since(0)[-1]
    assert last.event_type == "brief_done"
    assert last.brief_id == "auto-bid"
    assert last.data["status"] == "ok"
