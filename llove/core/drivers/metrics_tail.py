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

from llove.core.drivers._tail import read_new_complete_lines
from llove.core.viewmodels.fitness_trajectory import parse_metrics_row


class MetricsTailReader:
    """Read new, newline-terminated metrics rows since the last ``poll``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._offset = 0  # byte offset of the next unread position

    def poll(self) -> list[dict[str, Any]]:
        """Return metrics rows that became complete since the previous call.

        Only consumes bytes up to the last newline, so a partially-written final
        line is left for a later poll. Detects a rewrite (a fresh run) when the
        file **shrinks** below the consumed offset and resets.

        Honest limitation: an in-place rewrite to the *same or larger* size
        cannot be distinguished from an append using ``stat`` alone, so it is not
        auto-detected — point the reader at the new run's path, or call
        :meth:`reset`. In practice runs write to a fresh ``out/<run>/`` path, so
        this edge does not arise during normal tailing.
        """
        lines, self._offset = read_new_complete_lines(self._path, self._offset)
        rows: list[dict[str, Any]] = []
        for line in lines:
            row = parse_metrics_row(line)
            if row is not None:
                rows.append(row)
        return rows

    def reset(self) -> None:
        """Forget progress so the next ``poll`` re-reads from the start."""
        self._offset = 0


__all__ = ["MetricsTailReader"]
