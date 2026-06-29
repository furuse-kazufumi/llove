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
from llove.qt.qd_archive_panel import QdArchivePanel
from llove.qt.worker import JsonlTailController, MetricsTailController


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


def _app(argv: list[str] | None) -> QtWidgets.QApplication:
    existing = QtWidgets.QApplication.instance()
    if isinstance(existing, QtWidgets.QApplication):
        return existing
    return QtWidgets.QApplication(list(argv) if argv is not None else sys.argv)


def run_fitness_panel(metrics_path: str | Path, argv: list[str] | None = None) -> int:
    """Open the live fitness panel for ``metrics_path`` and run the event loop."""
    app = _app(argv)
    window, _panel, controller = build_window(metrics_path)
    controller.start()
    window.resize(900, 500)
    window.show()
    return app.exec()


def build_qd_window(
    qd_metrics_path: str | Path,
    interval_ms: int = 500,
) -> tuple[QtWidgets.QMainWindow, QdArchivePanel, JsonlTailController]:
    """Build the QD-archive window + panel + tail controller, wired but not started.

    Tails the QD metrics as plain JSONL (``JsonlTailController``); the QD rows use
    different score keys than ``metrics.jsonl`` so the fitness reader would drop them.
    """
    window = QtWidgets.QMainWindow()
    window.setWindowTitle(f"llove — QD archive · {Path(qd_metrics_path).name}")
    panel = QdArchivePanel()
    controller = JsonlTailController(qd_metrics_path, interval_ms=interval_ms)
    controller.rows_ready.connect(panel.feed_rows)
    window.setCentralWidget(panel)
    controller.setParent(window)
    return window, panel, controller


def run_qd_panel(qd_metrics_path: str | Path, argv: list[str] | None = None) -> int:
    """Open the live QD-archive panel for a ``metrics_*_qd.jsonl`` file."""
    app = _app(argv)
    window, _panel, controller = build_qd_window(qd_metrics_path)
    controller.start()
    window.resize(900, 450)
    window.show()
    return app.exec()


def run_shell(run_dir: str | Path, argv: list[str] | None = None) -> int:
    """Open the Stage 2 dockable shell for a run directory and run the loop."""
    from llove.qt.shell import LoveShell

    app = _app(argv)
    shell = LoveShell(run_dir)
    shell.open_window("viz.run_monitor")
    shell.open_window("viz.fitness_trajectory")
    shell.resize(1100, 650)
    shell.show()
    return app.exec()


def main(argv: list[str] | None = None) -> int:
    """CLI entry: a metrics file opens the single panel, a run dir opens the shell.

        python -m llove.qt path/to/<run>/metrics.jsonl   # Stage 1 single panel
        python -m llove.qt path/to/<run>/                 # Stage 2 dockable shell
    """
    args = list(sys.argv if argv is None else argv)
    if len(args) < 2:
        sys.stderr.write("usage: python -m llove.qt <metrics.jsonl | run_dir>\n")
        return 2
    target = Path(args[1])
    if target.is_dir():
        return run_shell(target, argv=args)
    if target.name.endswith("_qd.jsonl"):
        return run_qd_panel(target, argv=args)
    return run_fitness_panel(target, argv=args)


__all__ = [
    "build_qd_window",
    "build_window",
    "main",
    "run_fitness_panel",
    "run_qd_panel",
    "run_shell",
]
