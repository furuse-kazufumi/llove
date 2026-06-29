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

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
        """Parse a raw QD metrics JSONL line then ``feed`` it; ``False`` if unusable.

        The QD metrics file uses different score keys (``scalar_best``) than the
        fitness ``metrics.jsonl``, so this parses the line directly rather than
        reusing the fitness row parser; ``feed`` does the field validation.
        """
        line = line.strip()
        if not line:
            return False
        try:
            row = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return False
        if not isinstance(row, dict):
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


def find_qd_metrics(run_dir: str | Path) -> Path | None:
    """Return a QD metrics file (``metrics_*_qd.jsonl``) in ``run_dir``, or ``None``.

    QD runs name the file after their config (e.g. ``metrics_scalar_qd.jsonl`` /
    ``metrics_novelty_std_qd.jsonl``), so there is no fixed name; pick the
    lexicographically-first match for a stable default.
    """
    directory = Path(run_dir)
    if not directory.is_dir():
        return None
    matches = sorted(directory.glob("metrics_*_qd.jsonl"))
    return matches[0] if matches else None


__all__ = ["QdArchiveVM", "find_qd_metrics"]
