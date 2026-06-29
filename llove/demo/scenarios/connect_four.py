"""connect_four — an interactive Connect Four cartridge (board game).

You play discs against a deterministic CPU on a 7x6 grid. On every turn you
**choose a column** (1-7) and your disc drops to the lowest empty row; the CPU
then replies with a simple win/block/random heuristic. First to line up four
discs (horizontal, vertical, or diagonal) wins; a full board is a draw.

The opponent is a **deterministic heuristic, not a real LLM** — it only looks
one ply ahead (take a winning move, else block the human's winning move, else
pick a random legal column, seeded by ``seed`` for reproducible playback).
Wiring two LLMs in as the players (à la the shogi cartridge's MVP2) is left as
**future work for a later session**.

Like every demo it runs fully offline. With no asker wired (CI / ``--list``),
the deterministic default path drops in the leftmost legal column each turn, so
the game always reaches a terminal narration.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_ROWS = 6
_COLS = 7
_CONNECT = 4
_MAX_PLIES = _ROWS * _COLS  # 42 — hard cap that guarantees termination.

_HUMAN = "X"
_CPU = "O"
_EMPTY = "."


def _new_board() -> list[list[str]]:
    return [[_EMPTY for _ in range(_COLS)] for _ in range(_ROWS)]


def _legal_cols(board: list[list[str]]) -> list[int]:
    """Columns (0-indexed) that still have room for a disc."""
    return [c for c in range(_COLS) if board[0][c] == _EMPTY]


def _drop(board: list[list[str]], col: int, piece: str) -> int:
    """Drop ``piece`` into ``col``; return the row it landed in."""
    for r in range(_ROWS - 1, -1, -1):
        if board[r][col] == _EMPTY:
            board[r][col] = piece
            return r
    raise ValueError(f"column {col} is full")


def _wins(board: list[list[str]], piece: str, row: int, col: int) -> bool:
    """True if the disc just placed at (row, col) completes four in a row."""
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        count = 1
        for sign in (1, -1):
            r, c = row + dr * sign, col + dc * sign
            while 0 <= r < _ROWS and 0 <= c < _COLS and board[r][c] == piece:
                count += 1
                r += dr * sign
                c += dc * sign
        if count >= _CONNECT:
            return True
    return False


class ConnectFourScenario(InteractiveScenario):
    name = "connect_four"
    i18n_key = "connect_four"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ render
    def _render(self, board: list[list[str]]) -> str:
        header = "  " + " ".join(str(c + 1) for c in range(_COLS))
        rows = ["| " + " ".join(row) + " |" for row in board]
        footer = "+" + "-" * (2 * _COLS + 1) + "+"
        return "\n".join([header, *rows, footer])

    def _board_event(self, board: list[list[str]]) -> Event:
        return narrate(self._render(board), title=t("scenario.connect_four.turn"))

    def _audit(self, who: str, col: int) -> Event:
        key = "scenario.connect_four.human_move" if who == _HUMAN else "scenario.connect_four.cpu_move"
        return Event(
            kind=EventKind.AUDIT,
            source_id="connect_four",
            payload={
                "event": "move.human" if who == _HUMAN else "move.cpu",
                "piece": who,
                "column": col + 1,
                "display": t(key, col=col + 1),
            },
        )

    # --------------------------------------------------------------- opponent
    def _cpu_move(self, board: list[list[str]], legal: list[int]) -> int:
        """One-ply heuristic: win if possible, else block, else random."""
        for piece in (_CPU, _HUMAN):  # first try to win, then to block.
            for c in legal:
                r = _drop(board, c, piece)
                hit = _wins(board, piece, r, c)
                board[r][c] = _EMPTY  # undo the probe.
                if hit:
                    return c
        return self._rng.choice(legal)

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.connect_four.intro",
            title_key="scenario.connect_four.intro_title",
        )
        board = _new_board()
        yield self._board_event(board)

        human_turn = True
        for _ply in range(_MAX_PLIES):
            legal = _legal_cols(board)
            if not legal:
                break

            if human_turn:
                opts = [
                    ChoiceOption(str(c + 1), t("scenario.connect_four.col_label", col=c + 1))
                    for c in legal
                ]
                choice = await self.ask(
                    t("scenario.connect_four.your_move"),
                    opts,
                    default_id=str(legal[0] + 1),
                )
                try:
                    col = int(choice) - 1
                except ValueError:
                    col = legal[0]
                if col not in legal:
                    col = legal[0]
                piece = _HUMAN
            else:
                col = self._cpu_move(board, legal)
                piece = _CPU

            row = _drop(board, col, piece)
            yield self._audit(piece, col)
            yield self._board_event(board)

            if _wins(board, piece, row, col):
                key = "result_win" if piece == _HUMAN else "result_lose"
                yield narrate_key(
                    f"scenario.connect_four.{key}",
                    title_key="scenario.connect_four.result_title",
                )
                return

            human_turn = not human_turn

        # Board filled (or the hard cap was hit) with no four-in-a-row.
        yield narrate_key(
            "scenario.connect_four.result_draw",
            title_key="scenario.connect_four.result_title",
        )


__all__ = ["ConnectFourScenario"]
