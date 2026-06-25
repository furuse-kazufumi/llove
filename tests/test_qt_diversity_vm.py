"""Stage 3 — diversity-trajectory view-model tests (pure, no Qt).

``diversity_l2`` rides in the same ``metrics.jsonl`` rows the fitness VM reads, so
this panel reuses the existing metrics tail — no new reader. Acceptance signal
(design P2): diversity should stay non-zero into the tail generations.
"""

from __future__ import annotations

from llove.core.viewmodels.diversity_trajectory import DiversityTrajectoryVM


def test_feed_picks_diversity() -> None:
    vm = DiversityTrajectoryVM()
    assert vm.feed({"generation": 0, "best_score": 0.5, "mean_score": 0.4, "diversity_l2": 28.5})
    assert vm.feed({"generation": 1, "best_score": 0.6, "mean_score": 0.5, "diversity_l2": 27.9})
    assert vm.count == 2
    assert vm.generations == [0, 1]
    assert vm.diversity == [28.5, 27.9]


def test_feed_rejects_row_without_diversity() -> None:
    vm = DiversityTrajectoryVM()
    assert vm.feed({"generation": 0, "best_score": 0.5, "mean_score": 0.4}) is False
    assert vm.count == 0


def test_feed_line_parses_metrics_row() -> None:
    vm = DiversityTrajectoryVM()
    assert vm.feed_line(
        '{"generation":3,"best_score":0.7,"mean_score":0.5,"diversity_l2":12.3}'
    )
    assert vm.feed_line("not json") is False
    assert vm.count == 1
    assert vm.diversity == [12.3]


def test_series_aligned() -> None:
    vm = DiversityTrajectoryVM()
    vm.feed({"generation": 0, "best_score": 0.5, "mean_score": 0.4, "diversity_l2": 1.0})
    s = vm.series()
    assert set(s) >= {"generation", "diversity"}
    assert len(s["generation"]) == len(s["diversity"]) == 1
