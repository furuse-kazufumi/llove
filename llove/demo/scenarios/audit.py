"""Audit chain scenario — HMAC-chain tamper detection.

Walks through:
    1. append 5 entries
    2. tamper with the middle one
    3. verify_chain() detects the tampered record
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind

_INTRO = (
    "**AuditTrail** chains every entry's HMAC into the next. "
    "Removing or modifying any entry breaks the chain — `verify_chain()` raises."
)

_ENTRIES = [
    {"event": "firewall.allow", "user": "ops", "layer": "L2"},
    {"event": "rag.search", "query": "modbus replay defense", "hits": 5},
    {"event": "llm.complete", "model": "llama3.2", "tokens": 187},
    {"event": "audit.persist", "log_id": "a-0042"},
    {"event": "incident.report", "sensor_id": "bearing_temp_07", "cusum": 9.4},
]


class AuditChainScenario(DemoScenario):
    name = "audit"
    title = "Audit — HMAC chain tamper detection"
    description = (
        "Append a few audit entries, then tamper with one and watch verify_chain() "
        "raise on the broken link."
    )
    default_pause = 0.5

    async def events(self) -> AsyncIterator[Event]:
        yield narrate(_INTRO, title="Scenario: Audit chain")

        # Step 1 — append entries
        yield narrate("**Step 1.** Append 5 entries — each gets `prev_hmac` chained from the last",
                      title="Step 1")
        for i, entry in enumerate(_ENTRIES, start=1):
            yield Event(
                kind=EventKind.AUDIT,
                source_id="audit",
                payload={**entry, "seq": i, "hmac": f"deadbeef{i:02d}cafe"},
            )

        # Step 2 — tamper
        yield narrate(
            "**Step 2.** An attacker rewrites entry **#3** in-place. "
            "The stored HMAC is now stale relative to the chained `prev_hmac` of #4.",
            title="Step 2 — tamper",
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="audit",
            payload={"event": "TAMPERED!", "seq": 3, "note": "rewrote payload, kept old hmac"},
        )

        # Step 3 — verify
        yield narrate(
            "**Step 3.** Operator runs `verify_chain()` — entry #4's `prev_hmac` no longer "
            "matches recomputed HMAC of #3 → **chain broken at seq=3**",
            title="Step 3 — verify",
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="audit",
            payload={
                "event": "verify_chain.failed",
                "broken_at_seq": 3,
                "reason": "prev_hmac mismatch",
            },
        )
        yield narrate(
            "Tamper-evident, not tamper-proof. The attacker cannot silently rewrite history; "
            "the broken link is forensic evidence.",
            title="Take-away",
        )
