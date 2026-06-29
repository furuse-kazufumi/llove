# SPDX-License-Identifier: Apache-2.0
"""F25 Phase h.2 — unit tests for BriefEventBus (in-process emit/replay)."""
from __future__ import annotations

import asyncio

import pytest

from llove.engine.brief_event_bus import (
    BriefEvent,
    BriefEventBus,
    get_default_bus,
    reset_default_bus,
)


@pytest.fixture(autouse=True)
def _isolate_bus() -> None:
    reset_default_bus()
    yield
    reset_default_bus()


def test_emit_assigns_monotonic_seq() -> None:
    bus = BriefEventBus(maxlen=64)
    a = bus.emit("annotation", {"x": 1}, namespace="oka")
    b = bus.emit("stage_complete", {"stage": "salience"})
    c = bus.emit("brief_done", {"status": "ok"}, brief_id="b1")
    assert (a.seq, b.seq, c.seq) == (1, 2, 3)
    assert a.event_type == "annotation"
    assert b.event_type == "stage_complete"
    assert c.event_type == "brief_done"
    assert c.brief_id == "b1"


def test_buffer_drops_oldest_on_overflow() -> None:
    bus = BriefEventBus(maxlen=3)
    for i in range(5):
        bus.emit("annotation", {"i": i}, namespace="oka")
    buf = list(bus._buf)
    assert len(buf) == 3
    assert [ev.data["i"] for ev in buf] == [2, 3, 4]


def test_replay_since_filters_by_seq() -> None:
    bus = BriefEventBus(maxlen=64)
    for i in range(5):
        bus.emit("annotation", {"i": i}, namespace="oka")
    out = bus.replay_since(2)
    assert [ev.seq for ev in out] == [3, 4, 5]


def test_replay_since_zero_returns_full_buffer() -> None:
    bus = BriefEventBus(maxlen=64)
    bus.emit("annotation", {})
    bus.emit("annotation", {})
    assert len(bus.replay_since(0)) == 2


def test_subscribers_receive_emitted_events() -> None:
    async def run() -> list[BriefEvent]:
        bus = BriefEventBus(maxlen=64)
        q: asyncio.Queue[BriefEvent] = asyncio.Queue(maxsize=16)
        bus._register(q)
        bus.emit("annotation", {"k": "v"}, namespace="oka")
        bus.emit("brief_done", {"status": "ok"})
        received: list[BriefEvent] = []
        for _ in range(2):
            ev = await asyncio.wait_for(q.get(), timeout=0.5)
            received.append(ev)
        bus._unregister(q)
        return received

    events = asyncio.run(run())
    assert len(events) == 2
    assert events[0].event_type == "annotation"
    assert events[1].event_type == "brief_done"


def test_slow_subscriber_does_not_block_publisher() -> None:
    """QueueFull on a slow subscriber must not raise into emit()."""

    async def run() -> int:
        bus = BriefEventBus(maxlen=1024)
        slow: asyncio.Queue[BriefEvent] = asyncio.Queue(maxsize=2)
        bus._register(slow)
        # emit 10 events into a queue that holds only 2 — overflow should
        # be silently dropped at the subscriber side, not raised.
        for i in range(10):
            bus.emit("annotation", {"i": i}, namespace="oka")
        bus._unregister(slow)
        return bus._seq

    final_seq = asyncio.run(run())
    assert final_seq == 10  # all 10 emit() calls succeeded


def test_get_default_bus_singleton() -> None:
    a = get_default_bus()
    b = get_default_bus()
    assert a is b
    reset_default_bus()
    c = get_default_bus()
    assert c is not a


def test_brief_event_timestamp_iso_format() -> None:
    bus = BriefEventBus()
    ev = bus.emit("annotation", {})
    # Expect ISO-8601 UTC with 'Z' suffix
    assert ev.ts.endswith("Z")
    assert "T" in ev.ts
