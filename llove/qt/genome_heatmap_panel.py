"""Stage 3 panel P5: genome heatmap (individuals x genes, PySide6 + pyqtgraph).

A thin view over :class:`GenomeHeatmapVM`: a pyqtgraph ``ImageItem`` shows each
individual's flattened ``c_factors`` weights as a colour-mapped heatmap, so sparse
vs saturated mutation is visible at a glance (design P5). Snapshots are discrete
files, so this panel is load-on-demand (``load_snapshot``) rather than tailed.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pyqtgraph as pg
from PySide6 import QtWidgets

from llove.core.viewmodels.genome_heatmap import GenomeHeatmapVM


class GenomeHeatmapPanel(QtWidgets.QWidget):
    """Heatmap of individuals (rows) x genes (columns) from a snapshot."""

    def __init__(
        self,
        vm: GenomeHeatmapVM | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = vm if vm is not None else GenomeHeatmapVM()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.glw = pg.GraphicsLayoutWidget()
        self.plot = self.glw.addPlot()
        self.plot.setLabel("bottom", "gene (factor#k)")
        self.plot.setLabel("left", "individual")
        self.plot.invertY(True)
        self.image = pg.ImageItem()
        self.image.setColorMap(pg.colormap.get("viridis"))
        self.plot.addItem(self.image)
        layout.addWidget(self.glw)
        self.refresh()

    def load_snapshot(self, snapshot: dict[str, Any]) -> int:
        """Load a snapshot dict; return the number of individuals plotted."""
        self.vm.load_snapshot(snapshot)
        self.refresh()
        return len(self.vm.heatmap.row_labels)

    def refresh(self) -> None:
        """Repaint the heatmap from the current view-model matrix."""
        matrix = self.vm.heatmap.matrix
        if not matrix:
            self.image.clear()
            return
        # rows = individuals (y), cols = genes (x). ImageItem takes (x, y),
        # so transpose to put genes on x and individuals on y.
        arr = np.asarray(matrix, dtype=float)
        self.image.setImage(arr.T, autoLevels=True)


__all__ = ["GenomeHeatmapPanel"]
