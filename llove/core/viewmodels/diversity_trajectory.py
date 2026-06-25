"""Diversity-trajectory view-model — ``diversity_l2`` per generation.

``diversity_l2`` is carried in the same ``metrics.jsonl`` rows the fitness VM
reads, so this view-model accepts the very same parsed rows (the shell wires one
metrics tail to both panels). Rows without a ``diversity_l2`` field are rejected
so the series stays clean. Pure — no Qt / Textual.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from llove.core.viewmodels.fitness_trajectory import parse_metrics_row


def _as_float(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


@dataclass
class DiversityTrajectoryVM:
    """Accumulates ``(generation, diversity_l2)`` from parsed metrics rows."""

    generations: list[int] = field(default_factory=list)
    diversity: list[float] = field(default_factory=list)

    def feed(self, row: dict[str, Any]) -> bool:
        """Append a row; ``False`` if it lacks a generation or ``diversity_l2``."""
        if not isinstance(row, dict) or "generation" not in row:
            return False
        try:
            gen = int(row["generation"])
        except (TypeError, ValueError):
            return False
        div = _as_float(row.get("diversity_l2"))
        if math.isnan(div):
            return False
        self.generations.append(gen)
        self.diversity.append(div)
        return True

    def feed_line(self, line: str) -> bool:
        """Parse a raw metrics line then ``feed`` it; ``False`` if unusable."""
        row = parse_metrics_row(line)
        if row is None:
            return False
        return self.feed(row)

    @property
    def count(self) -> int:
        return len(self.generations)

    def series(self) -> dict[str, list[float]]:
        return {
            "generation": [float(g) for g in self.generations],
            "diversity": list(self.diversity),
        }


__all__ = ["DiversityTrajectoryVM"]
