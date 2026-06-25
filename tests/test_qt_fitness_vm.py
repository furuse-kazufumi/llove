"""Stage 1 Qt PoC — pure view-model tests (no Qt import).

The fitness-trajectory view-model parses the evolution engine's raw
``metrics.jsonl`` rows (``{generation, best_score, mean_score, ...}``) and keeps
aligned series for plotting. It is UI-framework independent so both the Textual
and the new Qt front can subscribe to it (design: llove_qt_gui_architecture_2026_05_25 §5).
"""

from __future__ import annotations

import math

from llove.core.viewmodels.fitness_trajectory import (
    FitnessTrajectoryVM,
    parse_metrics_row,
)


def test_parse_valid_row() -> None:
    row = parse_metrics_row(
        '{"generation":3,"best_score":0.7,"mean_score":0.5,'
        '"median_score":0.49,"std_score":0.1,"diversity_l2":28.5,"seed":0}'
    )
    assert row is not None
    assert row["generation"] == 3
    assert row["best_score"] == 0.7


def test_parse_rejects_bad_json() -> None:
    assert parse_metrics_row("not json") is None
    assert parse_metrics_row("") is None
    assert parse_metrics_row("   ") is None
    assert parse_metrics_row("[1,2,3]") is None  # not an object


def test_parse_requires_generation_and_a_score() -> None:
    assert parse_metrics_row('{"best_score":0.5,"mean_score":0.4}') is None  # no generation
    assert parse_metrics_row('{"generation":1}') is None  # no score field


def test_parse_coerces_generation_to_int() -> None:
    row = parse_metrics_row('{"generation":"4","best_score":0.7,"mean_score":0.5}')
    assert row is not None
    assert row["generation"] == 4


def test_vm_accumulates_rows_in_order() -> None:
    vm = FitnessTrajectoryVM()
    for i in range(3):
        assert vm.feed(
            {
                "generation": i,
                "best_score": 0.5 + i,
                "mean_score": 0.4 + i,
                "median_score": 0.39 + i,
                "std_score": 0.1,
            }
        )
    assert vm.count == 3
    assert vm.generations == [0, 1, 2]
    assert vm.best == [0.5, 1.5, 2.5]
    assert vm.mean == [0.4, 1.4, 2.4]


def test_vm_tolerant_to_missing_median_and_std() -> None:
    vm = FitnessTrajectoryVM()
    assert vm.feed({"generation": 0, "best_score": 0.5, "mean_score": 0.4})
    assert math.isnan(vm.median[0])
    assert math.isnan(vm.std[0])


def test_vm_rejects_row_without_any_score() -> None:
    vm = FitnessTrajectoryVM()
    assert vm.feed({"generation": 0}) is False
    assert vm.count == 0


def test_vm_feed_line_parses_then_feeds() -> None:
    vm = FitnessTrajectoryVM()
    assert vm.feed_line('{"generation":0,"best_score":0.5,"mean_score":0.4}')
    assert vm.feed_line("garbage") is False
    assert vm.count == 1


def test_vm_series_has_aligned_lengths() -> None:
    vm = FitnessTrajectoryVM()
    vm.feed({"generation": 0, "best_score": 0.5, "mean_score": 0.4})
    vm.feed({"generation": 1, "best_score": 0.6, "mean_score": 0.5})
    s = vm.series()
    assert set(s) >= {"generation", "best", "mean", "median", "std"}
    n = len(s["generation"])
    assert n == 2
    assert all(len(v) == n for v in s.values())
