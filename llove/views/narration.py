r"""NarrationView — show scenario commentary in a Markdown-flavoured pane.

Each ``Event`` of kind ``NARRATION`` carries:
    payload = {"text": "...", "title": "(optional)"}

The view shows the most recent few entries with the latest at the top, so a
demo can build a running story. Plain text is supported; very lightweight
Rich tag substitution renders bold (``**word**``) and inline code (``\`x\```).
"""
from __future__ import annotations

import re
from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

_RE_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_RE_CODE = re.compile(r"`([^`]+)`")


class NarrationView(Static, View):
    """Bottom pane that narrates what is happening in the demo."""

    name = "narration"
    title = "Narration"

    DEFAULT_CSS = """
    NarrationView {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 4) -> None:
        super().__init__("[dim](no narration yet — waiting for the scenario to begin)[/dim]")
        self._entries: deque[str] = deque(maxlen=limit)

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.NARRATION:
            return
        text = str(event.payload.get("text", "")).strip()
        if not text:
            return
        title = event.payload.get("title")
        ts = event.ts.strftime("%H:%M:%S")
        head = f"[dim]{ts}[/dim]"
        if title:
            head += f"  [bold]{title}[/bold]"
        body = self._lite_markdown(text)
        self._entries.appendleft(f"{head}\n  {body}")
        self.update("\n\n".join(self._entries))

    @staticmethod
    def _lite_markdown(text: str) -> str:
        """Apply minimal Markdown→Rich substitutions, safely escaping the rest."""
        # Escape any pre-existing Rich tags first.
        text = text.replace("[", r"\[")
        text = _RE_BOLD.sub(r"[bold]\1[/bold]", text)
        text = _RE_CODE.sub(r"[reverse]\1[/reverse]", text)
        return text
