"""Reliability scenario — MessageAssembler + ChunkSender + WatchdogTimer.

Walks through a small streamed message under simulated packet loss:
    1. send 6 chunks; chunks 3 and 5 are dropped
    2. receiver detects gaps and emits one RETRANSMIT
    3. sender re-sends only the missing chunks
    4. message is fully reassembled
    5. STREAM_ACK acknowledges; sender drops its buffer
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind

_INTRO = (
    "**Reliability protocol**: `ChunkSender` + `MessageAssembler` recover from packet "
    "loss with ACK + RETRANSMIT (sent at most **once** to avoid amplification)."
)


class ReliabilityScenario(DemoScenario):
    name = "reliability"
    title = "Reliability — ACK / RETRANSMIT / Watchdog"
    description = (
        "Lossy stream of 6 chunks. Watch RETRANSMIT recover dropped chunks 3 and 5 "
        "before STREAM_ACK arrives."
    )
    default_pause = 0.45

    async def events(self) -> AsyncIterator[Event]:
        yield narrate(_INTRO, title="Scenario: Reliability")

        # Step 1: send chunks
        yield narrate(
            "**Step 1.** Sender pushes chunks 1–6. The network drops **#3** and **#5**.",
            title="Step 1 — send",
        )
        for i in range(1, 7):
            dropped = i in {3, 5}
            yield Event(
                kind=EventKind.AUDIT,
                source_id="chunk_sender",
                payload={
                    "event": "chunk.send",
                    "seq": i,
                    "delivered": not dropped,
                    "note": "lost in transit" if dropped else "ok",
                },
            )

        # Step 2: detect gaps
        yield narrate(
            "**Step 2.** Receiver's `MessageAssembler.check_timeouts()` notices gaps at "
            "seq=3 and seq=5 → emits **one** RETRANSMIT request.",
            title="Step 2 — detect",
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="message_assembler",
            payload={"event": "retransmit.request", "missing_seq": [3, 5]},
        )

        # Step 3: re-send
        yield narrate(
            "**Step 3.** Sender's `handle_retransmit()` re-sends **only** the missing "
            "chunks. No duplicate retries.",
            title="Step 3 — recover",
        )
        for i in (3, 5):
            yield Event(
                kind=EventKind.AUDIT,
                source_id="chunk_sender",
                payload={"event": "chunk.resend", "seq": i, "delivered": True},
            )

        # Step 4: ACK
        yield narrate(
            "**Step 4.** Receiver completes the message → emits `STREAM_ACK`. "
            "Sender's `handle_ack()` drops its buffer.",
            title="Step 4 — ack",
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="message_assembler",
            payload={"event": "stream_ack", "total_chunks": 6, "ttl_used": False},
        )

        # Step 5: watchdog
        yield narrate(
            "If the receiver had gone silent, **WatchdogTimer** (NTP-checked clock) would "
            "have signalled a disconnect; `expire_old()` would have GC'd buffered chunks.",
            title="Bonus — watchdog",
        )
        yield narrate(
            "RETRANSMIT is sent **once** per gap to avoid retry storms / amplification. "
            "TTL guarantees buffers don't grow forever even on disconnect.",
            title="Take-away",
        )
