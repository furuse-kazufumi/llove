"""Register the Stage 1/2 Qt panels as ``WindowType`` builders.

The existing ``llove/window/types.py`` Registry already anticipates Qt
(``builder(config) -> View`` may return a Qt widget; ``default_size`` is px for
Qt). Here each panel becomes a "desktop app" the shell can launch from its View
menu (design §2.3 / §3). Registration is done lazily from
:func:`register_qt_window_types` — never at import time of the core registry —
so importing ``llove`` core never pulls in PySide6.
"""

from __future__ import annotations

from typing import Any

from PySide6 import QtWidgets

from llove.qt.diversity_panel import DiversityTrajectoryPanel
from llove.qt.fitness_panel import FitnessTrajectoryPanel
from llove.qt.run_monitor_panel import RunMonitorPanel
from llove.qt.worker import MetricsTailController
from llove.window.types import WindowType, register_window_type


def _wire_metrics_tail(panel: QtWidgets.QWidget, config: dict[str, Any]) -> None:
    """Attach a live metrics tail to a panel that exposes ``feed_rows``."""
    metrics_path = config.get("metrics_path")
    if not metrics_path:
        return
    controller = MetricsTailController(metrics_path, parent=panel)
    controller.rows_ready.connect(panel.feed_rows)
    controller.start()  # one immediate read now, then poll on the timer
    panel.controller = controller  # type: ignore[attr-defined]


def _build_fitness(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a fitness panel; if ``metrics_path`` is given, tail it live."""
    panel = FitnessTrajectoryPanel()
    _wire_metrics_tail(panel, config)
    return panel


def _build_diversity(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a diversity panel; if ``metrics_path`` is given, tail it live."""
    panel = DiversityTrajectoryPanel()
    _wire_metrics_tail(panel, config)
    return panel


def _build_run_monitor(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a run-monitor panel for ``run_dir`` (defaults to cwd)."""
    return RunMonitorPanel(config.get("run_dir", "."))


def register_qt_window_types() -> None:
    """Register the Qt panels into the shared WindowType Registry (idempotent)."""
    register_window_type(
        WindowType(
            id="viz.fitness_trajectory",
            display_name="Fitness Trajectory",
            category="visualization",
            description="Live best/mean/median score per generation (P1).",
            default_size=(900, 500),  # px (Qt)
            builder=_build_fitness,
        )
    )
    register_window_type(
        WindowType(
            id="viz.diversity_trajectory",
            display_name="Diversity Trajectory",
            category="visualization",
            description="Live population diversity_l2 per generation (P2).",
            default_size=(900, 400),  # px (Qt)
            builder=_build_diversity,
        )
    )
    register_window_type(
        WindowType(
            id="viz.run_monitor",
            display_name="Run Monitor",
            category="visualization",
            description="Run status + pause/resume/stop controls (P7).",
            default_size=(360, 280),  # px (Qt)
            builder=_build_run_monitor,
        )
    )


__all__ = ["register_qt_window_types"]
