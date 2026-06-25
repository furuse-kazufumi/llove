"""Genome heatmap view-model — individuals x genes matrix from a snapshot.

An evolution run writes ``snapshot_gen_NNNN.json`` with all individuals; each
carries a Genome3D whose ``c_factors`` block has ``factor_names`` [N] and
``factor_weights`` [N x K]. This view-model flattens those weights into one row
per individual (``factor#k`` columns) for the P5 heatmap (design §3). Pure — no
Qt. Helpers to locate/load the latest snapshot live here too (file-boundary
decoupling; the engine is never imported).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SNAPSHOT_RE = re.compile(r"snapshot_gen_(\d+)\.json$")


@dataclass
class GenomeHeatmap:
    """Rectangular individuals x genes matrix with row/column labels."""

    matrix: list[list[float]] = field(default_factory=list)
    row_labels: list[str] = field(default_factory=list)
    col_labels: list[str] = field(default_factory=list)


def _flatten_factors(genome: Any) -> tuple[list[float], list[str]] | None:
    """Return (flattened weights, column labels) from a genome's c_factors."""
    if not isinstance(genome, dict):
        return None
    cf = genome.get("c_factors")
    if not isinstance(cf, dict):
        return None
    weights = cf.get("factor_weights")
    names = cf.get("factor_names")
    if not isinstance(weights, list) or not weights:
        return None
    flat: list[float] = []
    labels: list[str] = []
    for fi, wrow in enumerate(weights):
        if not isinstance(wrow, list):
            return None
        fname = names[fi] if isinstance(names, list) and fi < len(names) else f"f{fi}"
        for k, w in enumerate(wrow):
            try:
                flat.append(float(w))
            except (TypeError, ValueError):
                return None
            labels.append(f"{fname}#{k}")
    return flat, labels


class GenomeHeatmapVM:
    """Builds a :class:`GenomeHeatmap` from a parsed snapshot dict."""

    def __init__(self) -> None:
        self.heatmap = GenomeHeatmap()

    def load_snapshot(self, snapshot: dict[str, Any]) -> GenomeHeatmap:
        """Flatten each individual's c_factors into an aligned matrix."""
        individuals = snapshot.get("individuals") if isinstance(snapshot, dict) else None
        rows: list[list[float]] = []
        row_labels: list[str] = []
        col_labels: list[str] = []
        for i, ind in enumerate(individuals or []):
            if not isinstance(ind, dict):
                continue
            result = _flatten_factors(ind.get("genome"))
            if result is None:
                continue
            flat, labels = result
            if not col_labels:
                col_labels = labels
            elif len(flat) != len(col_labels):
                continue  # width mismatch -> keep matrix rectangular
            rows.append(flat)
            row_labels.append(str(ind.get("individual_id", f"ind{i}")))
        self.heatmap = GenomeHeatmap(matrix=rows, row_labels=row_labels, col_labels=col_labels)
        return self.heatmap


def load_snapshot_file(path: str | Path) -> dict[str, Any] | None:
    """Load a snapshot JSON file, or ``None`` if absent/unreadable/not-an-object."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def find_latest_snapshot(run_dir: str | Path) -> Path | None:
    """Return the highest-generation ``snapshot_gen_*.json`` in ``run_dir``."""
    directory = Path(run_dir)
    if not directory.is_dir():
        return None
    best: tuple[int, Path] | None = None
    for p in directory.glob("snapshot_gen_*.json"):
        m = _SNAPSHOT_RE.search(p.name)
        if m is None:
            continue
        gen = int(m.group(1))
        if best is None or gen > best[0]:
            best = (gen, p)
    return best[1] if best is not None else None


__all__ = [
    "GenomeHeatmap",
    "GenomeHeatmapVM",
    "find_latest_snapshot",
    "load_snapshot_file",
]
