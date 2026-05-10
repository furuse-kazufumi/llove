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
from llove.views.folding import (
    FoldRegion,
    FoldState,
    apply_folds,
    find_code_block_regions,
    find_heading_regions,
    find_table_regions,
)


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
        # F15 (u): foldable blocks. We keep a single FoldState attached to the
        # view; folds apply to the *latest* entry's user text (where the user
        # is currently looking and interacting). Older history entries always
        # pass through verbatim — folding them would surprise users browsing
        # back through narration. State is keyed on line numbers (in
        # `last_source`), so a re-feed of the same document keeps folds shut.
        self.fold_state: FoldState = FoldState()
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
        # Track raw source so callers can introspect what was last fed in,
        # and so fold operations have a stable substrate.
        self.last_source = text
        self._render()

    # ------------------------------------------------------------------
    # F15 (u) Foldable Blocks — public API
    # ------------------------------------------------------------------
    def fold_regions(self) -> list[FoldRegion]:
        """Return the foldable regions in the *latest* entry's user text."""
        return find_heading_regions(self.last_source)

    def toggle_fold(self, start_line: int) -> None:
        """Toggle the fold whose region starts at `start_line` (0-indexed)."""
        self.fold_state.toggle(start_line)
        self._render()

    def close_all_folds(self) -> None:
        """Close every foldable region in the latest entry (Vim `zM`)."""
        self.fold_state.close_all(self.fold_regions())
        self._render()

    def open_all_folds(self) -> None:
        """Open every fold (Vim `zR`)."""
        self.fold_state.open_all()
        self._render()

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------
    def _folded_latest_entry(self, entry: str) -> str:
        """Apply current fold state to the latest entry only.

        Older history entries are not folded — folding them would lose
        scroll-back context. We only operate on the entry whose user text
        equals `last_source` (i.e. the most recent feed).
        """
        if not self.fold_state.closed_starts:
            return entry
        if not self.last_source or not entry.endswith(self.last_source):
            return entry
        regions = find_heading_regions(self.last_source)
        if not regions:
            return entry
        folded = apply_folds(self.last_source, regions, self.fold_state)
        prefix = entry[: -len(self.last_source)]
        return prefix + folded

    def _render(self) -> None:
        """Rasterise the history (latest first) into both string + live widget."""
        rendered_chunks: list[str] = []
        live_chunks: list[str] = []
        for idx, entry in enumerate(self._entries):
            shown = self._folded_latest_entry(entry) if idx == 0 else entry
            rendered_chunks.append(_markdown_to_text(shown, width=self._width))
            live_chunks.append(shown)
        rendered = "\n".join(rendered_chunks)
        self.last_render = rendered

        # Live update for an actually-mounted widget. Rich Markdown is the
        # source of truth on screen; the string snapshot above is for tests,
        # exports, and SVG capture.
        try:
            self.update(Markdown("\n\n---\n\n".join(live_chunks)))
        except Exception:  # nosec B110 — fail-closed to plain text outside an App.
            self.update(rendered)
