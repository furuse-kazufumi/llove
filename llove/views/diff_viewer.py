"""DiffViewerView — AI 提案 vs 人手修正の diff を side-by-side で見る (Phase 6).

The explainability dashboard needs to show *where* a human edited an
AI-proposed artefact, not just that they did. This view consumes a
diff payload and renders it line-by-line with per-line markers:

    +  line added by the human
    -  line removed from the AI proposal
       unchanged context line

The diff is computed by :mod:`difflib` (stdlib) so there is no
dependency on git, gitpython, or similar.
"""

from __future__ import annotations

import difflib
from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View


def compute_diff_lines(ai_proposal: str, human_edited: str) -> list[tuple[str, str]]:
    """Return ``(marker, line)`` tuples for one ai → human comparison.

    Markers follow :func:`difflib.ndiff` semantics, simplified to the
    three cases this view needs: ``"+"`` / ``"-"`` / ``" "``. Lines from
    ``? ...`` hint rows are dropped because they would visually crowd
    the small view without adding information.
    """
    a = (ai_proposal or "").splitlines()
    b = (human_edited or "").splitlines()
    out: list[tuple[str, str]] = []
    for raw in difflib.ndiff(a, b):
        if not raw:
            continue
        head = raw[:1]
        body = raw[2:]
        if head in ("+", "-", " "):
            out.append((head, body))
        # else: '?' hints — drop
    return out


class DiffViewerView(Static, View):
    """Renders one or more proposal/edit pairs as a coloured diff."""

    name = "diff_viewer"
    title = "Diff viewer"

    DEFAULT_CSS = """
    DiffViewerView {
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, *, history: int = 1) -> None:
        super().__init__("(no diff)")
        # We keep the last ``history`` pairs so the view can show
        # iterations rather than just the freshest comparison. A
        # value of 1 (default) keeps the rendering compact.
        self._history = max(1, int(history))
        self._pairs: deque[tuple[str, list[tuple[str, str]]]] = deque(
            maxlen=self._history
        )
        self.border_title = "Diff viewer"
        self.border_subtitle = ""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def set_diff(
        self, *, ai_proposal: str, human_edited: str, label: str = ""
    ) -> None:
        diff_lines = compute_diff_lines(ai_proposal, human_edited)
        title = label or f"#{len(self._pairs) + 1}"
        self._pairs.append((title, diff_lines))
        self._redraw()

    def feed(self, event: Event) -> None:
        # NARRATION payloads piggyback this view to avoid expanding the
        # EventKind enum for what is effectively structured commentary.
        if event.kind != EventKind.NARRATION:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        diff = payload.get("diff")
        if not isinstance(diff, dict):
            return
        ai = diff.get("ai_proposal")
        hu = diff.get("human_edited")
        if not isinstance(ai, str) or not isinstance(hu, str):
            return
        label = diff.get("label")
        self.set_diff(
            ai_proposal=ai,
            human_edited=hu,
            label=label if isinstance(label, str) else "",
        )

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        if not self._pairs:
            self.update("(no diff)")
            self.border_subtitle = ""
            return
        blocks: list[str] = []
        total_added = 0
        total_removed = 0
        for label, lines in self._pairs:
            block_lines: list[str] = [f"[bold]{label}[/bold]"]
            for marker, body in lines:
                if marker == "+":
                    total_added += 1
                    block_lines.append(f"[green]+ {body}[/green]")
                elif marker == "-":
                    total_removed += 1
                    block_lines.append(f"[red]- {body}[/red]")
                else:
                    block_lines.append(f"[dim]  {body}[/dim]")
            blocks.append("\n".join(block_lines))
        self.border_subtitle = f"+{total_added} −{total_removed}"
        self.update("\n\n".join(blocks))


__all__ = ["DiffViewerView", "compute_diff_lines"]
