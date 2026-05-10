"""F15 (t1) MarkdownView — full GFM successor of NarrationView.

NarrationView only knows two markdown constructs (bold and inline code) and
escapes everything else. MarkdownView is the upgrade path: any payload string
is treated as a Markdown document and rendered through Rich's `Markdown`
backend (markdown-it-py), so headings, lists, fenced code, blockquotes,
tables, and the rest of the GFM surface render natively in the terminal.

It exposes the same lifecycle contract as NarrationView (`feed(event)`,
`last_render`, NARRATION-only filter, latest-first history) so call-sites can
swap one for the other.
"""

from __future__ import annotations

from collections import deque
from io import StringIO

from rich.console import Console
from rich.markdown import Markdown
from textual.widgets import Static

from llove.events import Event, EventKind
from llove.i18n import t
from llove.views.base import View
from llove.views.folding import FoldRegion, FoldState, apply_folds, find_heading_regions


def _markdown_to_text(source: str, *, width: int = 100) -> str:
    """Render `source` through Rich Markdown into a plain string snapshot.

    We rasterise to a string so tests, exports, and headless callers can read
    what the user would see without mounting a Textual App. The terminal
    widget itself updates with a live `Markdown` instance so colour and styles
    survive there.
    """
    buf = StringIO()
    console = Console(
        file=buf,
        width=width,
        force_terminal=False,
        color_system=None,
        record=False,
    )
    console.print(Markdown(source))
    return buf.getvalue()


class MarkdownView(Static, View):
    """Pane that renders NARRATION events as full GFM Markdown documents."""

    name = "markdown"
    title = "Markdown"

    DEFAULT_CSS = """
    MarkdownView {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 4, width: int = 100) -> None:
        # Localised placeholder mirrors NarrationView so the i18n surface is
        # consistent across both panes; we fall back to a literal if a key is
        # missing in a particular locale.
        try:
            self._initial = t("ui.pane.markdown.empty")
        except Exception:  # nosec B110 — i18n key may not be defined yet.
            self._initial = "_(no markdown yet)_"
        super().__init__(self._initial)
        self._entries: deque[str] = deque(maxlen=limit)
        self._beats = 0
        self._width = width
        self.last_source: str = ""
        self.last_render: str = self._initial
        try:
            self.border_title = t("ui.pane.markdown.title")
        except Exception:  # nosec B110 — i18n missing key.
            self.border_title = "Markdown"

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.NARRATION:
            return
        raw = event.payload.get("text") if isinstance(event.payload, dict) else None
        if not isinstance(raw, str):
            return
        text = raw.strip()
        if not text:
            return
        title = event.payload.get("title") if isinstance(event.payload, dict) else None
        ts = event.ts.strftime("%H:%M:%S")
        # Build the markdown document for this entry.
        # Keep timestamp + title inline as a small header so latest-first
        # history reads naturally.
        header = f"**{ts}** — _{title}_\n\n" if title else f"**{ts}**\n\n"
        document = header + text
        self._entries.appendleft(document)
        self._beats += 1
        # Track raw source so callers can introspect what was last fed in.
        self.last_source = text

        # Rasterise the full history (latest first) into a text snapshot.
        rendered_chunks: list[str] = []
        for entry in self._entries:
            rendered_chunks.append(_markdown_to_text(entry, width=self._width))
        rendered = "\n".join(rendered_chunks)
        self.last_render = rendered

        # Live update for an actually-mounted widget. Rich Markdown is the
        # source of truth on screen; the string snapshot above is for tests,
        # exports, and SVG capture.
        try:
            self.update(Markdown("\n\n---\n\n".join(self._entries)))
        except Exception:  # nosec B110 — fail-closed to plain text outside an App.
            self.update(rendered)
