"""Qt-side tail controllers: poll a JSONL file on a timer, emit new rows.

Wraps the UI-independent readers (``MetricsTailReader`` / ``JsonlTailReader``) in
``QObject``s that drive them from a ``QTimer`` and emit ``rows_ready`` with each
batch of new rows. For Stage 1/3 the poll is a tiny incremental file read, so
running it on the GUI thread via ``QTimer`` is fine; the QThread worker model
(design §4.2) is a later hardening for heavier aggregation.

``poll_now`` does one synchronous read+emit so controllers are testable without
spinning an event loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PySide6 import QtCore

from llove.core.drivers.jsonl_tail import JsonlTailReader
from llove.core.drivers.metrics_tail import MetricsTailReader


class _Reader(Protocol):
    def poll(self) -> list[dict]: ...


class _TailController(QtCore.QObject):
    """Timer-driven poller that emits new rows from a tailed JSONL reader."""

    rows_ready = QtCore.Signal(list)

    def __init__(
        self,
        reader: _Reader,
        interval_ms: int = 500,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._reader = reader
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.poll_now)

    def start(self) -> None:
        """Read whatever already exists, then poll on the timer."""
        self.poll_now()
        self._timer.start()

    def stop(self) -> None:
        """Stop polling (the file is left untouched)."""
        self._timer.stop()

    @QtCore.Slot()
    def poll_now(self) -> None:
        """One synchronous read; emit ``rows_ready`` only if there are new rows."""
        rows = self._reader.poll()
        if rows:
            self.rows_ready.emit(rows)


class MetricsTailController(_TailController):
    """Tail a ``metrics.jsonl`` and emit parsed metrics rows."""

    def __init__(
        self,
        path: str | Path,
        interval_ms: int = 500,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(MetricsTailReader(path), interval_ms, parent)


class JsonlTailController(_TailController):
    """Tail an arbitrary JSONL file and emit raw JSON-object rows."""

    def __init__(
        self,
        path: str | Path,
        interval_ms: int = 500,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(JsonlTailReader(path), interval_ms, parent)


__all__ = ["JsonlTailController", "MetricsTailController"]
