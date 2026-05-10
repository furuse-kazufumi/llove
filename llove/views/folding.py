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


# ---------------------------------------------------------------------------
# F15 (u8) Presets
# ---------------------------------------------------------------------------

# Each preset is a predicate over (kind, level) that says
# "should this region be CLOSED under this preset?". Open is the default.
_FOLD_PRESETS: dict[str, "FoldPredicate"] = {}

FoldPredicate = "Callable[[str, int], bool]"  # forward-ish; see typing below


def _preset_outline(kind: str, level: int) -> bool:
    # Skeleton view: keep h1/h2 open, collapse everything else.
    if kind == "heading":
        return level >= 3
    return True


def _preset_code(kind: str, level: int) -> bool:
    # Focus on code: keep code blocks open, collapse the rest.
    return kind != "code"


def _preset_data_only(kind: str, level: int) -> bool:
    # Focus on tables.
    return kind != "table"


def _preset_prose(kind: str, level: int) -> bool:
    # Reading mode: collapse code and tables, leave headings open.
    return kind in ("code", "table")


_FOLD_PRESETS = {
    "outline": _preset_outline,
    "code": _preset_code,
    "data-only": _preset_data_only,
    "prose": _preset_prose,
}


def fold_preset_names() -> tuple[str, ...]:
    """Return the canonical preset names in stable order."""
    return tuple(sorted(_FOLD_PRESETS))


def apply_preset(
    state: FoldState,
    regions: Iterable[FoldRegion],
    preset: str,
) -> FoldState:
    """Apply a named preset to `state`, returning a new FoldState.

    Unknown preset names leave the input untouched (returned by value as a
    fresh FoldState so callers can swap freely without aliasing concerns).
    The function is idempotent: applying the same preset twice yields the
    same result.
    """
    predicate = _FOLD_PRESETS.get(preset)
    region_list = list(regions)
    if predicate is None:
        # Defensive copy so the caller can't mutate `state` through us.
        return FoldState(closed_starts=set(state.closed_starts))
    closed: set[int] = set()
    for r in region_list:
        if predicate(r.kind, r.level):
            closed.add(r.start_line)
    return FoldState(closed_starts=closed)


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


def find_code_block_regions(source: str) -> list[FoldRegion]:
    """Extract fenced code block regions (``` or ~~~ pairs) from `source`.

    Each region spans from the opening fence line through the closing fence
    line, both inclusive. The label carries the info-string (language hint)
    when present; otherwise it falls back to the literal ``"code"``.

    Fail-closed: a fence that is opened but never closed produces no region.
    Returning a phantom span would cause `apply_folds` to swallow the rest
    of the document, which is the wrong default for a malformed snippet.
    """
    if not isinstance(source, str) or not source:
        return []

    lines = source.splitlines()
    regions: list[FoldRegion] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = _RE_FENCE_OPEN.match(line)
        if not m:
            i += 1
            continue
        marker = m.group("marker")
        info = m.group("info") or "code"
        # Look for the matching closing fence (same marker family). A blank
        # info string is what closes; anything with text would re-open with a
        # different language, which we don't accept here.
        close_idx = -1
        for j in range(i + 1, n):
            stripped = lines[j].strip()
            if stripped == marker:
                close_idx = j
                break
        if close_idx == -1:
            # No closing fence — bail out (fail-closed).
            break
        regions.append(
            FoldRegion(
                kind="code",
                level=0,
                label=info.strip() or "code",
                start_line=i,
                end_line=close_idx,
            )
        )
        i = close_idx + 1
    return regions


def find_table_regions(source: str) -> list[FoldRegion]:
    """Extract GFM pipe-table regions (header row + alignment row + body).

    A table is recognised only when an alignment row (`|---|---|`) immediately
    follows a pipe-row header. Body rows continue while consecutive lines look
    like pipe rows; the first non-pipe row terminates the table. Tables
    inside fenced code blocks are skipped.
    """
    if not isinstance(source, str) or not source:
        return []

    lines = source.splitlines()
    regions: list[FoldRegion] = []
    in_fence = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _RE_FENCE.match(line):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        # We need at least header + alignment + ≥0 body rows. Header is a
        # pipe-row, alignment is the dashed row immediately after.
        if not _RE_TABLE_ROW.match(line):
            i += 1
            continue
        if i + 1 >= n or not _RE_TABLE_ALIGN.match(lines[i + 1]):
            i += 1
            continue
        # Count columns in the header for the label.
        cols = max(1, line.strip().strip("|").count("|") + 1)
        # Walk forward through body rows.
        end = i + 1  # alignment row is part of the table
        j = i + 2
        while j < n and _RE_TABLE_ROW.match(lines[j]):
            end = j
            j += 1
        regions.append(
            FoldRegion(
                kind="table",
                level=0,
                label=f"table ({cols} cols)",
                start_line=i,
                end_line=end,
            )
        )
        i = end + 1
    return regions


def _summary_line(region: FoldRegion, hidden: int) -> str:
    """Format a closed-region summary line per (u4)."""
    if region.kind == "heading":
        hashes = "#" * region.level
        return f"▶ {hashes} {region.label} ({hidden} lines)"
    if region.kind == "code":
        return f"▶ ```{region.label} ({hidden} lines)"
    if region.kind == "table":
        # Tables count rows rather than lines; "rows" reads more naturally
        # for a table fold, even though both are line counts internally.
        return f"▶ | {region.label} ({hidden} rows)"
    return f"▶ {region.label} ({hidden} lines)"


def apply_folds(
    source: str,
    regions: Iterable[FoldRegion],
    state: FoldState,
) -> str:
    """Collapse closed regions to a one-line summary; pass open content through.

    Per spec u4, a closed region renders as one of::

        ▶ ## Heading (N lines)
        ▶ ```python (N lines)
        ▶ | table (3 cols) (N rows)

    where N counts the body lines hidden. Nested closed regions are absorbed
    by the outer fold — we walk top-to-bottom and skip any line covered by an
    already-emitted closed region.
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
        hidden = match.end_line - match.start_line  # body line count
        out.append(_summary_line(match, hidden))
        # Skip everything inside, including any nested closed regions.
        i = match.end_line + 1

    return "\n".join(out)
