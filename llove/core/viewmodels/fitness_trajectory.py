"""Fitness-trajectory view-model for evolution-run ``metrics.jsonl``.

The evolution engine writes one JSON object per generation, e.g.::

    {"generation": 0, "n_individuals": 32, "best_score": 0.74, "mean_score": 0.50,
     "std_score": 0.11, "median_score": 0.49, "diversity_l2": 28.5, "seed": 0}

(see C:/dev/projects/llive/out/<run>/metrics.jsonl). This view-model parses those raw
rows and keeps aligned per-generation series (best / mean / median / std) ready
for a plot. It is **pure** — no Textual, no Qt — so the Textual front and the new
Qt front (``llove/qt``) both subscribe to it (design §5.2). Missing optional
fields become ``nan`` so the series stay length-aligned with ``generation``.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any

# A row must carry a generation index and at least one score to be plottable.
_SCORE_KEYS = ("best_score", "mean_score")


def _as_float(value: Any, *, default: float = math.nan) -> float:
    """Best-effort float coercion; ``default`` (nan) when missing/unparseable."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_metrics_row(line: str) -> dict[str, Any] | None:
    """Parse one ``metrics.jsonl`` line into a dict, or ``None`` if unusable.

    Tolerant (fail-closed per row, never raises): rejects blank lines, non-JSON,
    non-objects, rows without ``generation``, and rows without any score field.
    ``generation`` is coerced to ``int``.
    """
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if "generation" not in data:
        return None
    if not any(k in data for k in _SCORE_KEYS):
        return None
    try:
        gen = int(data["generation"])
    except (TypeError, ValueError):
        return None
    out: dict[str, Any] = dict(data)
    out["generation"] = gen
    return out


@dataclass
class FitnessTrajectoryVM:
    """Accumulates per-generation fitness series from parsed metrics rows.

    ``feed`` accepts an already-parsed dict; ``feed_line`` parses a raw JSONL
    line first. Both return ``True`` only when the row was accepted, so callers
    can count how many points were added (and skip a redraw when zero).
    """

    generations: list[int] = field(default_factory=list)
    best: list[float] = field(default_factory=list)
    mean: list[float] = field(default_factory=list)
    median: list[float] = field(default_factory=list)
    std: list[float] = field(default_factory=list)

    def feed(self, row: dict[str, Any]) -> bool:
        """Append one parsed row; ``False`` if it lacks a generation or any score."""
        if not isinstance(row, dict) or "generation" not in row:
            return False
        try:
            gen = int(row["generation"])
        except (TypeError, ValueError):
            return False
        best = _as_float(row.get("best_score"), default=math.nan)
        mean = _as_float(row.get("mean_score"), default=math.nan)
        if math.isnan(best) and math.isnan(mean):
            return False
        self.generations.append(gen)
        self.best.append(best)
        self.mean.append(mean)
        self.median.append(_as_float(row.get("median_score")))
        self.std.append(_as_float(row.get("std_score")))
        return True

    def feed_line(self, line: str) -> bool:
        """Parse a raw JSONL line then ``feed`` it; ``False`` if unusable."""
        row = parse_metrics_row(line)
        if row is None:
            return False
        return self.feed(row)

    @property
    def count(self) -> int:
        """Number of accepted generations."""
        return len(self.generations)

    def series(self) -> dict[str, list[float]]:
        """Plot-ready aligned series. ``generation`` is returned as floats."""
        return {
            "generation": [float(g) for g in self.generations],
            "best": list(self.best),
            "mean": list(self.mean),
            "median": list(self.median),
            "std": list(self.std),
        }


__all__ = ["FitnessTrajectoryVM", "parse_metrics_row"]
