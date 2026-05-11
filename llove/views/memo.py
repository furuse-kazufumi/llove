"""QualitativeMemoView — free-form researcher memo (Phase 6).

The explainability dashboard needs a place for the human to scribble
"why this hypothesis felt wrong" or "interesting drift on day 3" —
qualitative context that no numeric chart captures. This view
accumulates time-stamped memos, newest first, and renders them with
the same lite-Markdown substitutions that :class:`NarrationView` uses
so reviewers can drop in ``**bold**`` and `` `code` `` highlights
without pulling in the full markdown stack.

Building on F15 (t1) MarkdownView and F17 WindowManager: this view
is intentionally separate from MarkdownView because memos are
append-only events, not a single editable buffer.
"""

from __future__ import annotations

import re
from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

_RE_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_RE_CODE = re.compile(r"`([^`]+)`")


class QualitativeMemoView(Static, View):
    """Append-only memo pane, newest entry on top."""

    name = "memo"
    title = "Memo"

    DEFAULT_CSS = """
    QualitativeMemoView {
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 16) -> None:
        super().__init__("(no memo)")
        self._limit = max(1, int(limit))
        self._entries: deque[str] = deque(maxlen=self._limit)
        self._count = 0
        self.border_title = "Memo"
        self.border_subtitle = ""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def add_memo(self, text: str, *, author: str = "", tag: str = "") -> None:
        body = (text or "").strip()
        if not body:
            return
        author_label = author.strip()
        tag_label = tag.strip()
        body = _RE_BOLD.sub(r"[bold]\1[/bold]", body.replace("[", r"\["))
        body = _RE_CODE.sub(r"[reverse]\1[/reverse]", body)
        head_bits: list[str] = []
        if author_label:
            head_bits.append(f"[cyan]{author_label}[/cyan]")
        if tag_label:
            head_bits.append(f"[dim]#{tag_label}[/dim]")
        head = "  ".join(head_bits)
        block = f"{head}\n  {body}" if head else f"  {body}"
        self._entries.appendleft(block)
        self._count += 1
        self.border_subtitle = f"memos:{self._count}"
        self.update("\n\n".join(self._entries))

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.NARRATION:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        memo = payload.get("memo")
        if not isinstance(memo, dict):
            return
        text = memo.get("text")
        if not isinstance(text, str):
            return
        self.add_memo(
            text,
            author=memo.get("author", "") if isinstance(memo.get("author"), str) else "",
            tag=memo.get("tag", "") if isinstance(memo.get("tag"), str) else "",
        )


__all__ = ["QualitativeMemoView"]
