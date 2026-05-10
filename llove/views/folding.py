"""F15 (u) Foldable Blocks — UI-agnostic data + algorithm tier.

This module is intentionally widget-free. MarkdownView, NotebookView,
JSONTreeView etc. all delegate fold calculation here, so the same logic
covers every view kind (u6).

Public surface:
    FoldRegion        — one foldable span (kind/level/label/start/end)
    FoldState         — open/closed bookkeeping (toggle, close-all, ...)
    find_heading_regions(source)     — Markdown ATX-heading sections
    find_code_block_regions(source)  — fenced ```/~~~ code blocks
    find_table_regions(source)       — GFM pipe tables
    apply_folds(source, regions, state)
                      — collapse closed sections to a one-line summary
                        per spec (u4); return rendered text

Design notes:
    * Pure functions and a small dataclass — no Textual / Rich imports here.
    * Fail-closed (u10): any malformed input returns the source unchanged
      or an empty string; this layer must never raise into the UI.
    * Nesting (u5): when an outer section is closed it absorbs everything
      inside, including inner headings. When only an inner section is
      closed the outer chrome stays visible.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

# Compile once. ATX-only for v1 — Setext (`Title\n===`) can come later if a
# scenario actually needs it; pinning ATX keeps the surface predictable.
_RE_ATX_HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<label>.+?)\s*#*\s*$")
_RE_FENCE = re.compile(r"^\s*(```|~~~)")
# Match an opening code fence and capture its info-string (the language hint
# that appears after the backticks, e.g. ```python). The closing fence has no
# info string; we identify it by absence of language-only content rather than
# a separate regex.
_RE_FENCE_OPEN = re.compile(r"^\s*(?P<marker>```|~~~)\s*(?P<info>[^\s`~]*)\s*$")
# A GFM alignment row: pipes around dashes, optional colons for alignment,
# possibly with leading/trailing whitespace. Empty cells (just `--`) count.
_RE_TABLE_ALIGN = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_RE_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")


@dataclass(frozen=True)
class FoldRegion:
    """One foldable span, addressable by its first line index.

    `start_line` is the line that holds the "header" (e.g. the `## Title`
    line for headings, or the opening fence for code blocks). `end_line` is
    inclusive — the last line that belongs to the region. We use line indices
    rather than byte offsets so callers can plug into Textual's line-oriented
    widgets without re-tokenising.
    """

    kind: str
    level: int
    label: str
    start_line: int
    end_line: int


@dataclass
class FoldState:
    """Mutable open/closed bookkeeping keyed by `start_line`.

    Keyed on `start_line` (not on FoldRegion identity) so a re-parse of the
    same document — which produces fresh FoldRegion instances — keeps the
    user's existing fold state intact as long as line numbers haven't moved.
    Persistence to ~/.config/llove/folds/<doc-id>.toml (spec u3) layers on
    top of this; not in scope for this file.
    """

    closed_starts: set[int] = field(default_factory=set)

    def is_closed(self, start_line: int) -> bool:
        return start_line in self.closed_starts

    def toggle(self, start_line: int) -> None:
        if start_line in self.closed_starts:
            self.closed_starts.discard(start_line)
        else:
            self.closed_starts.add(start_line)

    def close(self, start_line: int) -> None:
        self.closed_starts.add(start_line)

    def open(self, start_line: int) -> None:
        # Method name shadows the builtin on purpose — it mirrors the zo/zc
        # verb pair the spec leans on (Vim foldopen / foldclose).
        self.closed_starts.discard(start_line)

    def close_all(self, regions: Iterable[FoldRegion]) -> None:
        for r in regions:
            self.closed_starts.add(r.start_line)

    def open_all(self) -> None:
        self.closed_starts.clear()

    def close_by_kind(self, regions: Iterable[FoldRegion], kind: str) -> None:
        for r in regions:
            if r.kind == kind:
                self.closed_starts.add(r.start_line)


def find_heading_regions(source: str) -> list[FoldRegion]:
    """Extract Markdown ATX heading sections from `source`.

    A "section" runs from its heading line to the line just before the next
    heading whose level is ≤ this one (siblings or shallower close us;
    deeper headings are absorbed as nested children — see u5). Code fences
    are skipped so a `# inside fence` is not mistaken for a heading.
    """
    if not isinstance(source, str) or not source:
        return []

    lines = source.splitlines()
    in_fence = False
    headings: list[tuple[int, int, str]] = []  # (start_line, level, label)
    for i, line in enumerate(lines):
        if _RE_FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _RE_ATX_HEADING.match(line)
        if not m:
            continue
        level = len(m.group("hashes"))
        label = m.group("label").strip()
        headings.append((i, level, label))

    if not headings:
        return []

    regions: list[FoldRegion] = []
    last_line = len(lines) - 1
    for idx, (start, level, label) in enumerate(headings):
        # Find the next heading whose level <= ours; that line - 1 is our end.
        end = last_line
        for j in range(idx + 1, len(headings)):
            other_start, other_level, _ = headings[j]
            if other_level <= level:
                end = other_start - 1
                break
        regions.append(
            FoldRegion(
                kind="heading",
                level=level,
                label=label,
                start_line=start,
                end_line=end,
            )
        )
    return regions


def apply_folds(
    source: str,
    regions: Iterable[FoldRegion],
    state: FoldState,
) -> str:
    """Collapse closed regions to a one-line summary; pass open content through.

    Per spec u4, a closed region renders as::

        ▶ ## Heading (N lines)

    where N is the count of body lines hidden (i.e. excluding the header
    line itself). Nested closed regions are absorbed by the outer fold —
    we walk top-to-bottom and skip any line covered by an already-emitted
    closed region.
    """
    if not isinstance(source, str):
        return ""
    if not source:
        return ""

    region_list = list(regions)
    if not region_list:
        return source

    closed = sorted(
        (r for r in region_list if state.is_closed(r.start_line)),
        key=lambda r: r.start_line,
    )
    if not closed:
        return source

    lines = source.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        # Is this line the start of a closed region we haven't emitted yet?
        match = next((r for r in closed if r.start_line == i), None)
        if match is None:
            out.append(lines[i])
            i += 1
            continue
        # Build the summary line. body = lines (i+1 .. end_line) inclusive.
        hidden = match.end_line - match.start_line  # number of body lines
        hashes = "#" * match.level if match.kind == "heading" else ""
        prefix = f"{hashes} " if hashes else ""
        out.append(f"▶ {prefix}{match.label} ({hidden} lines)")
        # Skip everything inside, including any nested closed regions.
        i = match.end_line + 1

    return "\n".join(out)
