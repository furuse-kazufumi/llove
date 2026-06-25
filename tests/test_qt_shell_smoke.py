"""Stage 2 — offscreen smoke for the registry, run-monitor panel, and shell.

Skipped when the ``gui`` extra is absent. Runs headless via the Qt ``offscreen``
platform. Covers: Qt builders register into the shared WindowType Registry; the
shell docks panels from it; a perspective round-trips; and the run-monitor's
buttons write a control request.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6 import QtWidgets

from llove.qt.registry import register_qt_window_types
from llove.qt.run_monitor_panel import RunMonitorPanel
from llove.qt.shell import LoveShell
from llove.window.types import get_window_type


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return app  # type: ignore[return-value]


def test_qt_builders_register(qapp: QtWidgets.QApplication) -> None:
    register_qt_window_types()
    for type_id in (
        "viz.fitness_trajectory",
        "viz.diversity_trajectory",
        "viz.persona_dominance",
        "viz.genome3d_heatmap",
        "viz.run_monitor",
    ):
        wt = get_window_type(type_id)
        assert wt is not None
        assert wt.builder is not None
        widget = wt.builder({})
        assert isinstance(widget, QtWidgets.QWidget)


def test_diversity_panel_plots_rows(qapp: QtWidgets.QApplication) -> None:
    from llove.qt.diversity_panel import DiversityTrajectoryPanel

    panel = DiversityTrajectoryPanel()
    added = panel.feed_rows(
        [
            {"generation": 0, "best_score": 0.5, "mean_score": 0.4, "diversity_l2": 28.5},
            {"generation": 1, "best_score": 0.6, "mean_score": 0.5, "diversity_l2": 27.9},
            {"generation": 2, "best_score": 0.7, "mean_score": 0.6},  # no diversity -> skipped
        ]
    )
    assert added == 2
    x, y = panel.diversity_curve.getData()
    assert len(x) == 2
    assert len(y) == 2


def test_persona_panel_plots_rows(qapp: QtWidgets.QApplication) -> None:
    from llove.qt.persona_dominance_panel import PersonaDominancePanel

    panel = PersonaDominancePanel()
    added = panel.feed_rows(
        [
            {"generation": 0, "n_individuals": 4, "founder_counts": {"a": 1, "b": 3}},
            {"generation": 1, "n_individuals": 4, "founder_counts": {"a": 2, "c": 2}},
            {"generation": 2},  # no founder_counts -> skipped
        ]
    )
    assert added == 2
    assert panel.vm.founders() == ["a", "b", "c"]
    assert panel.vm.max_share_per_generation() == [0.75, 0.5]


def test_shell_opens_panels(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    shell = LoveShell(tmp_path)
    shell.open_window("viz.run_monitor")
    shell.open_window("viz.fitness_trajectory")
    assert shell.dock_count == 2
    assert shell.open_type_ids() == ["viz.run_monitor", "viz.fitness_trajectory"]
    # unknown type id is fail-closed (no dock created)
    assert shell.open_window("viz.does_not_exist") is None
    assert shell.dock_count == 2


def test_shell_perspective_roundtrip(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    persp = tmp_path / "perspective.json"
    shell = LoveShell(tmp_path)
    shell.open_window("viz.run_monitor")
    shell.open_window("viz.fitness_trajectory")
    shell.save_perspective(persp)

    restored = LoveShell(tmp_path)
    assert restored.dock_count == 0
    restored.restore_perspective(persp)
    assert restored.dock_count == 2
    assert restored.open_type_ids() == ["viz.run_monitor", "viz.fitness_trajectory"]


def test_run_monitor_buttons_write_control(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    panel = RunMonitorPanel(tmp_path)
    panel.request_pause()
    data = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert data["command"] == "pause"
    panel.request_resume()
    data = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert data["command"] == "resume"
    assert data["seq"] == 2


def test_run_monitor_reflects_status(qapp: QtWidgets.QApplication, tmp_path: Path) -> None:
    (tmp_path / "run_manifest.json").write_text(
        json.dumps({"fitness": "proxy", "population": 32, "generations": 500}),
        encoding="utf-8",
    )
    (tmp_path / "metrics.jsonl").write_text(
        '{"generation":12,"best_score":0.83,"mean_score":0.6}\n', encoding="utf-8"
    )
    panel = RunMonitorPanel(tmp_path)
    assert panel.status.status == "running"
    assert panel.status.current_generation == 12
    assert panel.status.best_score == 0.83
