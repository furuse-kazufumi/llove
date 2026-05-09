"""Standalone Qt viewer for llove `pointcloud` scenario JSONL streams.

Renders the LiDAR top-view as a 2D scatter (x vs y) using a `QGraphicsScene`
and lets you scrub through frames. Missing slots are highlighted.

Usage:
    pip install PySide6
    llove demo --scenario pointcloud | tee out/pointcloud.jsonl
    python tools/qt_viewer/pointcloud_viewer.py out/pointcloud.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover — runtime guard, not a llove dep
    print("This viewer requires PySide6: pip install PySide6", file=sys.stderr)
    raise


SCENE_W = 600
SCENE_H = 420
MARGIN = 30


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def _index_by_frame(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    by_frame: dict[int, dict[str, Any]] = defaultdict(dict)
    for ev in events:
        kind = ev.get("kind", "")
        payload = ev.get("payload", {})
        fid = payload.get("frame_id")
        if fid is None:
            continue
        if kind == "sensor":
            by_frame[fid]["sensor"] = payload
        elif kind == "spc_alarm":
            by_frame[fid]["alarm"] = payload
    return dict(by_frame)


class PointCloudViewer(QtWidgets.QMainWindow):
    def __init__(self, frames: dict[int, dict[str, Any]]) -> None:
        super().__init__()
        self.setWindowTitle("llove pointcloud viewer")
        self.resize(SCENE_W + 60, SCENE_H + 180)
        self._frames = frames
        self._frame_ids = sorted(frames)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self._scene = QtWidgets.QGraphicsScene(0, 0, SCENE_W, SCENE_H)
        self._scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#0d1117")))
        self._view = QtWidgets.QGraphicsView(self._scene)
        self._view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        layout.addWidget(self._view, stretch=1)

        self._summary = QtWidgets.QLabel()
        self._summary.setStyleSheet("font-family: monospace; font-size: 12px; padding: 6px;")
        layout.addWidget(self._summary)

        self._slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(max(0, len(self._frame_ids) - 1))
        self._slider.valueChanged.connect(self._render)
        layout.addWidget(self._slider)

        self.setCentralWidget(central)
        if self._frame_ids:
            self._render(0)

    def _render(self, index: int) -> None:
        if not self._frame_ids:
            return
        fid = self._frame_ids[index]
        bundle = self._frames[fid]
        sensor = bundle.get("sensor", {})
        alarm = bundle.get("alarm")

        self._scene.clear()

        # Tray bounds.
        pen_tray = QtGui.QPen(QtGui.QColor("#444"), 1)
        self._scene.addRect(MARGIN, MARGIN, SCENE_W - 2 * MARGIN, SCENE_H - 2 * MARGIN, pen_tray)

        # Axes.
        font = QtGui.QFont("monospace", 9)
        for label, x, y in (("x →", SCENE_W - MARGIN + 4, SCENE_H - MARGIN + 4), ("y ↑", MARGIN - 22, MARGIN - 16)):
            t = self._scene.addText(label, font)
            t.setDefaultTextColor(QtGui.QColor("#aaa"))
            t.setPos(x, y)

        points = sensor.get("points_xyz") or []
        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)
            # Avoid div-by-zero.
            x_range = max(1e-6, x1 - x0)
            y_range = max(1e-6, y1 - y0)

            inner_w = SCENE_W - 2 * MARGIN
            inner_h = SCENE_H - 2 * MARGIN

            pen_pt = QtGui.QPen(QtCore.Qt.PenStyle.NoPen)
            brush_pt = QtGui.QBrush(QtGui.QColor("#42c8a0"))
            for px, py, _pz in points:
                u = MARGIN + (px - x0) / x_range * inner_w
                # Flip y so positive y goes up on screen.
                v = SCENE_H - MARGIN - (py - y0) / y_range * inner_h
                self._scene.addEllipse(u - 2, v - 2, 4, 4, pen_pt, brush_pt)

        missing = sensor.get("missing_slot")
        if missing:
            # Highlight the missing slot region in the same x/y space.
            col, row = missing
            # Slot centre in synth coords: cx=col*0.10+0.05, cy=row*0.10+0.05.
            cx = float(col) * 0.10 + 0.05
            cy = float(row) * 0.10 + 0.05
            # Re-use the same affine projection as above.
            if points:
                xs = [p[0] for p in points] + [cx, cx]
                ys = [p[1] for p in points] + [cy, cy]
                x0, x1 = min(xs), max(xs)
                y0, y1 = min(ys), max(ys)
                x_range = max(1e-6, x1 - x0)
                y_range = max(1e-6, y1 - y0)
                inner_w = SCENE_W - 2 * MARGIN
                inner_h = SCENE_H - 2 * MARGIN
                u = MARGIN + (cx - x0) / x_range * inner_w
                v = SCENE_H - MARGIN - (cy - y0) / y_range * inner_h
                pen_miss = QtGui.QPen(QtGui.QColor("#ff3060"), 2, QtCore.Qt.PenStyle.DashLine)
                self._scene.addEllipse(u - 22, v - 22, 44, 44, pen_miss)

        density = sensor.get("value", 0)
        topview = sensor.get("topview_ascii", "")
        msg = (
            f"Frame #{fid}    density={density} returns    "
            f"missing_slot={missing or 'none'}    "
            f"alarm={'YES' if alarm else 'no'}"
        )
        self._summary.setText(msg)
        # First-line preview of the topview ascii in tooltip.
        self._summary.setToolTip(topview)


def main() -> int:
    parser = argparse.ArgumentParser(description="Qt viewer for llove pointcloud JSONL")
    parser.add_argument("path", type=Path, help="JSONL file produced by `llove demo --scenario pointcloud`")
    args = parser.parse_args()

    events = _load_events(args.path)
    frames = _index_by_frame(events)
    if not frames:
        print(f"No pointcloud frames found in {args.path}", file=sys.stderr)
        return 2

    app = QtWidgets.QApplication(sys.argv)
    win = PointCloudViewer(frames)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
