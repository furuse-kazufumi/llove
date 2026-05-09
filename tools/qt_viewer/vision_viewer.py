"""Standalone Qt viewer for llove `vision` scenario JSONL streams.

Renders each frame as an upscaled image (from `image_b64` if present, otherwise
synthesised from `image_ascii`), draws bounding boxes from any SPC_ALARM event
that shares the same `frame_id`, and shows the VLM caption + score.

Usage:
    pip install PySide6
    llove demo --scenario vision | tee out/vision.jsonl
    python tools/qt_viewer/vision_viewer.py out/vision.jsonl

Not a llove dependency — lives in `tools/` so the core stays graphics-free.
"""

from __future__ import annotations

import argparse
import base64
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


CELL_PX = 20  # how many on-screen pixels each ASCII cell scales to


def _ascii_to_pixmap(art: str, cell_px: int = CELL_PX) -> QtGui.QPixmap:
    """Render an ASCII frame as a pixmap. '.' = light, '#' = dark, '|/-' borders."""
    rows = art.splitlines()
    if not rows:
        return QtGui.QPixmap()
    h = len(rows)
    w = max(len(r) for r in rows)
    img = QtGui.QImage(w * cell_px, h * cell_px, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor("#fafaf2"))
    painter = QtGui.QPainter(img)
    try:
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                rect = QtCore.QRectF(x * cell_px, y * cell_px, cell_px, cell_px)
                if ch == "#":
                    painter.fillRect(rect, QtGui.QColor("#222"))
                elif ch in {"|", "-"}:
                    painter.fillRect(rect, QtGui.QColor("#888"))
                elif ch in {"[", "]"}:
                    painter.fillRect(rect, QtGui.QColor("#7a4"))
                elif ch == "o":
                    painter.fillRect(rect.adjusted(3, 3, -3, -3), QtGui.QColor("#ddd"))
                elif ch == ">":
                    painter.fillRect(rect, QtGui.QColor("#444"))
                elif ch.strip() == "":
                    pass
        painter.end()
    except BaseException:
        painter.end()
        raise
    return QtGui.QPixmap.fromImage(img)


def _b64_to_pixmap(b64: str) -> QtGui.QPixmap:
    raw = base64.b64decode(b64)
    img = QtGui.QImage.fromData(raw)
    return QtGui.QPixmap.fromImage(img)


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # llove demo prints non-JSON status lines too; skip them.
            continue
    return events


def _index_by_frame(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Group events by `frame_id`. Each group keeps the SENSOR + any SPC_ALARM."""
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


class VisionViewer(QtWidgets.QMainWindow):
    def __init__(self, frames: dict[int, dict[str, Any]]) -> None:
        super().__init__()
        self.setWindowTitle("llove vision viewer")
        self.resize(720, 600)
        self._frames = frames
        self._frame_ids = sorted(frames)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self._image_label = QtWidgets.QLabel(alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(440, 200)
        self._image_label.setStyleSheet("background:#222;")
        layout.addWidget(self._image_label, stretch=1)

        self._caption = QtWidgets.QLabel(wordWrap=True)
        self._caption.setStyleSheet("font-size: 13px; padding: 6px;")
        layout.addWidget(self._caption)

        self._score_label = QtWidgets.QLabel()
        self._score_label.setStyleSheet("font-family: monospace; padding: 4px;")
        layout.addWidget(self._score_label)

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

        b64 = sensor.get("image_b64")
        pix = _b64_to_pixmap(b64) if b64 else _ascii_to_pixmap(sensor.get("image_ascii") or "")

        if alarm:
            bbox = alarm.get("bbox") or []
            if len(bbox) == 4:
                pix = self._draw_bbox(pix, bbox, CELL_PX)

        self._image_label.setPixmap(
            pix.scaled(
                self._image_label.width(),
                self._image_label.height(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )

        score = sensor.get("value")
        caption = sensor.get("vlm_caption", "")
        self._caption.setText(f"<b>Frame #{fid}</b> — {caption}")
        verdict = "DEFECT" if alarm else "ok"
        self._score_label.setText(f"defect_score = {score:.2f}    verdict = {verdict}")

    @staticmethod
    def _draw_bbox(
        pix: QtGui.QPixmap, bbox: list[int], cell_px: int
    ) -> QtGui.QPixmap:
        # bbox came from an ASCII grid; if image came from b64, just draw at
        # the same coords scaled down.
        canvas = pix.copy()
        painter = QtGui.QPainter(canvas)
        try:
            pen = QtGui.QPen(QtGui.QColor("#ff3060"), 3)
            painter.setPen(pen)
            x1, y1, x2, y2 = bbox
            painter.drawRect(
                x1 * cell_px,
                y1 * cell_px,
                (x2 - x1 + 1) * cell_px,
                (y2 - y1 + 1) * cell_px,
            )
        finally:
            painter.end()
        return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description="Qt viewer for llove vision JSONL")
    parser.add_argument("path", type=Path, help="JSONL file produced by `llove demo --scenario vision`")
    args = parser.parse_args()

    events = _load_events(args.path)
    frames = _index_by_frame(events)
    if not frames:
        print(f"No vision frames found in {args.path}", file=sys.stderr)
        return 2

    app = QtWidgets.QApplication(sys.argv)
    win = VisionViewer(frames)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
