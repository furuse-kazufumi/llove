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
from pathlib import Path

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
from llove.views.folding_persistence import (
    default_fold_state_path,
    load_fold_state,
    save_fold_state,
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

    def __init__(
        self,
        *,
        limit: int = 4,
        width: int = 100,
        doc_id: str | None = None,
        fold_persist_dir: Path | None = None,
    ) -> None:
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
        # F15 (u3) persistence wiring. With a doc_id we read the previous
        # FoldState from disk on construction and write back on every mutating
        # fold operation. Without one, persistence is silently disabled —
        # legacy callers keep their existing behaviour.
        self._doc_id: str | None = doc_id
        self._fold_persist_dir: Path | None = fold_persist_dir
        # F15 (u): foldable blocks. We keep a single FoldState attached to the
        # view; folds apply to the *latest* entry's user text (where the user
        # is currently looking and interacting). Older history entries always
        # pass through verbatim — folding them would surprise users browsing
        # back through narration. State is keyed on line numbers (in
        # `last_source`), so a re-feed of the same document keeps folds shut.
        self.fold_state: FoldState = self._load_fold_state_or_empty()
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
        """Return every foldable region in the *latest* entry's user text.

        Headings, fenced code blocks, and GFM tables are surfaced together
        and sorted by `start_line`, so a single "toggle fold on this line"
        command works regardless of construct kind.
        """
        src = self.last_source
        regions = (
            find_heading_regions(src)
            + find_code_block_regions(src)
            + find_table_regions(src)
        )
        return sorted(regions, key=lambda r: (r.start_line, r.end_line))

    def toggle_fold(self, start_line: int) -> None:
        """Toggle the fold whose region starts at `start_line` (0-indexed)."""
        self.fold_state.toggle(start_line)
        self._render()
        self._persist_fold_state()

    def close_all_folds(self) -> None:
        """Close every foldable region in the latest entry (Vim `zM`)."""
        self.fold_state.close_all(self.fold_regions())
        self._render()
        self._persist_fold_state()

    def open_all_folds(self) -> None:
        """Open every fold (Vim `zR`)."""
        self.fold_state.open_all()
        self._render()
        self._persist_fold_state()

    def save_folds(self) -> None:
        """Public hook to flush the current fold state to disk.

        Useful when the caller mutates `fold_state` directly (bypassing the
        normal toggle / close-all path) or wants to force a write at app
        shutdown. No-op when persistence is disabled (no `doc_id`).
        """
        self._persist_fold_state()

    # ------------------------------------------------------------------
    # F15 (u3) persistence helpers
    # ------------------------------------------------------------------
    def _fold_state_path(self) -> Path | None:
        """Resolve the on-disk path for our doc_id, or None if disabled."""
        if not self._doc_id:
            return None
        try:
            return default_fold_state_path(
                self._doc_id, base_dir=self._fold_persist_dir
            )
        except ValueError:
            # An invalid doc_id (path traversal, empty, etc.) silently
            # disables persistence rather than crashing the view.
            return None

    def _load_fold_state_or_empty(self) -> FoldState:
        path = self._fold_state_path()
        if path is None:
            return FoldState()
        try:
            return load_fold_state(path)
        except Exception:  # nosec B110 — fail-closed: never crash the view.
            return FoldState()

    def _persist_fold_state(self) -> None:
        path = self._fold_state_path()
        if path is None or not self._doc_id:
            return
        try:
            save_fold_state(self.fold_state, path, doc_id=self._doc_id)
        except Exception:  # nosec B110 — fail-closed: I/O hiccups don't crash UI.
            return

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
        regions = self.fold_regions()
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


def make_markdown_fold_hook(view: MarkdownView):
    """Return a callable suitable for `ctx.hooks['fold']` (F15 u8 wiring).

    The `:fold` builtin command treats the hook as a verb dispatcher:
    `(verb, args)` → `tuple[str, ...] | None`. Returning ``None`` signals
    "this view does not understand the verb"; the dispatcher then surfaces
    that to the user as an error rather than silently dropping the request.

    Supported verbs:
        close-all      — close every fold in the latest entry
        open-all       — open every fold
        by-tag <kind>  — close only folds whose `kind` matches (heading /
                         code / table)
        toggle <line>  — toggle the fold whose region starts at <line>
                         (integer; non-integer arg returns None)
    """

    def hook(verb: str, args: list[str]) -> tuple[str, ...] | None:
        if verb == "close-all":
            before = len(view.fold_state.closed_starts)
            view.close_all_folds()
            after = len(view.fold_state.closed_starts)
            return (f"closed {after - before} fold(s) (total {after})",)
        if verb == "open-all":
            view.open_all_folds()
            return ("opened all folds",)
        if verb == "by-tag":
            if not args:
                return None
            kind = args[0]
            valid = {"heading", "code", "table"}
            if kind not in valid:
                return None
            regions = view.fold_regions()
            view.fold_state.close_by_kind(regions, kind)
            view._render()
            count = sum(1 for r in regions if r.kind == kind)
            return (f"closed {count} {kind} fold(s)",)
        if verb == "toggle":
            if not args:
                return None
            try:
                line = int(args[0])
            except ValueError:
                return None
            view.toggle_fold(line)
            state = "closed" if view.fold_state.is_closed(line) else "open"
            return (f"fold at line {line} now {state}",)
        return None

    return hook
