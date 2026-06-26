"""Lineage view-model — generation DAG from ``winners.jsonl``.

Each row (``{generation, individual_id, parent_ids, score, rank}``) becomes a
node; ``parent_ids`` reference earlier individuals' ids (crossover gives multiple
parents, so the graph is a DAG, not a tree). ``edges`` are emitted only for
parents that are present (tolerant of windowed/partial reads), and
``champion_path`` traces back from the best-scoring individual via its
best-scoring known parent (design P3). Pure — no Qt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LineageNode:
    """One individual in the lineage DAG."""

    individual_id: str
    generation: int
    score: float | None
    rank: int | None
    parent_ids: tuple[str, ...]


def _opt_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _opt_int(value: Any) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


@dataclass
class LineageVM:
    """Accumulates lineage nodes/edges from winner rows."""

    nodes: dict[str, LineageNode] = field(default_factory=dict)
    _gen_order: dict[int, list[str]] = field(default_factory=dict)

    def feed(self, row: dict[str, Any]) -> bool:
        """Add one winner row; ``False`` if it lacks a generation or id."""
        if not isinstance(row, dict) or "generation" not in row or "individual_id" not in row:
            return False
        try:
            gen = int(row["generation"])
        except (TypeError, ValueError):
            return False
        ind_id = str(row["individual_id"])
        parents_raw = row.get("parent_ids") or []
        parent_ids = tuple(str(p) for p in parents_raw) if isinstance(parents_raw, list) else ()
        node = LineageNode(
            individual_id=ind_id,
            generation=gen,
            score=_opt_float(row.get("score")),
            rank=_opt_int(row.get("rank")),
            parent_ids=parent_ids,
        )
        if ind_id not in self.nodes:
            self._gen_order.setdefault(gen, []).append(ind_id)
        self.nodes[ind_id] = node
        return True

    @property
    def count(self) -> int:
        return len(self.nodes)

    def by_generation(self) -> dict[int, list[LineageNode]]:
        """``{generation: [nodes in feed order]}`` (ascending generations)."""
        return {
            gen: [self.nodes[i] for i in self._gen_order[gen]]
            for gen in sorted(self._gen_order)
        }

    def edges(self) -> list[tuple[str, str]]:
        """``(parent_id, child_id)`` pairs for parents present in the graph."""
        out: list[tuple[str, str]] = []
        for node in self.nodes.values():
            for parent in node.parent_ids:
                if parent in self.nodes:
                    out.append((parent, node.individual_id))
        return out

    def champion_path(self) -> list[str]:
        """Best-scoring individual traced back via its best-scoring known parent."""
        if not self.nodes:
            return []
        scored = [n for n in self.nodes.values() if n.score is not None]
        champ = (
            max(scored, key=lambda n: n.score)  # type: ignore[arg-type,return-value]
            if scored
            else next(iter(self.nodes.values()))
        )
        path = [champ.individual_id]
        seen = {champ.individual_id}
        cur = champ
        while cur.parent_ids:
            known = [
                self.nodes[p]
                for p in cur.parent_ids
                if p in self.nodes and p not in seen
            ]
            if not known:
                break
            nxt = max(known, key=lambda n: n.score if n.score is not None else float("-inf"))
            path.append(nxt.individual_id)
            seen.add(nxt.individual_id)
            cur = nxt
        path.reverse()
        return path


__all__ = ["LineageNode", "LineageVM"]
