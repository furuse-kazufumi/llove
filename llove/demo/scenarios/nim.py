"""nim — an interactive Nim cartridge (single-heap subtraction game).

Classic **Nim** in its simplest single-heap form. A pile starts with 15-21
objects; on each turn a player removes 1, 2, or 3 of them. Whoever takes the
**last** object **wins** (normal play, not misere).

You move first against a deterministic CPU that plays the optimal modulo-4
strategy — it tries to hand you a heap that is a multiple of four, the losing
position — but slips into a random legal move now and then so the game is not
a foregone conclusion. The opponent here is a tiny rule-based AI driven by a
seeded RNG, **not a real LLM**. Wiring two LLMs to play (and explain) their
moves is a planned future cartridge, the same upgrade path the shogi demo
sketches; this MVP just proves the turn loop, the win condition, and the
audit trail.

Like every llove demo it runs fully offline. With no asker wired (CI /
``--list`` / a unit test), every turn falls back to the deterministic default
move (the optimal take), so the flow always reaches a terminal state and emits
a result narration.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_MIN_START = 15
_MAX_START = 21
_MAX_TAKE = 3
# Hard cap on loop iterations. The heap strictly shrinks by >= 2 each round
# (one human take + one CPU take), so a 21-object pile resolves in well under
# this many turns; the cap is a belt-and-braces termination guarantee.
_MAX_TURNS = 40
# Probability the CPU deviates from optimal play into a random legal move.
_SLIP_PROB = 0.18


def _optimal_take(heap: int) -> int:
    """Optimal take for normal-play subtraction Nim with set {1,2,3}.

    The P-positions (bad for the player to move) are multiples of four. From a
    non-multiple, removing ``heap % 4`` hands the opponent a multiple of four.
    From a multiple of four every move loses against perfect play, so we fall
    back to the smallest legal take.
    """
    remainder = heap % (_MAX_TAKE + 1)
    if remainder == 0:
        return min(_MAX_TAKE, heap)
    return remainder


class NimScenario(InteractiveScenario):
    """Single-heap Nim: take 1-3, last to take wins, vs a mod-4 CPU."""

    name = "nim"
    i18n_key = "nim"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _legal_takes(self, heap: int) -> list[int]:
        return [k for k in range(1, _MAX_TAKE + 1) if k <= heap]

    def _board(self, heap: int) -> str:
        """Build the (dynamic) heap display — no i18n, glyphs + count only."""
        pile = "●" * heap if heap else "—"
        return f"{pile}  ({heap})"

    def _cpu_move(self, heap: int) -> int:
        """Pick the CPU's take: optimal mod-4, with an occasional random slip."""
        legal = self._legal_takes(heap)
        if self._rng.random() < _SLIP_PROB:
            return self._rng.choice(legal)
        return _optimal_take(heap)

    def _audit(self, event: str, display: str, **extra: object) -> Event:
        payload: dict[str, object] = {"event": event, "display": display}
        payload.update(extra)
        return Event(kind=EventKind.AUDIT, source_id="nim", payload=payload)

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.nim.intro", title_key="scenario.nim.intro_title")

        heap: int = self._rng.randint(_MIN_START, _MAX_START)
        yield self._audit("nim.game_start", f"Heap starts at {heap}.", heap=heap)

        winner: str | None = None
        for _ in range(_MAX_TURNS):
            if heap <= 0:
                break

            # ---- human turn -------------------------------------------------
            yield narrate(self._board(heap), title=t("scenario.nim.turn"))
            legal = self._legal_takes(heap)
            opts = [ChoiceOption(str(k), t("scenario.nim.take_n", n=k)) for k in legal]
            optimal = _optimal_take(heap)
            default_id = str(optimal) if optimal in legal else str(legal[0])
            move = await self.ask(t("scenario.nim.your_move"), opts, default_id=default_id)
            take = int(move) if move.isdigit() and int(move) in legal else legal[0]
            heap -= take
            yield narrate(
                f"You take {take}.  →  {self._board(heap)}",
                title=t("scenario.nim.turn"),
            )
            yield self._audit("nim.human_move", f"Human takes {take} (heap {heap}).",
                              take=take, heap=heap, side="human")
            if heap <= 0:
                winner = "human"
                break

            # ---- CPU turn ---------------------------------------------------
            ctake = self._cpu_move(heap)
            heap -= ctake
            yield narrate(
                f"CPU takes {ctake}.  →  {self._board(heap)}",
                title=t("scenario.nim.cpu_turn"),
            )
            yield self._audit("nim.cpu_move", f"CPU takes {ctake} (heap {heap}).",
                              take=ctake, heap=heap, side="cpu")
            if heap <= 0:
                winner = "cpu"
                break

        yield self._audit("nim.game_end", f"Winner: {winner or 'cpu'}.", winner=winner or "cpu")
        if winner == "human":
            yield narrate_key("scenario.nim.result_win", title_key="scenario.nim.result_title")
        else:
            yield narrate_key("scenario.nim.result_lose", title_key="scenario.nim.result_title")


__all__ = ["NimScenario"]
