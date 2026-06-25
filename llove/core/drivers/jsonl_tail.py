"""Generic JSON-Lines tail reader — yields raw dict rows since the last poll.

Like :class:`MetricsTailReader` but schema-agnostic: it returns every complete
line that parses to a JSON object. Used for run artifacts that are not metrics
rows (e.g. ``founder_lineage.jsonl`` for the persona-dominance panel), which the
metrics-specific reader would reject. Shares the offset mechanics in
``_tail.read_new_complete_lines`` (fail-closed, partial-line safe).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llove.core.drivers._tail import read_new_complete_lines


class JsonlTailReader:
    """Read new JSON-object lines from a JSONL file since the last ``poll``."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._offset = 0

    def poll(self) -> list[dict[str, Any]]:
        """Return JSON-object rows that became complete since the previous call."""
        lines, self._offset = read_new_complete_lines(self._path, self._offset)
        rows: list[dict[str, Any]] = []
        for line in lines:
            try:
                obj = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    def reset(self) -> None:
        """Forget progress so the next ``poll`` re-reads from the start."""
        self._offset = 0


__all__ = ["JsonlTailReader"]
