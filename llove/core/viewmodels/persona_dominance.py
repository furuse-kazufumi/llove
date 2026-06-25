"""Persona-dominance view-model — founder share per generation.

Reads ``founder_lineage.jsonl`` rows
(``{generation, n_individuals, founder_counts: {name: count}}``) into per-founder
*share* (count / population) series aligned across generations: a founder that
first appears at generation k is back-filled with zeros for 0..k-1, and any
founder absent in a generation is zero there. This drives the dominance panel
(P4) and its monoculture guard (``max_share`` should stay below ~0.8). Pure — no
Qt / Textual.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PersonaDominanceVM:
    """Accumulates per-founder share series from founder-lineage rows."""

    generations: list[int] = field(default_factory=list)
    _shares: dict[str, list[float]] = field(default_factory=dict)

    def feed(self, row: dict[str, Any]) -> bool:
        """Append one founder-lineage row; ``False`` if it is unusable."""
        if not isinstance(row, dict) or "generation" not in row:
            return False
        counts = row.get("founder_counts")
        if not isinstance(counts, dict) or not counts:
            return False
        try:
            gen = int(row["generation"])
        except (TypeError, ValueError):
            return False

        # Population: explicit n_individuals, else the sum of the counts.
        n_raw = row.get("n_individuals")
        try:
            total = (
                float(n_raw)
                if isinstance(n_raw, (int, float)) and not isinstance(n_raw, bool)
                else 0.0
            )
        except (TypeError, ValueError):
            total = 0.0
        numeric_counts: dict[str, float] = {}
        running = 0.0
        for name, value in counts.items():
            try:
                c = float(value)
            except (TypeError, ValueError):
                c = 0.0
            numeric_counts[str(name)] = c
            running += c
        if total <= 0:
            total = running
        if total <= 0:
            return False

        index = len(self.generations)
        # Back-fill any newly-seen founder with zeros for the prior generations.
        for name in numeric_counts:
            if name not in self._shares:
                self._shares[name] = [0.0] * index
        # Append this generation's share for every known founder (0 if absent).
        for name, series in self._shares.items():
            series.append(numeric_counts.get(name, 0.0) / total)
        self.generations.append(gen)
        return True

    @property
    def count(self) -> int:
        return len(self.generations)

    def founders(self) -> list[str]:
        """Founder names, sorted for stable legend ordering."""
        return sorted(self._shares)

    def series(self) -> dict[str, list[float]]:
        """``{founder: [share per generation]}``, all aligned to ``generations``."""
        return {name: list(self._shares[name]) for name in self.founders()}

    def max_share_per_generation(self) -> list[float]:
        """Largest single-founder share at each generation (monoculture guard)."""
        if not self.generations:
            return []
        result: list[float] = []
        for i in range(len(self.generations)):
            result.append(max((series[i] for series in self._shares.values()), default=0.0))
        return result


__all__ = ["PersonaDominanceVM"]
