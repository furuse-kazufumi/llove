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
from llove.i18n import t
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
        self._initial = t("ui.pane.narration.empty")
        super().__init__(self._initial)
        self._entries: deque[str] = deque(maxlen=limit)
        self._beats = 0
        # Mirror the latest rendered string so tests / external callers can
        # inspect what the user would see without diving into Textual internals.
        self.last_render: str = self._initial
        self.border_title = t("ui.pane.narration.title")
        self.border_subtitle = t("ui.pane.narration.subtitle_init")

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
            # Escape any user-provided '[' in the title so it can't break out
            # of our [bold]...[/bold] wrapper.
            safe_title = str(title).replace("[", r"\[")
            head += f"  [bold]{safe_title}[/bold]"
        body = self._lite_markdown(text)
        self._entries.appendleft(f"{head}\n  {body}")
        self._beats += 1
        latest = title if title else t("ui.pane.narration.title")
        self.border_subtitle = t(
            "ui.pane.narration.subtitle_active", beat=self._beats, latest=latest
        )
        rendered = "\n\n".join(self._entries)
        self.last_render = rendered
        self.update(rendered)

    @staticmethod
    def _lite_markdown(text: str) -> str:
        """Apply minimal Markdown→Rich substitutions, safely escaping the rest."""
        # Escape any pre-existing Rich tags first.
        text = text.replace("[", r"\[")
        text = _RE_BOLD.sub(r"[bold]\1[/bold]", text)
        text = _RE_CODE.sub(r"[reverse]\1[/reverse]", text)
        return text
