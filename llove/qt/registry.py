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

from llove.core.viewmodels.genome_heatmap import find_latest_snapshot, load_snapshot_file
from llove.qt.diversity_panel import DiversityTrajectoryPanel
from llove.qt.fitness_panel import FitnessTrajectoryPanel
from llove.qt.genome_heatmap_panel import GenomeHeatmapPanel
from llove.qt.lineage_panel import LineagePanel
from llove.qt.persona_dominance_panel import PersonaDominancePanel
from llove.qt.qd_archive_panel import QdArchivePanel
from llove.qt.run_monitor_panel import RunMonitorPanel
from llove.qt.worker import JsonlTailController, MetricsTailController
from llove.window.types import WindowType, register_window_type


def _wire_metrics_tail(panel: Any, config: dict[str, Any]) -> None:
    """Attach a live metrics tail to a panel that exposes ``feed_rows``.

    ``panel`` is a fitness/diversity panel (QWidget with ``feed_rows``); typed
    ``Any`` because this is a small structural wiring helper.
    """
    metrics_path = config.get("metrics_path")
    if not metrics_path:
        return
    controller = MetricsTailController(metrics_path, parent=panel)
    controller.rows_ready.connect(panel.feed_rows)
    controller.start()  # one immediate read now, then poll on the timer
    panel.controller = controller


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


def _build_persona(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a persona-dominance panel; tail ``founder_lineage_path`` if given."""
    panel = PersonaDominancePanel()
    path = config.get("founder_lineage_path")
    if path:
        controller = JsonlTailController(path, parent=panel)
        controller.rows_ready.connect(panel.feed_rows)
        controller.start()
        panel.controller = controller  # type: ignore[attr-defined]
    return panel


def _build_lineage(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a lineage panel; tail ``winners_path`` if given."""
    panel = LineagePanel()
    path = config.get("winners_path")
    if path:
        controller = JsonlTailController(path, parent=panel)
        controller.rows_ready.connect(panel.feed_rows)
        controller.start()
        panel.controller = controller  # type: ignore[attr-defined]
    return panel


def _build_genome_heatmap(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a genome heatmap; load ``snapshot_path`` or the latest in ``run_dir``."""
    panel = GenomeHeatmapPanel()
    path = config.get("snapshot_path")
    if not path:
        run_dir = config.get("run_dir")
        if run_dir:
            latest = find_latest_snapshot(run_dir)
            path = str(latest) if latest is not None else None
    if path:
        snap = load_snapshot_file(path)
        if snap is not None:
            panel.load_snapshot(snap)
    return panel


def _build_run_monitor(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a run-monitor panel for ``run_dir`` (defaults to cwd)."""
    return RunMonitorPanel(config.get("run_dir", "."))


def _build_qd_archive(config: dict[str, Any]) -> QtWidgets.QWidget:
    """Build a QD-archive panel; tail ``qd_metrics_path`` (``metrics_*_qd.jsonl``) if given."""
    panel = QdArchivePanel()
    path = config.get("qd_metrics_path")
    if path:
        controller = MetricsTailController(path, parent=panel)
        controller.rows_ready.connect(panel.feed_rows)
        controller.start()
        panel.controller = controller  # type: ignore[attr-defined]
    return panel


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
            id="viz.persona_dominance",
            display_name="Persona Dominance",
            category="visualization",
            description="Founder/persona population share per generation (P4).",
            default_size=(900, 400),  # px (Qt)
            builder=_build_persona,
        )
    )
    register_window_type(
        WindowType(
            id="viz.lineage_tree",
            display_name="Lineage Tree",
            category="visualization",
            description="Generation DAG with champion lineage highlighted (P3).",
            default_size=(1000, 600),  # px (Qt)
            builder=_build_lineage,
        )
    )
    register_window_type(
        WindowType(
            id="viz.genome3d_heatmap",
            display_name="Genome Heatmap",
            category="visualization",
            description="Per-individual c_factors weights heatmap from a snapshot (P5).",
            default_size=(900, 500),  # px (Qt)
            builder=_build_genome_heatmap,
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
