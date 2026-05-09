"""AuditLogView — rolling tail of audit + LLM events."""

from __future__ import annotations

from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.i18n import t
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
        super().__init__(t("ui.pane.audit_log.empty"))
        self._rows: deque[str] = deque(maxlen=limit)
        self._counts: dict[EventKind, int] = {k: 0 for k in _INTERESTING}
        self.border_title = t("ui.pane.audit_log.title")
        self.border_subtitle = t("ui.pane.audit_log.subtitle_init")

    def feed(self, event: Event) -> None:
        if event.kind not in _INTERESTING:
            return
        # Scenarios may pre-format an audit line via payload['display'] (e.g.
        # shogi turns USI into '▲７六歩'). Fall back to Event.short() otherwise
        # so existing audit consumers keep their current rendering.
        display = event.payload.get("display") if isinstance(event.payload, dict) else None
        if display:
            ts = event.ts.strftime("%H:%M:%S")
            line = f"{ts}  {display}"
        else:
            line = event.short()
        self._rows.appendleft(line)
        self._counts[event.kind] = self._counts.get(event.kind, 0) + 1
        # Compact subtitle counter so users can see what kinds happened. We
        # keep it locale-neutral (kind values + numbers) — the locale-specific
        # *labels* live in the border title above and in the audit messages.
        parts = [
            f"audit:{self._counts.get(EventKind.AUDIT, 0)}",
            f"llm:{self._counts.get(EventKind.LLM_CALL, 0)}",
            f"rag:{self._counts.get(EventKind.RAG_HIT, 0)}",
        ]
        self.border_subtitle = " · ".join(parts)
        self.update("\n".join(self._rows))
