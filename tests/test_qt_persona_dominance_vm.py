"""Stage 3 — persona-dominance view-model tests (pure, no Qt).

Reads ``founder_lineage.jsonl`` rows
(``{generation, n_individuals, founder_counts: {name: count}}``) into per-founder
*share* series aligned across generations (design P4). Founders that appear later
are back-filled with zeros; founders absent in a generation are zero there. The
monoculture guard watches ``max_share`` per generation (< 0.8 acceptance).
"""

from __future__ import annotations

from llove.core.viewmodels.persona_dominance import PersonaDominanceVM


def test_feed_computes_shares() -> None:
    vm = PersonaDominanceVM()
    assert vm.feed({"generation": 0, "n_individuals": 4, "founder_counts": {"a": 1, "b": 3}})
    s = vm.series()
    assert s["a"] == [0.25]
    assert s["b"] == [0.75]
    assert vm.generations == [0]


def test_new_founder_backfilled_with_zero() -> None:
    vm = PersonaDominanceVM()
    vm.feed({"generation": 0, "n_individuals": 4, "founder_counts": {"a": 4}})
    vm.feed({"generation": 1, "n_individuals": 4, "founder_counts": {"a": 2, "c": 2}})
    s = vm.series()
    assert s["a"] == [1.0, 0.5]
    assert s["c"] == [0.0, 0.5]  # c appeared at gen 1, back-filled 0 at gen 0


def test_absent_founder_is_zero_that_generation() -> None:
    vm = PersonaDominanceVM()
    vm.feed({"generation": 0, "n_individuals": 2, "founder_counts": {"a": 1, "b": 1}})
    vm.feed({"generation": 1, "n_individuals": 2, "founder_counts": {"a": 2}})
    s = vm.series()
    assert s["a"] == [0.5, 1.0]
    assert s["b"] == [0.5, 0.0]


def test_n_individuals_defaults_to_sum_of_counts() -> None:
    vm = PersonaDominanceVM()
    assert vm.feed({"generation": 0, "founder_counts": {"a": 1, "b": 1}})
    assert vm.series()["a"] == [0.5]


def test_rejects_rows_without_founder_counts_or_generation() -> None:
    vm = PersonaDominanceVM()
    assert vm.feed({"generation": 0}) is False
    assert vm.feed({"founder_counts": {"a": 1}}) is False
    assert vm.count == 0


def test_max_share_per_generation_for_monoculture_guard() -> None:
    vm = PersonaDominanceVM()
    vm.feed({"generation": 0, "n_individuals": 4, "founder_counts": {"a": 1, "b": 3}})
    vm.feed({"generation": 1, "n_individuals": 4, "founder_counts": {"a": 4}})
    assert vm.max_share_per_generation() == [0.75, 1.0]


def test_founders_sorted_and_stable() -> None:
    vm = PersonaDominanceVM()
    vm.feed({"generation": 0, "n_individuals": 2, "founder_counts": {"b": 1, "a": 1}})
    assert vm.founders() == ["a", "b"]
