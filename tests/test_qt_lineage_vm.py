"""Stage 3 — lineage view-model tests (pure, no Qt).

Builds a generation DAG from ``winners.jsonl`` rows
(``{generation, individual_id, parent_ids, score, rank}``): nodes per individual,
edges parent->child (crossover => multiple parents => DAG), and a champion
lineage traced back from the best-scoring individual (design P3).
"""

from __future__ import annotations

from llove.core.viewmodels.lineage import LineageVM


def _rows() -> list[dict]:
    return [
        {"generation": 0, "individual_id": "A", "parent_ids": [], "score": 0.5, "rank": 0},
        {"generation": 0, "individual_id": "B", "parent_ids": [], "score": 0.7, "rank": 1},
        {"generation": 1, "individual_id": "C", "parent_ids": ["A"], "score": 0.6, "rank": 1},
        {"generation": 1, "individual_id": "D", "parent_ids": ["B", "A"], "score": 0.9, "rank": 0},
    ]


def test_feed_builds_nodes_and_generations() -> None:
    vm = LineageVM()
    for r in _rows():
        assert vm.feed(r)
    assert vm.count == 4
    by_gen = vm.by_generation()
    assert sorted(by_gen) == [0, 1]
    assert [n.individual_id for n in by_gen[0]] == ["A", "B"]
    assert [n.individual_id for n in by_gen[1]] == ["C", "D"]


def test_edges_only_for_present_parents() -> None:
    vm = LineageVM()
    vm.feed({"generation": 1, "individual_id": "C", "parent_ids": ["ghost"], "score": 0.6})
    assert vm.edges() == []  # parent not present
    vm.feed({"generation": 0, "individual_id": "ghost", "parent_ids": [], "score": 0.4})
    assert ("ghost", "C") in vm.edges()


def test_dag_multiple_parents() -> None:
    vm = LineageVM()
    for r in _rows():
        vm.feed(r)
    edges = set(vm.edges())
    assert ("A", "C") in edges
    assert ("B", "D") in edges
    assert ("A", "D") in edges  # crossover: D has two parents


def test_champion_path_traces_best() -> None:
    vm = LineageVM()
    for r in _rows():
        vm.feed(r)
    # champion = D (0.9); best known parent of D is B (0.7) > A (0.5); B has no parent
    assert vm.champion_path() == ["B", "D"]


def test_rejects_rows_without_id_or_generation() -> None:
    vm = LineageVM()
    assert vm.feed({"generation": 0}) is False
    assert vm.feed({"individual_id": "X"}) is False
    assert vm.count == 0
