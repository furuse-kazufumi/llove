"""Stage 3 panel P6: quality-diversity archive coverage (PySide6 + pyqtgraph).

A thin view over :class:`QdArchiveVM`. Plots ``archive_cells`` (cumulative niche
coverage, non-decreasing) and ``occupied_cells`` (live occupancy) per generation;
the widening gap between the two lines is the exploration-vs-convergence story of
an open-ended / QD run (the archive keeps the discovered niches even as the live
population collapses toward a few). Same shape as the other trajectory panels
(``feed_rows`` returns the accepted count, redraw only on change), so the shell
can wire the QD metrics tail straight to it.
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6 import QtWidgets

from llove.core.viewmodels.qd_archive import QdArchiveVM

_ARCHIVE_PEN = pg.mkPen("#16a085", width=2)   # teal — cumulative archive
_OCCUPIED_PEN = pg.mkPen("#e67e22", width=2)  # orange — live occupancy


class QdArchivePanel(QtWidgets.QWidget):
    """Plot QD ``archive_cells`` and ``occupied_cells`` per generation, fed row-by-row."""

    def __init__(
        self,
        vm: QdArchiveVM | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = vm if vm is not None else QdArchiveVM()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.addLegend(offset=(-10, 10))
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "generation")
        self.plot.setLabel("left", "niches (cells)")
        layout.addWidget(self.plot)

        self.archive_curve = self.plot.plot(
            [], [], pen=_ARCHIVE_PEN, name="archive_cells", connect="finite"
        )
        self.occupied_curve = self.plot.plot(
            [], [], pen=_OCCUPIED_PEN, name="occupied_cells", connect="finite"
        )
        self.refresh()

    def feed_rows(self, rows: list[dict[str, Any]]) -> int:
        """Feed parsed QD metrics rows to the view-model; redraw if any were added."""
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
        self.archive_curve.setData(s["generation"], s["archive_cells"])
        self.occupied_curve.setData(s["generation"], s["occupied_cells"])


__all__ = ["QdArchivePanel"]
