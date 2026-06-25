"""Stage 3 panel P4: founder/persona dominance over generations.

A thin view over :class:`PersonaDominanceVM`: one line per founder showing its
population *share* across generations. ``feed_rows`` accepts founder-lineage rows
(from a generic JSONL tail) and rebuilds the curves. Because the founder set can
grow as new founders appear, the curve set is rebuilt on change rather than
appended (founder count is small, so this is cheap).
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6 import QtWidgets

from llove.core.viewmodels.persona_dominance import PersonaDominanceVM

# A categorical palette (no red/green status semantics — these are founders).
_PALETTE = (
    "#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b",
    "#e377c2", "#17becf", "#bcbd22", "#7f7f7f", "#d62728",
)


class PersonaDominancePanel(QtWidgets.QWidget):
    """Plot each founder's population share per generation."""

    def __init__(
        self,
        vm: PersonaDominanceVM | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = vm if vm is not None else PersonaDominanceVM()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.addLegend(offset=(-10, 10))
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setLabel("bottom", "generation")
        self.plot.setLabel("left", "founder share")
        self.plot.setYRange(0.0, 1.0)
        layout.addWidget(self.plot)
        self.refresh()

    def feed_rows(self, rows: list[dict[str, Any]]) -> int:
        """Feed founder-lineage rows; rebuild curves if any were added."""
        added = 0
        for row in rows:
            if self.vm.feed(row):
                added += 1
        if added:
            self.refresh()
        return added

    def refresh(self) -> None:
        """Rebuild one curve per founder from the current view-model series."""
        self.plot.clear()
        legend = self.plot.plotItem.legend
        if legend is not None:
            legend.clear()
        gen = [float(g) for g in self.vm.generations]
        series = self.vm.series()
        for i, founder in enumerate(self.vm.founders()):
            pen = pg.mkPen(_PALETTE[i % len(_PALETTE)], width=2)
            self.plot.plot(gen, series[founder], pen=pen, name=founder, connect="finite")


__all__ = ["PersonaDominancePanel"]
