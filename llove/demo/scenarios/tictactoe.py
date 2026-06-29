"""tictactoe — an interactive 3x3 tic-tac-toe cartridge (board game).

You play **X** against a small deterministic heuristic CPU (**O**). Each turn
*you* pick an empty cell (1-9) at a choice-point; place three in a row to win.
Like every llove demo it runs fully offline and synthetic — the new part is
that you steer it move by move.

The opponent is **not** a real LLM: it is a fixed rule-based player
(win / block / center / corner / side) driven by ``self._rng`` only to break
ties deterministically. Wiring an actual LLM (or two) as the opponent is a
**future session** — the per-move Event/AUDIT trail already carries enough
board state to drop one in later.

With no asker wired (CI / ``--list`` / a unit test), :meth:`ask` returns the
deterministic default cell each turn, so the game still plays itself to a
terminal result. The game can never exceed nine placements, so it always
terminates.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

# The eight winning triples on a 3x3 board (0-indexed cells, 1-9 on screen).
_WIN_LINES: list[tuple[int, int, int]] = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columns
    (0, 4, 8), (2, 4, 6),             # diagonals
]
_CENTER = 4
_CORNERS: tuple[int, ...] = (0, 2, 6, 8)
_MAX_TURNS = 9  # hard cap — at most nine cells can ever be filled


def _winner(board: list[str]) -> str | None:
    """Return ``"X"`` / ``"O"`` if a side owns a line, else ``None``."""
    for a, b, c in _WIN_LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def _render(board: list[str]) -> str:
    """Render the board; empty cells show their 1-9 number so X can pick."""
    cells = [board[i] if board[i] != " " else str(i + 1) for i in range(9)]
    rows: list[str] = []
    for r in range(3):
        a, b, c = cells[3 * r], cells[3 * r + 1], cells[3 * r + 2]
        rows.append(f" {a} | {b} | {c} ")
        if r < 2:
            rows.append("---+---+---")
    return "\n".join(rows)


class TicTacToeScenario(InteractiveScenario):
    """Play tic-tac-toe as X against a simple heuristic CPU (O)."""

    name = "tictactoe"
    i18n_key = "tictactoe"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _cpu_pick(self, board: list[str], empties: list[int]) -> int:
        """Simple heuristic: win, else block, else center, else corner, else side."""
        for c in empties:  # take a winning move if one exists
            board[c] = "O"
            won = _winner(board) == "O"
            board[c] = " "
            if won:
                return c
        for c in empties:  # otherwise block X's winning move
            board[c] = "X"
            block = _winner(board) == "X"
            board[c] = " "
            if block:
                return c
        if _CENTER in empties:
            return _CENTER
        corners = [c for c in _CORNERS if c in empties]
        if corners:
            return self._rng.choice(corners)
        return self._rng.choice(empties)

    def _move(self, player: str, cell: int) -> Event:
        """An AUDIT event recording one placement (cell is 1-9 for humans)."""
        return Event(
            kind=EventKind.AUDIT,
            source_id="tictactoe",
            payload={
                "event": "tictactoe.move",
                "player": player,
                "cell": cell + 1,
                "display": f"{player} -> {cell + 1}",
            },
        )

    def _board(self, board: list[str]) -> Event:
        return narrate(
            f"```\n{_render(board)}\n```",
            title=t("scenario.tictactoe.turn"),
        )

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.tictactoe.intro", title_key="scenario.tictactoe.intro_title"
        )

        board = [" "] * 9
        outcome: str | None = None

        for _turn in range(_MAX_TURNS):
            empties = [i for i in range(9) if board[i] == " "]
            if not empties:
                break

            # --- your move (the choice-point) -----------------------------
            yield self._board(board)
            options = [
                ChoiceOption(str(i + 1), t("scenario.tictactoe.cell", n=i + 1))
                for i in empties
            ]
            default_id = "5" if _CENTER in empties else str(empties[0] + 1)
            valid_ids = {str(i + 1) for i in empties}
            move = await self.ask(
                t("scenario.tictactoe.your_move"), options, default_id=default_id
            )
            cell = (int(move) if move in valid_ids else int(default_id)) - 1
            board[cell] = "X"
            yield self._move("X", cell)
            if _winner(board) == "X":
                outcome = "win"
                break
            if all(c != " " for c in board):
                outcome = "draw"
                break

            # --- CPU reply (deterministic heuristic) ----------------------
            empties = [i for i in range(9) if board[i] == " "]
            cpu_cell = self._cpu_pick(board, empties)
            board[cpu_cell] = "O"
            yield self._move("O", cpu_cell)
            if _winner(board) == "O":
                outcome = "lose"
                break
            if all(c != " " for c in board):
                outcome = "draw"
                break

        if outcome is None:  # defensive — the loop always sets one
            outcome = "draw"

        yield self._board(board)
        yield narrate_key(
            f"scenario.tictactoe.result_{outcome}",
            title_key="scenario.tictactoe.result_title",
        )


__all__ = ["TicTacToeScenario"]
