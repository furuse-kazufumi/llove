"""Stage 1 panel: live fitness-trajectory plot (PySide6 + pyqtgraph).

A thin view over :class:`FitnessTrajectoryVM`: the view-model owns the data and
all parsing logic, the panel only paints. ``feed_rows`` returns how many rows
were accepted so callers (or the tail controller) can skip a redraw when nothing
changed. ``nan`` gaps (missing median/std) are drawn with ``connect="finite"``.
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6 import QtWidgets

from llove.core.viewmodels.fitness_trajectory import FitnessTrajectoryVM

# Colour-blind-friendly, no red/green status semantics (these are data series,
# not pass/fail — see project OUTPUT STYLE: no 🔴/🟢).
_BEST_PEN = pg.mkPen("#e67e22", width=2)  # orange
_MEAN_PEN = pg.mkPen("#2980b9", width=2)  # blue
_MEDIAN_PEN = pg.mkPen("#7f8c8d", width=1, style=pg.QtCore.Qt.PenStyle.DashLine)  # grey dashed


class FitnessTrajectoryPanel(QtWidgets.QWidget):
    """Plot best/mean/median fitness per generation, fed row-by-row."""

    def __init__(
        self,
        vm: FitnessTrajectoryVM | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = vm if vm is not None else FitnessTrajectoryVM()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.addLegend(offset=(-10, 10))
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "generation")
        self.plot.setLabel("left", "score")
        layout.addWidget(self.plot)

        self.best_curve = self.plot.plot([], [], pen=_BEST_PEN, name="best", connect="finite")
        self.mean_curve = self.plot.plot([], [], pen=_MEAN_PEN, name="mean", connect="finite")
        self.median_curve = self.plot.plot(
            [], [], pen=_MEDIAN_PEN, name="median", connect="finite"
        )
        self.refresh()

    def feed_rows(self, rows: list[dict[str, Any]]) -> int:
        """Feed parsed metrics rows to the view-model; redraw if any were added."""
        added = 0
        for row in rows:
            if self.vm.feed(row):
                added += 1
        if added:
            self.refresh()
        return added

    def refresh(self) -> None:
        """Repaint all curves from the current view-model series."""
        s = self.vm.series()
        gen = s["generation"]
        self.best_curve.setData(gen, s["best"])
        self.mean_curve.setData(gen, s["mean"])
        self.median_curve.setData(gen, s["median"])


__all__ = ["FitnessTrajectoryPanel"]
