"""Stage 2 panel P7: run monitor — status + pause/resume/stop controls.

Shows a :class:`RunStatusVM` snapshot (status / fitness / generation / best /
seed / stop reason / elapsed) and offers Pause / Resume / Stop buttons that drop
a request via :class:`RunControl`. The run process honours those requests by
polling ``control.json`` (a llive-side contract; if the run ignores it the panel
still works as a read-only monitor — fail-open observation).
"""

from __future__ import annotations

from pathlib import Path

from PySide6 import QtWidgets

from llove.core.drivers.run_control import RunControl
from llove.core.viewmodels.run_status import RunStatus, RunStatusVM

# (label, RunStatus attribute) rows shown in the panel, in order.
_ROWS: tuple[tuple[str, str], ...] = (
    ("Status", "status"),
    ("Fitness", "fitness"),
    ("Generation", "_generation"),  # synthesised "cur / target"
    ("Best score", "best_score"),
    ("Seed", "seed"),
    ("Stopped reason", "stopped_reason"),
    ("Elapsed (s)", "elapsed_seconds"),
)


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


class RunMonitorPanel(QtWidgets.QWidget):
    """Read-only run status plus pause/resume/stop request buttons."""

    def __init__(self, run_dir: str | Path, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = RunStatusVM(run_dir)
        self.control = RunControl(run_dir)
        self.status: RunStatus = RunStatus()

        outer = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self._value_labels: dict[str, QtWidgets.QLabel] = {}
        for label, attr in _ROWS:
            value = QtWidgets.QLabel("—")
            self._value_labels[attr] = value
            form.addRow(QtWidgets.QLabel(f"{label}:"), value)
        outer.addLayout(form)

        buttons = QtWidgets.QHBoxLayout()
        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.resume_btn = QtWidgets.QPushButton("Resume")
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.pause_btn.clicked.connect(self.request_pause)
        self.resume_btn.clicked.connect(self.request_resume)
        self.stop_btn.clicked.connect(self.request_stop)
        for btn in (self.pause_btn, self.resume_btn, self.stop_btn):
            buttons.addWidget(btn)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        outer.addStretch(1)

        self.refresh()

    # ---- control requests (also the slots wired to the buttons) ----------
    def request_pause(self) -> None:
        self.control.pause()

    def request_resume(self) -> None:
        self.control.resume()

    def request_stop(self) -> None:
        self.control.stop()

    # ---- status ----------------------------------------------------------
    def refresh(self) -> None:
        """Re-read the run directory and repaint the status labels."""
        st = self.vm.refresh()
        self.status = st
        generation = (
            f"{_fmt(st.current_generation)} / {_fmt(st.target_generations)}"
            if st.target_generations is not None
            else _fmt(st.current_generation)
        )
        for attr, label in self._value_labels.items():
            if attr == "_generation":
                label.setText(generation)
            else:
                label.setText(_fmt(getattr(st, attr)))


__all__ = ["RunMonitorPanel"]
