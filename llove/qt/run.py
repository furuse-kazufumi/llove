"""Stage 1 launcher: a single-window app that live-plots a run's metrics.

    python -m llove.qt path/to/out/<run>/metrics.jsonl

A minimal ``QMainWindow`` hosting one :class:`FitnessTrajectoryPanel`, fed by a
:class:`MetricsTailController` polling the file. No QtAds shell yet — that is
Stage 2 (design §6). ``build_window`` is factored out so it can be exercised
headless (``QT_QPA_PLATFORM=offscreen``) without entering the event loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6 import QtWidgets

from llove.qt.fitness_panel import FitnessTrajectoryPanel
from llove.qt.worker import MetricsTailController


def build_window(
    metrics_path: str | Path,
    interval_ms: int = 500,
) -> tuple[QtWidgets.QMainWindow, FitnessTrajectoryPanel, MetricsTailController]:
    """Build the window + panel + tail controller, wired but not started."""
    window = QtWidgets.QMainWindow()
    window.setWindowTitle(f"llove — fitness trajectory · {Path(metrics_path).name}")
    panel = FitnessTrajectoryPanel()
    controller = MetricsTailController(metrics_path, interval_ms=interval_ms)
    controller.rows_ready.connect(panel.feed_rows)
    window.setCentralWidget(panel)
    # Keep the controller alive for the window's lifetime.
    controller.setParent(window)
    return window, panel, controller


def run_fitness_panel(metrics_path: str | Path, argv: list[str] | None = None) -> int:
    """Open the live fitness panel for ``metrics_path`` and run the event loop."""
    existing = QtWidgets.QApplication.instance()
    app = (
        existing
        if isinstance(existing, QtWidgets.QApplication)
        else QtWidgets.QApplication(list(argv) if argv is not None else sys.argv)
    )
    window, _panel, controller = build_window(metrics_path)
    controller.start()
    window.resize(900, 500)
    window.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``python -m llove.qt <metrics.jsonl>``."""
    args = list(sys.argv if argv is None else argv)
    if len(args) < 2:
        sys.stderr.write("usage: python -m llove.qt <metrics.jsonl>\n")
        return 2
    return run_fitness_panel(args[1], argv=args)


__all__ = ["build_window", "main", "run_fitness_panel"]
