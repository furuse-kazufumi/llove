# SPDX-License-Identifier: Apache-2.0
"""F25 Phase h.2 — in-process event bus for /api/v1/annotations/stream.

Engine-internal bounded buffer that lets:

* the ``POST /api/v1/brief/submit`` handler (or any future llive bridge)
  emit ``annotation`` / ``stage_complete`` / ``brief_done`` events
* the ``GET /api/v1/annotations/stream`` SSE handler subscribe and replay

This is a Phase-1 skeleton — events are not yet wired from a running
``BriefRunner``; that bridge lands once llive grows an Annotation emit
hook the engine can attach to.

Design notes:

* ``deque(maxlen=...)`` enforces the bounded buffer (drop-oldest semantics
  on overflow; queue policy = ``drop_oldest`` from docs/design 4.6.3).
* Each subscriber has its own ``asyncio.Queue`` so a slow client cannot
  starve fast ones. ``put_nowait`` ignores ``QueueFull`` — slow client
  loses events rather than blocking publishers.
* Sequence numbers are monotonic per-process and survive within the buffer
  for ``Last-Event-ID`` resume (best-effort; not durable across restarts).
* No global lock — emit is fast-path; subscribers list mutation is rare.
  In multi-worker deployments (Pattern C) this needs a Redis/NATS backplane
  but that is Phase h+1 / Pattern C territory.
"""
from __future__ import annotations

import asyncio
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class BriefEvent:
    """One event on the bus. Mirrors docs/design/f25-phase-h-e2e.md 4.6.2."""

    seq: int
    event_type: str  # "annotation" | "stage_complete" | "brief_done" | "heartbeat"
    data: dict[str, Any] = field(default_factory=dict)
    brief_id: str | None = None
    target_layer: str | None = None
    namespace: str | None = None  # set only for event_type=="annotation"
    ts: str = field(default_factory=_utcnow_iso)


def _max_queue_size() -> int:
    raw = os.environ.get("LLOVE_BRIEF_QUEUE_MAX", "1024")
    try:
        value = int(raw)
    except ValueError:
        return 1024
    return max(1, value)


class BriefEventBus:
    """Bounded, multi-subscriber event bus (in-process, asyncio-friendly)."""

    def __init__(self, maxlen: int | None = None) -> None:
        self._buf: deque[BriefEvent] = deque(maxlen=maxlen if maxlen is not None else _max_queue_size())
        self._seq: int = 0
        self._subscribers: list[asyncio.Queue[BriefEvent]] = []

    @property
    def buffer_size(self) -> int:
        return len(self._buf)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def emit(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        *,
        brief_id: str | None = None,
        target_layer: str | None = None,
        namespace: str | None = None,
    ) -> BriefEvent:
        """Append an event to the buffer and broadcast to live subscribers."""
        self._seq += 1
        ev = BriefEvent(
            seq=self._seq,
            event_type=event_type,
            data=dict(data or {}),
            brief_id=brief_id,
            target_layer=target_layer,
            namespace=namespace,
        )
        self._buf.append(ev)
        for q in list(self._subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                # drop_oldest policy at subscriber level: skip slow client
                pass
        return ev

    def replay_since(self, since_seq: int) -> list[BriefEvent]:
        """Return buffered events with ``seq > since_seq`` (for Last-Event-ID)."""
        return [ev for ev in list(self._buf) if ev.seq > since_seq]

    def _register(self, q: asyncio.Queue[BriefEvent]) -> None:
        self._subscribers.append(q)

    def _unregister(self, q: asyncio.Queue[BriefEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass


# Module-level singleton — one bus per engine process.
_DEFAULT_BUS: BriefEventBus | None = None


def get_default_bus() -> BriefEventBus:
    global _DEFAULT_BUS
    if _DEFAULT_BUS is None:
        _DEFAULT_BUS = BriefEventBus()
    return _DEFAULT_BUS


def reset_default_bus() -> None:
    """For tests: drop the cached default bus."""
    global _DEFAULT_BUS
    _DEFAULT_BUS = None
