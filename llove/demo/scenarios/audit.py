"""Audit chain scenario — HMAC-chain tamper detection."""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind

_ENTRIES = [
    {"event": "firewall.allow", "user": "ops", "layer": "L2"},
    {"event": "rag.search", "query": "modbus replay defense", "hits": 5},
    {"event": "llm.complete", "model": "llama3.2", "tokens": 187},
    {"event": "audit.persist", "log_id": "a-0042"},
    {"event": "incident.report", "sensor_id": "bearing_temp_07", "cusum": 9.4},
]


class AuditChainScenario(DemoScenario):
    name = "audit"
    i18n_key = "audit"
    default_pause = 0.5

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.audit.intro", title_key="scenario.audit.intro_title")
        yield narrate_key("scenario.audit.step1", title_key="scenario.audit.step1_title")
        for i, entry in enumerate(_ENTRIES, start=1):
            yield Event(
                kind=EventKind.AUDIT,
                source_id="audit",
                payload={**entry, "seq": i, "hmac": f"deadbeef{i:02d}cafe"},
            )

        yield narrate_key("scenario.audit.step2", title_key="scenario.audit.step2_title")
        yield Event(
            kind=EventKind.AUDIT,
            source_id="audit",
            payload={"event": "TAMPERED!", "seq": 3, "note": "rewrote payload, kept old hmac"},
        )

        yield narrate_key("scenario.audit.step3", title_key="scenario.audit.step3_title")
        yield Event(
            kind=EventKind.AUDIT,
            source_id="audit",
            payload={
                "event": "verify_chain.failed",
                "broken_at_seq": 3,
                "reason": "prev_hmac mismatch",
            },
        )
        yield narrate_key("scenario.audit.takeaway", title_key="scenario.audit.takeaway_title")
