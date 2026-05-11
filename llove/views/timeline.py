"""TimelineView — time-ordered execution trace (Phase 0c).

Rolling tail of ``TRACE_SPAN`` events, rendered newest-at-bottom so a
research run reads top-to-bottom like a log. Pairs with
:class:`TaskGraphView`: the graph view shows *what* the workflow is,
the timeline shows *when* each step happened and how long it took.

Expected ``Event.payload`` (all optional — missing keys are rendered as
``?``):

    seq:         monotonically increasing entry index within a run
    trace_kind:  e.g. ``"agent.run"``, ``"tool.call"``, ``"llm.prompt"``
    actor:       producing agent or tool name
    node_id:     id within the enclosing :class:`TaskGraphView` (if any)
    duration_ms: wall-clock duration of the span, in milliseconds
"""

from __future__ import annotations

from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View


class TimelineView(Static, View):
    """Compact, append-only view of trace spans."""

    name = "timeline"
    title = "Execution timeline"

    DEFAULT_CSS = """
    TimelineView {
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 200) -> None:
        super().__init__("(no events)")
        self._rows: deque[str] = deque(maxlen=limit)
        self._count = 0
        self.border_title = "Execution timeline"
        self.border_subtitle = ""

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.TRACE_SPAN:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        ts = event.ts.strftime("%H:%M:%S")
        seq = payload.get("seq")
        seq_text = f"#{seq:>4}" if isinstance(seq, int) else "#   ?"
        trace_kind = str(payload.get("trace_kind", "?"))
        actor = str(payload.get("actor", "?"))
        node_id = payload.get("node_id")
        node_text = f" [{node_id}]" if isinstance(node_id, str) else ""
        duration_ms = payload.get("duration_ms")
        dur_text = ""
        if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
            dur_text = f" ({duration_ms:.0f}ms)"
        line = f"[dim]{ts}[/dim] {seq_text} [bold]{trace_kind:<14}[/bold] {actor}{node_text}{dur_text}"
        self._rows.append(line)
        self._count += 1
        self.border_subtitle = f"spans:{self._count}"
        self.update("\n".join(self._rows))


__all__ = ["TimelineView"]
