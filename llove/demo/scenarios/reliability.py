"""Reliability scenario — MessageAssembler + ChunkSender + WatchdogTimer."""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind


class ReliabilityScenario(DemoScenario):
    name = "reliability"
    i18n_key = "reliability"
    default_pause = 0.45

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.reliability.intro", title_key="scenario.reliability.intro_title")

        yield narrate_key("scenario.reliability.step1", title_key="scenario.reliability.step1_title")
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

        yield narrate_key("scenario.reliability.step2", title_key="scenario.reliability.step2_title")
        yield Event(
            kind=EventKind.AUDIT,
            source_id="message_assembler",
            payload={"event": "retransmit.request", "missing_seq": [3, 5]},
        )

        yield narrate_key("scenario.reliability.step3", title_key="scenario.reliability.step3_title")
        for i in (3, 5):
            yield Event(
                kind=EventKind.AUDIT,
                source_id="chunk_sender",
                payload={"event": "chunk.resend", "seq": i, "delivered": True},
            )

        yield narrate_key("scenario.reliability.step4", title_key="scenario.reliability.step4_title")
        yield Event(
            kind=EventKind.AUDIT,
            source_id="message_assembler",
            payload={"event": "stream_ack", "total_chunks": 6, "ttl_used": False},
        )

        yield narrate_key("scenario.reliability.watchdog", title_key="scenario.reliability.watchdog_title")
        yield narrate_key("scenario.reliability.takeaway", title_key="scenario.reliability.takeaway_title")
