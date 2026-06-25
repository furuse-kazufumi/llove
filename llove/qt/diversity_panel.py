"""Stage 3 panel P2: live diversity-trajectory plot (PySide6 + pyqtgraph).

A thin view over :class:`DiversityTrajectoryVM`. Same shape as the fitness panel
(``feed_rows`` returns the accepted count, redraw only on change) and consumes
the same parsed metrics rows, so the shell can wire one metrics tail to both.
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6 import QtWidgets

from llove.core.viewmodels.diversity_trajectory import DiversityTrajectoryVM

_DIVERSITY_PEN = pg.mkPen("#8e44ad", width=2)  # purple


class DiversityTrajectoryPanel(QtWidgets.QWidget):
    """Plot population ``diversity_l2`` per generation, fed row-by-row."""

    def __init__(
        self,
        vm: DiversityTrajectoryVM | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = vm if vm is not None else DiversityTrajectoryVM()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.addLegend(offset=(-10, 10))
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "generation")
        self.plot.setLabel("left", "diversity (L2)")
        layout.addWidget(self.plot)

        self.diversity_curve = self.plot.plot(
            [], [], pen=_DIVERSITY_PEN, name="diversity_l2", connect="finite"
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
        """Repaint from the current view-model series."""
        s = self.vm.series()
        self.diversity_curve.setData(s["generation"], s["diversity"])


__all__ = ["DiversityTrajectoryPanel"]
