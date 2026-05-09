"""JSONLSource — read events from a JSON Lines file or stream-tail it."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

from llove.events import Event, EventKind
from llove.sources.base import DataSource


class JSONLSource(DataSource):
    """Read events from a JSON Lines file.

    Each line must be a JSON object with at least ``kind``. Anything else is
    placed into ``payload`` so downstream views can pick fields they need.

    Pass ``follow=True`` to keep tailing the file as new lines arrive (akin to
    ``tail -F``). Default is finite read-and-stop.
    """

    name = "jsonl"

    def __init__(self, path: str | Path, *, follow: bool = False, poll_seconds: float = 0.5) -> None:
        self._path = Path(path)
        self._follow = follow
        self._poll = poll_seconds

    async def stream(self) -> AsyncIterator[Event]:
        if not self._path.exists():
            return

        with self._path.open("r", encoding="utf-8") as fh:
            # Read existing content first.
            for line in fh:
                ev = self._parse_line(line)
                if ev is not None:
                    yield ev

            if not self._follow:
                return

            # Tail-follow loop.
            while True:
                where = fh.tell()
                line = fh.readline()
                if not line:
                    await asyncio.sleep(self._poll)
                    fh.seek(where)
                    continue
                ev = self._parse_line(line)
                if ev is not None:
                    yield ev

    def _parse_line(self, line: str) -> Event | None:
        line = line.strip()
        if not line:
            return None
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None

        kind_raw = data.pop("kind", None)
        if not kind_raw:
            return None
        try:
            kind = EventKind(kind_raw)
        except ValueError:
            return None

        ts = data.pop("ts", None)
        source_id = data.pop("source_id", str(self._path.name))
        payload = data.pop("payload", None)
        if payload is None:
            payload = data  # everything left is treated as payload

        try:
            kwargs: dict = {"kind": kind, "source_id": source_id, "payload": payload}
            if ts is not None:
                kwargs["ts"] = ts
            return Event(**kwargs)
        except (TypeError, ValueError):
            return None
