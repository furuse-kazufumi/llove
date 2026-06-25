"""Offset-based tail reader for an evolution-run ``metrics.jsonl``.

Mirrors the ``TimelinePollDriver`` pattern (``views/llive/dispatch.py``): the
reader holds no loop and no timer — the caller (a Qt ``QTimer``, a Textual
``Timer``, or a CLI) decides when to ``poll()``, and each call returns only the
rows that became complete since the previous call.

Design rationale (llove_qt_gui_architecture §0.3 / §4): the evolution engine and
the GUI are decoupled at the file boundary, so the GUI follows a run by tailing
its output and never imports the engine. ``poll`` is **fail-closed**: a missing
file, a partial trailing line, a malformed line, or a non-UTF-8 byte run is
skipped rather than raised, so a half-flushed writer never crashes the reader.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from llove.core.viewmodels.fitness_trajectory import parse_metrics_row


class MetricsTailReader:
    """Read new, newline-terminated metrics rows since the last ``poll``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._offset = 0  # byte offset of the next unread position

    def poll(self) -> list[dict[str, Any]]:
        """Return metrics rows that became complete since the previous call.

        Only consumes bytes up to the last newline, so a partially-written final
        line is left for a later poll. Detects truncation/rewrite (a fresh run)
        by resetting the offset when the file shrinks below it.
        """
        if not self._path.exists():
            return []

        try:
            size = self._path.stat().st_size
        except OSError:
            return []
        if size < self._offset:
            # File was truncated or rewritten (e.g. a fresh run) — start over.
            self._offset = 0

        with self._path.open("rb") as fh:
            fh.seek(self._offset)
            data = fh.read()

        if not data:
            return []

        last_nl = data.rfind(b"\n")
        if last_nl == -1:
            return []  # no complete line available yet

        complete = data[: last_nl + 1]
        self._offset += len(complete)

        rows: list[dict[str, Any]] = []
        for raw in complete.split(b"\n"):
            if not raw.strip():
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            row = parse_metrics_row(text)
            if row is not None:
                rows.append(row)
        return rows

    def reset(self) -> None:
        """Forget progress so the next ``poll`` re-reads from the start."""
        self._offset = 0


__all__ = ["MetricsTailReader"]
