"""reversi — an interactive 6x6 Reversi (Othello) cartridge (you vs. a CPU).

A small 6x6 board starts with the four centre discs. On your turn llove
**stops and asks you which legal move to play** — a move must flank one or
more of the CPU's discs in a straight line bounded by one of your own, and
every flanked disc flips to your colour. If you have no legal move you pass.
The CPU then replies with a deterministic greedy policy (it grabs the move
that flips the most discs, breaking ties with a seeded RNG so ``--seed``
makes playback reproducible). The game ends when the board fills up or both
sides pass in a row; whoever holds the most discs wins.

This is a *self-contained, fully-offline* demo: the opponent is a tiny
deterministic engine, **not a real LLM**. Wiring two LLMs (or a human vs. an
LLM) into the move loop — reusing the same legality checker and Event
payloads — is the planned next-session upgrade, mirroring the shogi
cartridge's MVP ladder.

With no asker wired (CI / ``--list`` / a unit test), :meth:`ask` returns the
deterministic default move (the highest-flip legal move) every turn, so the
whole game still plays itself to a final result.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_BLACK = "B"   # the human player (you), moves first
_WHITE = "W"   # the CPU
_EMPTY = "."
_SIZE = 6
_MAX_TURNS = 40        # hard cap — guarantees the loop always terminates
_MAX_CHOICES = 9       # keep the per-turn choice list small and bounded
_COLS = "abcdef"
_GLYPH = {_BLACK: "●", _WHITE: "○", _EMPTY: "·"}
_DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _initial_board() -> list[list[str]]:
    """Standard Othello opening: white on one centre diagonal, black on the other."""
    board = [[_EMPTY for _ in range(_SIZE)] for _ in range(_SIZE)]
    board[2][2] = _WHITE
    board[3][3] = _WHITE
    board[2][3] = _BLACK
    board[3][2] = _BLACK
    return board


def _coord(r: int, c: int) -> str:
    return f"{_COLS[c]}{r + 1}"


def _flips(board: list[list[str]], r: int, c: int, player: str) -> list[tuple[int, int]]:
    """Discs that placing ``player`` at (r, c) would flank-and-flip (empty list if illegal)."""
    if board[r][c] != _EMPTY:
        return []
    opp = _WHITE if player == _BLACK else _BLACK
    out: list[tuple[int, int]] = []
    for dr, dc in _DIRS:
        line: list[tuple[int, int]] = []
        rr, cc = r + dr, c + dc
        while 0 <= rr < _SIZE and 0 <= cc < _SIZE and board[rr][cc] == opp:
            line.append((rr, cc))
            rr += dr
            cc += dc
        if line and 0 <= rr < _SIZE and 0 <= cc < _SIZE and board[rr][cc] == player:
            out.extend(line)
    return out


def _legal_moves(
    board: list[list[str]], player: str
) -> dict[tuple[int, int], list[tuple[int, int]]]:
    """Map every legal move for ``player`` to the discs it would flip."""
    moves: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for r in range(_SIZE):
        for c in range(_SIZE):
            if board[r][c] != _EMPTY:
                continue
            flipped = _flips(board, r, c, player)
            if flipped:
                moves[(r, c)] = flipped
    return moves


def _apply_move(
    board: list[list[str]], r: int, c: int, player: str
) -> list[tuple[int, int]]:
    """Place ``player`` at (r, c) and flip every flanked disc. Returns the flipped cells."""
    flipped = _flips(board, r, c, player)
    board[r][c] = player
    for fr, fc in flipped:
        board[fr][fc] = player
    return flipped


def _count(board: list[list[str]]) -> tuple[int, int]:
    black = sum(row.count(_BLACK) for row in board)
    white = sum(row.count(_WHITE) for row in board)
    return black, white


def _is_full(board: list[list[str]]) -> bool:
    return all(cell != _EMPTY for row in board for cell in row)


def _render_board(board: list[list[str]]) -> str:
    lines = ["    a b c d e f"]
    for r in range(_SIZE):
        cells = " ".join(_GLYPH[board[r][c]] for c in range(_SIZE))
        lines.append(f" {r + 1}  {cells}")
    return "\n".join(lines)


class ReversiScenario(InteractiveScenario):
    """Play 6x6 Reversi against a deterministic greedy CPU (no real LLM — yet)."""

    name = "reversi"
    i18n_key = "reversi"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        # The opponent is a deterministic simple AI (greedy max-flips with a
        # seeded RNG tie-break). LLM / human-vs-LLM play is a future session.
        self._rng = random.Random(seed)

    def _audit(self, payload: dict[str, object]) -> Event:
        return Event(kind=EventKind.AUDIT, source_id="reversi", payload=payload)

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.reversi.intro", title_key="scenario.reversi.intro_title")

        board: list[list[str]] = _initial_board()
        passes = 0

        for _turn in range(_MAX_TURNS):
            # ---- your turn (black) ----------------------------------------
            legal = _legal_moves(board, _BLACK)
            black, white = _count(board)
            status = t("scenario.reversi.status", black=black, white=white)
            yield narrate(
                _render_board(board) + "\n" + status,
                title=t("scenario.reversi.turn"),
            )
            if not legal:
                yield narrate_key(
                    "scenario.reversi.pass_human", title_key="scenario.reversi.pass_title"
                )
                yield self._audit(
                    {"event": "reversi.pass", "side": "black", "display": "● pass"}
                )
                passes += 1
                if passes >= 2:
                    break
            else:
                passes = 0
                ranked = sorted(legal.items(), key=lambda kv: (-len(kv[1]), kv[0]))
                ranked = ranked[:_MAX_CHOICES]
                options: list[ChoiceOption] = []
                by_id: dict[str, tuple[int, int]] = {}
                for (r, c), flipped in ranked:
                    coord = _coord(r, c)
                    options.append(
                        ChoiceOption(
                            coord, coord, t("scenario.reversi.move_desc", n=len(flipped))
                        )
                    )
                    by_id[coord] = (r, c)
                default_id = options[0].id  # the highest-flip legal move
                choice = await self.ask(
                    t("scenario.reversi.your_move"), options, default_id=default_id
                )
                r, c = by_id.get(choice, by_id[default_id])
                moved = _apply_move(board, r, c, _BLACK)
                yield self._audit(
                    {
                        "event": "reversi.move",
                        "side": "black",
                        "coord": _coord(r, c),
                        "flips": len(moved),
                        "display": f"● {_coord(r, c)} (+{len(moved)})",
                    }
                )
            if _is_full(board):
                break

            # ---- CPU turn (white) -----------------------------------------
            legal_w = _legal_moves(board, _WHITE)
            if not legal_w:
                yield narrate_key(
                    "scenario.reversi.pass_cpu", title_key="scenario.reversi.pass_title"
                )
                yield self._audit(
                    {"event": "reversi.pass", "side": "white", "display": "○ pass"}
                )
                passes += 1
                if passes >= 2:
                    break
            else:
                passes = 0
                best_n = max(len(v) for v in legal_w.values())
                best_moves = sorted(m for m, v in legal_w.items() if len(v) == best_n)
                br, bc = self._rng.choice(best_moves)
                moved = _apply_move(board, br, bc, _WHITE)
                yield self._audit(
                    {
                        "event": "reversi.move",
                        "side": "white",
                        "coord": _coord(br, bc),
                        "flips": len(moved),
                        "display": f"○ {_coord(br, bc)} (+{len(moved)})",
                    }
                )
                yield narrate_key(
                    "scenario.reversi.cpu_move",
                    title_key="scenario.reversi.cpu_title",
                    coord=_coord(br, bc),
                    n=len(moved),
                )
            if _is_full(board):
                break

        # ---- final position + result --------------------------------------
        black, white = _count(board)
        yield narrate(
            _render_board(board) + "\n"
            + t("scenario.reversi.status", black=black, white=white),
            title=t("scenario.reversi.turn"),
        )
        yield self._audit(
            {
                "event": "reversi.game_end",
                "black": black,
                "white": white,
                "display": f"● {black} : {white} ○",
            }
        )
        if black > white:
            result_key = "scenario.reversi.result_win"
        elif black < white:
            result_key = "scenario.reversi.result_lose"
        else:
            result_key = "scenario.reversi.result_draw"
        yield narrate_key(
            result_key,
            title_key="scenario.reversi.result_title",
            black=black,
            white=white,
        )


__all__ = ["ReversiScenario"]
