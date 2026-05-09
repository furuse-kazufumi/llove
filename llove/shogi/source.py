"""``DataSource`` adapter that drives ``run_game`` into LoveApp's pipeline.

LoveApp consumes a :class:`~llove.sources.base.DataSource`; ``run_game``
yields :class:`Event`s. This module is the thin glue between the two so
``llove play shogi`` can use the existing TUI panes for free.

The adapter optionally tees every event to stdout as a JSON line, which
lets ``llove play shogi --stream`` produce both a watchable TUI **and** a
machine-readable log on the same run.
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator

from llove.events import Event
from llove.shogi.loop import run_game
from llove.shogi.players.base import Player
from llove.sources.base import DataSource


class ShogiSource(DataSource):
    """LoveApp-compatible source that yields events from a shogi game."""

    name = "shogi"

    def __init__(
        self,
        sente: Player,
        gote: Player,
        *,
        max_ply: int = 400,
        also_stdout: bool = False,
    ) -> None:
        self._sente = sente
        self._gote = gote
        self._max_ply = max_ply
        self._also_stdout = also_stdout

    async def stream(self) -> AsyncIterator[Event]:
        async for ev in run_game(
            self._sente, self._gote, max_ply=self._max_ply
        ):
            if self._also_stdout:
                # fail-closed: a broken stdout (e.g. pipe closed) must not
                # kill the TUI side.
                try:
                    sys.stdout.write(ev.model_dump_json() + "\n")
                    sys.stdout.flush()
                except Exception:  # nosec B110
                    pass
            yield ev
