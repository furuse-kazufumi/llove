"""QD-archive view-model — quality-diversity archive coverage per generation.

Reads the quality-diversity metrics rows (``metrics_*_qd.jsonl`` produced by the
open-ended / QD runs): ``archive_cells`` is the cumulative count of behavioural
niches ever filled (coverage growth, non-decreasing) and ``occupied_cells`` is how
many are occupied *right now* (live occupancy, which can fall as the population
converges). The gap between the two is the exploration-vs-convergence story of an
open-ended run. Rows without an ``archive_cells`` field are rejected so the series
stays clean; ``occupied_cells`` is optional (NaN when absent, which pyqtgraph draws
as a gap). Pure — no Qt / Textual.
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
class QdArchiveVM:
    """Accumulates ``(generation, archive_cells, occupied_cells)`` from QD metrics rows."""

    generations: list[int] = field(default_factory=list)
    archive_cells: list[float] = field(default_factory=list)
    occupied_cells: list[float] = field(default_factory=list)

    def feed(self, row: dict[str, Any]) -> bool:
        """Append a row; ``False`` if it lacks a generation or ``archive_cells``."""
        if not isinstance(row, dict) or "generation" not in row:
            return False
        try:
            gen = int(row["generation"])
        except (TypeError, ValueError):
            return False
        arch = _as_float(row.get("archive_cells"))
        if math.isnan(arch):
            return False
        self.generations.append(gen)
        self.archive_cells.append(arch)
        self.occupied_cells.append(_as_float(row.get("occupied_cells")))
        return True

    def feed_line(self, line: str) -> bool:
        """Parse a raw QD metrics line then ``feed`` it; ``False`` if unusable."""
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
            "archive_cells": list(self.archive_cells),
            "occupied_cells": list(self.occupied_cells),
        }


__all__ = ["QdArchiveVM"]
