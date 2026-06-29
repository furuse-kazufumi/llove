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
