"""``DataSource`` adapter that drives the generic ``run_game`` into LoveApp.

This is the ``games.base`` counterpart of :class:`llove.shogi.source.ShogiSource`.
Where ``ShogiSource`` drives the shogi-specific ``llove.shogi.loop.run_game``
(two :class:`~llove.shogi.players.base.Player` instances against a single
shogi :class:`~llove.shogi.engine.Engine`), :class:`GameSource` drives the
**generic** :func:`llove.games.base.loop.run_game` — any
:class:`~llove.games.base.engine.GameEngine` (chess today; go / mahjong on the
roadmap) with a ``{player_id: GamePlayer}`` map. That is what lets a real
LLM chess game (``:play chess`` / ``llove play chess``) flow into the LoveApp
pipeline, for free.

Pane parity is *partial* and honest about it: the generic loop emits only
``AUDIT`` events, so a chess game scrolls the **audit pane**. The shogi play
loop additionally emits a per-move ``SENSOR`` ``eval_score`` event that nudges
the SensorStream / SPC panes — those stay in their empty initial state for a
generic game until a games.base engine emits sensor telemetry of its own.

Like ``ShogiSource`` it can optionally tee every event to stdout as one JSON
line (``also_stdout``). This is a **best-effort** tee: under a running Textual
app the framework may capture ``sys.stdout``, so for a guaranteed machine-
readable stream use ``--no-tui`` (or ``--log`` for the signed JSONL record).
"""

from __future__ import annotations

import sys
from collections.abc import AsyncIterator

from llove.events import Event
from llove.games.base.engine import GameEngine
from llove.games.base.loop import DEFAULT_MAX_PLY, run_game
from llove.games.base.player import GamePlayer
from llove.identity import LoveIdentity
from llove.sources.base import DataSource


class GameSource(DataSource):
    """LoveApp-compatible source that yields events from a generic game.

    Parameters
    ----------
    engine
        An initialised :class:`GameEngine` (e.g. ``ChessEngine()``).
    players
        ``{player_id: GamePlayer}`` covering every ``engine.player_ids()``.
        ``run_game`` fails closed if a player is missing.
    max_ply
        Safety cap on half-moves (forwarded to ``run_game``).
    also_stdout
        When ``True``, tee every event to stdout as one JSON line. A broken
        stdout (closed pipe) is swallowed so it never kills the TUI side.
    identity
        Optional :class:`LoveIdentity` for per-move signing. ``None`` lets
        ``run_game`` discover one via ``load_local_identity()``.
    """

    #: Overridden per-instance in ``__init__`` to the concrete game name.
    name = "game"

    def __init__(
        self,
        engine: GameEngine,
        players: dict[str, GamePlayer],
        *,
        max_ply: int = DEFAULT_MAX_PLY,
        also_stdout: bool = False,
        identity: LoveIdentity | None = None,
    ) -> None:
        self._engine = engine
        self._players = players
        self._max_ply = max_ply
        self._also_stdout = also_stdout
        self._identity = identity
        # Make the source name specific (``"chess"`` etc.) so any UI that reads
        # ``source.name`` shows the game rather than the generic placeholder.
        self.name = engine.game

    async def stream(self) -> AsyncIterator[Event]:
        async for ev in run_game(
            self._engine,
            self._players,
            identity=self._identity,
            max_ply=self._max_ply,
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


__all__ = ["GameSource"]
