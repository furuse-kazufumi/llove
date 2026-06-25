"""Qt-side tail controller: poll a metrics file on a timer, emit new rows.

Wraps :class:`MetricsTailReader` (UI-independent) in a ``QObject`` that drives it
from a ``QTimer`` and emits ``rows_ready`` with each batch of new rows. For
Stage 1 the poll is a tiny incremental file read, so running it on the GUI thread
via ``QTimer`` is fine; the QThread worker model (design §4.2) is a Stage 2
hardening for heavier aggregation.

``poll_now`` does one synchronous read+emit so the controller is testable without
spinning an event loop.
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore

from llove.core.drivers.metrics_tail import MetricsTailReader


class MetricsTailController(QtCore.QObject):
    """Timer-driven poller that emits new metrics rows from a tailed file."""

    rows_ready = QtCore.Signal(list)

    def __init__(
        self,
        path: str | Path,
        interval_ms: int = 500,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._reader = MetricsTailReader(path)
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


__all__ = ["MetricsTailController"]
