"""AuditLogView — rolling tail of audit + LLM events."""
from __future__ import annotations

from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

_INTERESTING = {EventKind.AUDIT, EventKind.LLM_CALL, EventKind.RAG_HIT, EventKind.INFO}


class AuditLogView(Static, View):
    """Rolling list of audit-relevant events. Newest at the top."""

    name = "audit_log"
    title = "Audit log"

    DEFAULT_CSS = """
    AuditLogView {
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 12) -> None:
        super().__init__("(no audit events yet)")
        self._rows: deque[str] = deque(maxlen=limit)
        self._counts: dict[EventKind, int] = {k: 0 for k in _INTERESTING}
        self.border_title = "📋 Audit log — audit / LLM / RAG events"
        self.border_subtitle = "newest first"

    def feed(self, event: Event) -> None:
        if event.kind not in _INTERESTING:
            return
        self._rows.appendleft(event.short())
        self._counts[event.kind] = self._counts.get(event.kind, 0) + 1
        # Compact subtitle counter so users can see "what kinds happened".
        parts = [
            f"audit:{self._counts.get(EventKind.AUDIT, 0)}",
            f"llm:{self._counts.get(EventKind.LLM_CALL, 0)}",
            f"rag:{self._counts.get(EventKind.RAG_HIT, 0)}",
        ]
        self.border_subtitle = " · ".join(parts)
        self.update("\n".join(self._rows))
