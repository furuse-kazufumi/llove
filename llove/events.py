"""Unified event model for llove.

Every DataSource yields ``Event``s. Every View consumes them.
A single union type keeps the wire format simple and makes serialisation
to JSON Lines straightforward.
"""
from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventKind(str, Enum):
    """The kind of event flowing through the pipeline."""

    SENSOR = "sensor"
    SPC_ALARM = "spc_alarm"
    AUDIT = "audit"
    RAG_HIT = "rag_hit"
    LLM_CALL = "llm_call"
    TRACE_SPAN = "trace_span"
    INFO = "info"


class Event(BaseModel):
    """A single observation flowing through llove.

    The shape is intentionally permissive: ``payload`` is a free-form dict so
    DataSources can ferry arbitrary data without rigid up-front schemas. Views
    pick the fields they care about and ignore the rest.
    """

    kind: EventKind
    ts: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    source_id: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}

    def short(self) -> str:
        """One-line, human-readable summary for compact log views."""
        ts = self.ts.strftime("%H:%M:%S")
        head = f"{ts}  {self.kind.value:10}"
        if self.kind == EventKind.SENSOR:
            sid = self.payload.get("sensor_id", "?")
            val = self.payload.get("value", "?")
            return f"{head}  {sid}={val}"
        if self.kind == EventKind.SPC_ALARM:
            sid = self.payload.get("sensor_id", "?")
            cusum = self.payload.get("cusum", "?")
            return f"{head}  ALARM {sid} cusum={cusum}"
        if self.kind == EventKind.AUDIT:
            event = self.payload.get("event", "?")
            return f"{head}  {event}"
        if self.kind == EventKind.RAG_HIT:
            score = self.payload.get("score", "?")
            text = self.payload.get("text", "")[:60]
            return f"{head}  score={score}  {text}"
        if self.kind == EventKind.LLM_CALL:
            tokens = self.payload.get("tokens", "?")
            latency = self.payload.get("latency_ms", "?")
            return f"{head}  tokens={tokens}  latency={latency}ms"
        return f"{head}  {self.payload}"
