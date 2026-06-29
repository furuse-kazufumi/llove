"""Stage 1 Qt PoC — offscreen smoke test for the PySide6 + pyqtgraph panel.

Skipped automatically when the ``gui`` extra is not installed
(``pip install 'llmesh-llove[gui]'``). Runs headless via the Qt ``offscreen``
platform so it works in CI / on machines without a display.
"""

from __future__ import annotations

import os

import pytest

# Headless before any QApplication is created.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6 import QtWidgets

from llove.qt.fitness_panel import FitnessTrajectoryPanel
from llove.qt.qd_archive_panel import QdArchivePanel
from llove.qt.worker import MetricsTailController


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return app  # type: ignore[return-value]


def _rows(n: int) -> list[dict]:
    return [
        {
            "generation": i,
            "best_score": 0.5 + i * 0.05,
            "mean_score": 0.4 + i * 0.04,
            "median_score": 0.39 + i * 0.04,
            "std_score": 0.1,
        }
        for i in range(n)
    ]


def test_panel_constructs_and_plots_fed_rows(qapp: QtWidgets.QApplication) -> None:
    panel = FitnessTrajectoryPanel()
    added = panel.feed_rows(_rows(5))
    assert added == 5
    assert panel.vm.count == 5
    x, y = panel.best_curve.getData()
    assert len(x) == 5
    assert len(y) == 5


def test_panel_ignores_malformed_rows(qapp: QtWidgets.QApplication) -> None:
    panel = FitnessTrajectoryPanel()
    added = panel.feed_rows([{"generation": 0}, {"oops": 1}])
    assert added == 0
    assert panel.vm.count == 0


def test_controller_emits_rows_from_file(
    qapp: QtWidgets.QApplication, tmp_path: object
) -> None:
    from pathlib import Path

    p = Path(str(tmp_path)) / "metrics.jsonl"
    p.write_text(
        '{"generation":0,"best_score":0.5,"mean_score":0.4}\n'
        '{"generation":1,"best_score":0.6,"mean_score":0.5}\n',
        encoding="utf-8",
    )
    controller = MetricsTailController(p, interval_ms=10)
    received: list[dict] = []
    controller.rows_ready.connect(received.extend)
    controller.poll_now()  # synchronous one-shot read (no event loop needed)
    assert [r["generation"] for r in received] == [0, 1]


def test_qd_archive_panel_plots(qapp: QtWidgets.QApplication) -> None:
    panel = QdArchivePanel()
    added = panel.feed_rows(
        [
            {"generation": 0, "archive_cells": 29, "occupied_cells": 29},
            {"generation": 1, "archive_cells": 30, "occupied_cells": 26},
            {"generation": 2, "archive_cells": 31},  # occupied missing -> NaN, still accepted
        ]
    )
    assert added == 3
    assert panel.vm.count == 3
    x, y = panel.archive_curve.getData()
    assert len(x) == 3
    assert len(y) == 3


def test_qd_reachable_via_shell_and_single_panel(
    qapp: QtWidgets.QApplication, tmp_path: object
) -> None:
    from pathlib import Path

    from llove.qt.run import build_qd_window
    from llove.qt.shell import LoveShell
    from llove.window.types import list_window_types

    run_dir = Path(str(tmp_path))
    qd = run_dir / "metrics_demo_qd.jsonl"
    qd.write_text(
        '{"generation":0,"archive_cells":29,"occupied_cells":29}\n'
        '{"generation":1,"archive_cells":30,"occupied_cells":26}\n',
        encoding="utf-8",
    )
    # (1) shell View-menu path: registered + resolves the QD file from run_dir + feeds it.
    shell = LoveShell(run_dir)
    assert "viz.qd_archive" in [w.id for w in list_window_types("visualization")]
    dock = shell.open_window("viz.qd_archive")
    assert dock is not None
    panel = dock.widget()
    panel.controller.poll_now()  # synchronous read; no event loop
    assert panel.vm.count == 2
    # (2) single-panel path (`python -m llove.qt <…_qd.jsonl>`): same tail wiring.
    _win, panel2, controller2 = build_qd_window(qd)
    controller2.poll_now()
    assert panel2.vm.count == 2

