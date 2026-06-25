"""Run-control writer — request pause/resume/stop of an evolution run.

The GUI's run-monitor panel calls this to drop a ``control.json`` request into
the run directory; the run process polls that file and honours it. That
engine-side poll is a small llive contract (out of scope here) — llove only
writes the request, **fail-closed**: only known commands are accepted, and a
monotonically increasing ``seq`` lets the run notice a fresh request even when
the command text repeats. Writes are atomic (tmp + ``Path.replace``) so a
polling reader never sees a half-written file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_KNOWN_COMMANDS = frozenset({"pause", "resume", "stop"})


class RunControl:
    """Atomically write control requests into ``<run_dir>/control.json``."""

    def __init__(self, run_dir: str | Path) -> None:
        self._path = Path(run_dir) / "control.json"

    def request(self, command: str) -> None:
        """Write a control request; raise ``ValueError`` for unknown commands."""
        if command not in _KNOWN_COMMANDS:
            raise ValueError(
                f"unknown control command {command!r} "
                f"(known: {sorted(_KNOWN_COMMANDS)})"
            )
        prev = self.read()
        prev_seq = prev.get("seq", 0) if prev else 0
        seq = (int(prev_seq) if isinstance(prev_seq, (int, float)) else 0) + 1
        payload: dict[str, Any] = {"command": command, "seq": seq}
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(self._path)  # atomic on the same filesystem

    def pause(self) -> None:
        self.request("pause")

    def resume(self) -> None:
        self.request("resume")

    def stop(self) -> None:
        self.request("stop")

    def read(self) -> dict[str, Any] | None:
        """Return the current control request, or ``None`` if absent/garbled."""
        try:
            text = self._path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        try:
            data = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None


__all__ = ["RunControl"]
