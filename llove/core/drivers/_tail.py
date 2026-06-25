"""Shared offset-based tail mechanics for the JSONL readers.

Both :class:`MetricsTailReader` and :class:`JsonlTailReader` need the same
fail-closed, byte-offset incremental read (consume only up to the last newline;
reset on truncation). That logic lives here once.
"""

from __future__ import annotations

from pathlib import Path


def read_new_complete_lines(path: Path, offset: int) -> tuple[list[str], int]:
    """Return ``(decoded complete lines since offset, new offset)``.

    Fail-closed: a missing file, an empty read, or a partially-written final
    line yields no lines and leaves the offset where more data can complete it.
    A file that shrank below ``offset`` (a rewrite / fresh run) resets to 0.
    Non-UTF-8 lines are skipped.
    """
    if not path.exists():
        return [], offset
    try:
        size = path.stat().st_size
    except OSError:
        return [], offset
    if size < offset:
        offset = 0

    with path.open("rb") as fh:
        fh.seek(offset)
        data = fh.read()

    if not data:
        return [], offset

    last_nl = data.rfind(b"\n")
    if last_nl == -1:
        return [], offset

    complete = data[: last_nl + 1]
    offset += len(complete)

    lines: list[str] = []
    for raw in complete.split(b"\n"):
        if not raw.strip():
            continue
        try:
            lines.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return lines, offset


__all__ = ["read_new_complete_lines"]
