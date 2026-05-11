"""HypothesisBoardView — explainability board of hypothesis candidates (Phase 6).

Renders the hypothesis candidates emitted by llmesh's research pipeline
(Phase 2 `HypothesisAgent`) as a labelled board so a researcher can see
at a glance which candidate is approved, under review, or rejected and
read the falsifier / variables for each.

The view consumes ``Event(kind=NARRATION)`` with payload shape
``{"hypothesis": <dict>}`` or ``{"hypotheses": [<dict>, ...]}``. A
dict-only schema keeps it framework-neutral: tests can feed plain
dicts without importing llmesh.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

# Status -> (glyph, colour tag) used for the heading line of each card.
_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "proposed": ("o", "cyan"),
    "under_review": (">", "yellow"),
    "approved": ("+", "green"),
    "rejected": ("x", "red"),
    "withdrawn": ("-", "dim"),
}
_VALID_STATUSES = frozenset(_STATUS_STYLE)


def _coerce_dict(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return item
    return None


class HypothesisBoardView(Static, View):
    """Card-style board of hypotheses with per-card status.

    Each card occupies three lines:
        STATUS_GLYPH id  [bold]statement[/bold]
                    iv=... dv=... effect=...
                    falsifier=...
    """

    name = "hypothesis_board"
    title = "Hypothesis board"

    DEFAULT_CSS = """
    HypothesisBoardView {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 12) -> None:
        super().__init__("(no hypotheses)")
        self._limit = max(1, int(limit))
        # OrderedDict preserves insertion order so the board reads top
        # to bottom in the order hypotheses arrived.
        self._cards: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.border_title = "Hypothesis board"
        self.border_subtitle = ""

    # ------------------------------------------------------------------
    # public API (also reachable via feed())
    # ------------------------------------------------------------------

    def add_hypothesis(self, hypothesis: dict[str, Any]) -> None:
        """Add or replace one hypothesis card. Missing 'id' is filled
        with the index, so plain Phase 2 mocks (which carry no id)
        still render."""
        coerced = _coerce_dict(hypothesis)
        if coerced is None:
            return
        # Default id: deterministic per insertion order
        hid = str(coerced.get("id") or f"h{len(self._cards) + 1}")
        status = str(coerced.get("status") or "proposed").lower()
        if status not in _VALID_STATUSES:
            status = "proposed"
        card = {
            "id": hid,
            "statement": str(coerced.get("statement") or "").strip(),
            "independent_variable": str(coerced.get("independent_variable") or "").strip(),
            "dependent_variable": str(coerced.get("dependent_variable") or "").strip(),
            "expected_effect": str(coerced.get("expected_effect") or "").strip(),
            "falsifier": str(coerced.get("falsifier") or "").strip(),
            "status": status,
        }
        if not card["statement"]:
            return  # silently drop unusable card; keeps board readable
        # If an existing card with the same id is present, refresh it in
        # place so status transitions update the same row.
        if hid in self._cards:
            self._cards.pop(hid)
        self._cards[hid] = card
        # Evict oldest cards beyond the limit.
        while len(self._cards) > self._limit:
            self._cards.popitem(last=False)
        self._redraw()

    def set_status(self, hypothesis_id: str, status: str) -> None:
        if hypothesis_id not in self._cards:
            return
        s = str(status).lower()
        if s not in _VALID_STATUSES:
            return
        self._cards[hypothesis_id]["status"] = s
        self._redraw()

    def feed(self, event: Event) -> None:
        # We piggyback on the NARRATION kind to avoid expanding EventKind
        # for what is essentially structured commentary. The dispatcher
        # checks for explicit board payloads only.
        if event.kind != EventKind.NARRATION:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        h = payload.get("hypothesis")
        if isinstance(h, dict):
            self.add_hypothesis(h)
            return
        hs = payload.get("hypotheses")
        if isinstance(hs, list):
            for item in hs:
                if isinstance(item, dict):
                    self.add_hypothesis(item)
            return
        status_change = payload.get("hypothesis_status")
        if isinstance(status_change, dict):
            hid = status_change.get("id")
            status = status_change.get("status")
            if isinstance(hid, str) and isinstance(status, str):
                self.set_status(hid, status)

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        if not self._cards:
            self.update("(no hypotheses)")
            self.border_subtitle = ""
            return
        lines: list[str] = []
        counts: dict[str, int] = {}
        for card in self._cards.values():
            status = card["status"]
            counts[status] = counts.get(status, 0) + 1
            glyph, colour = _STATUS_STYLE[status]
            head = (
                f"[{colour}]{glyph}[/{colour}] [bold]{card['id']}[/bold]  "
                f"{card['statement']}"
            )
            meta = (
                f"   iv={card['independent_variable'] or '-'}  "
                f"dv={card['dependent_variable'] or '-'}  "
                f"effect={card['expected_effect'] or '-'}"
            )
            falsifier = f"   falsifier: {card['falsifier'] or '-'}"
            lines.extend([head, meta, falsifier, ""])
        if lines and lines[-1] == "":
            lines.pop()  # trailing blank
        self.border_subtitle = " · ".join(f"{k}:{v}" for k, v in counts.items() if v)
        self.update("\n".join(lines))


__all__ = ["HypothesisBoardView"]
