"""Run-status view-model — snapshot an evolution run directory.

Reads, tolerantly, three file-boundary artifacts an evolution run writes (design
§0.3) into one :class:`RunStatus` for the run-monitor panel (P7):

* ``run_manifest.json`` (``run_manifest/v1``) — run config (fitness, population,
  target generations, seed).
* ``run_summary.json`` (``run_summary/v1``) — present only once the run finishes
  (status, final generation, best score, stop reason, elapsed).
* ``metrics.jsonl`` — the live tail; its last row gives the *current* generation
  and best score while the run is in flight.

Never imports the engine; missing/garbled files degrade to ``None`` fields and a
``"running"``/``"unknown"`` status rather than raising.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from llove.core.viewmodels.fitness_trajectory import parse_metrics_row


def _load_json_obj(path: Path) -> dict[str, Any] | None:
    """Read a JSON object, or ``None`` if absent/unreadable/not-an-object."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _last_metrics_row(path: Path) -> dict[str, Any] | None:
    """Return the last parseable metrics row, or ``None``."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    last: dict[str, Any] | None = None
    for line in text.splitlines():
        row = parse_metrics_row(line)
        if row is not None:
            last = row
    return last


def _opt_int(source: dict[str, Any] | None, key: str) -> int | None:
    if source is None:
        return None
    value = source.get(key)
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _opt_float(source: dict[str, Any] | None, key: str) -> float | None:
    if source is None:
        return None
    value = source.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _opt_str(source: dict[str, Any] | None, key: str) -> str | None:
    if source is None:
        return None
    value = source.get(key)
    return str(value) if value is not None else None


@dataclass(frozen=True)
class RunStatus:
    """One immutable snapshot of a run's state."""

    status: str = "unknown"
    fitness: str | None = None
    population: int | None = None
    target_generations: int | None = None
    current_generation: int | None = None
    best_score: float | None = None
    stopped_reason: str | None = None
    elapsed_seconds: float | None = None
    seed: int | None = None


class RunStatusVM:
    """Re-reads a run directory on each :meth:`refresh` into a :class:`RunStatus`."""

    def __init__(self, run_dir: str | Path) -> None:
        self._dir = Path(run_dir)

    def refresh(self) -> RunStatus:
        """Read manifest + summary + live metrics tail into a status snapshot."""
        manifest = _load_json_obj(self._dir / "run_manifest.json")
        summary = _load_json_obj(self._dir / "run_summary.json")
        last = _last_metrics_row(self._dir / "metrics.jsonl")

        if summary is not None:
            status = _opt_str(summary, "status") or "completed"
        elif manifest is not None:
            status = "running"
        else:
            status = "unknown"

        # Current generation / best score: prefer the live tail, else the summary.
        current_generation: int | None = None
        best_score: float | None = None
        if last is not None:
            current_generation = int(last["generation"])
            best_score = _opt_float(last, "best_score")
        elif summary is not None:
            current_generation = _opt_int(summary, "final_generation")
            best_score = _opt_float(summary, "best_score")

        return RunStatus(
            status=status,
            fitness=_opt_str(manifest, "fitness"),
            population=_opt_int(manifest, "population"),
            target_generations=_opt_int(manifest, "generations"),
            current_generation=current_generation,
            best_score=best_score,
            stopped_reason=_opt_str(summary, "stopped_reason"),
            elapsed_seconds=_opt_float(summary, "elapsed_seconds"),
            seed=_opt_int(manifest, "seed"),
        )


__all__ = ["RunStatus", "RunStatusVM"]
