"""Stage 3 panel P3: lineage DAG (PySide6 QGraphicsView, no extra deps).

A thin view over :class:`LineageVM`: nodes laid out by generation (x) and
feed-order within a generation (y), edges drawn parent->child, node colour mapped
by score, and the champion lineage highlighted. Uses Qt's built-in
``QGraphicsScene`` (BSP-indexed, fine for thousands of nodes) so no QWebEngine /
mermaid dependency is needed. Rebuilds the scene on refresh (lineage grows in
batches, and rebuild keeps the layout consistent).
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets

from llove.core.viewmodels.lineage import LineageVM

_DX = 90.0   # px per generation
_DY = 22.0   # px per individual within a generation
_R = 5.0     # node radius


def _score_color(score: float | None, lo: float, hi: float) -> QtGui.QColor:
    """Map a score in [lo, hi] to a blue->red colour (no pass/fail semantics)."""
    if score is None or hi <= lo:
        return QtGui.QColor("#bdc3c7")
    t = max(0.0, min(1.0, (score - lo) / (hi - lo)))
    return QtGui.QColor.fromRgbF(0.15 + 0.7 * t, 0.35, 0.9 - 0.7 * t)


class LineagePanel(QtWidgets.QWidget):
    """Generation lineage DAG with champion path highlighted."""

    def __init__(
        self,
        vm: LineageVM | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = vm if vm is not None else LineageVM()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.scene = QtWidgets.QGraphicsScene(self)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        layout.addWidget(self.view)
        self.refresh()

    def feed_rows(self, rows: list[dict[str, Any]]) -> int:
        """Feed winner rows; rebuild the scene if any were added."""
        added = 0
        for row in rows:
            if self.vm.feed(row):
                added += 1
        if added:
            self.refresh()
        return added

    def _positions(self) -> dict[str, QtCore.QPointF]:
        pos: dict[str, QtCore.QPointF] = {}
        for gen, nodes in self.vm.by_generation().items():
            for i, node in enumerate(nodes):
                pos[node.individual_id] = QtCore.QPointF(gen * _DX, i * _DY)
        return pos

    def refresh(self) -> None:
        """Rebuild the lineage scene from the current view-model."""
        self.scene.clear()
        if self.vm.count == 0:
            return
        pos = self._positions()
        scores = [n.score for n in self.vm.nodes.values() if n.score is not None]
        lo = min(scores) if scores else 0.0
        hi = max(scores) if scores else 1.0

        champion = self.vm.champion_path()
        champion_set = set(champion)
        champion_edges = {(champion[i], champion[i + 1]) for i in range(len(champion) - 1)}

        # Edges first (under the nodes).
        faint = QtGui.QPen(QtGui.QColor(0, 0, 0, 40))
        gold = QtGui.QPen(QtGui.QColor("#e67e22"))
        gold.setWidthF(2.0)
        for parent, child in self.vm.edges():
            if parent not in pos or child not in pos:
                continue
            p, c = pos[parent], pos[child]
            pen = gold if (parent, child) in champion_edges else faint
            self.scene.addLine(p.x(), p.y(), c.x(), c.y(), pen)

        # Nodes.
        for ind_id, node in self.vm.nodes.items():
            point = pos[ind_id]
            color = _score_color(node.score, lo, hi)
            pen = gold if ind_id in champion_set else QtGui.QPen(QtGui.QColor(0, 0, 0, 90))
            self.scene.addEllipse(
                point.x() - _R, point.y() - _R, 2 * _R, 2 * _R, pen, QtGui.QBrush(color)
            )

    @property
    def node_count(self) -> int:
        return self.vm.count


__all__ = ["LineagePanel"]
