"""mancala — an interactive Mancala (Kalah) board-game cartridge.

A two-player sowing game on a 6-pit-per-side board (4 stones per pit, one
store each). On every turn *you* pick one of your non-empty pits and sow its
stones counter-clockwise; if your last stone drops into your own store you take
another turn. When either side runs out of pits the remaining stones are swept
into their owner's store and whoever banked the most wins.

The opponent is a small **deterministic** heuristic (one-ply look-ahead over the
seeded RNG), *not* a real LLM — a genuine model rival is the next session's job.
Like every llove cartridge it runs fully offline.

With no asker wired (CI / ``--list`` / a unit test) every choice resolves to the
deterministic default (the lowest-numbered legal pit), so the game still plays
itself to a finish and emits a result.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

# Board layout (single flat list, counter-clockwise):
#   index 0..5   = human pits (move numbers 1..6)
#   index 6      = human store
#   index 7..12  = CPU pits
#   index 13     = CPU store
_HUMAN_PITS: tuple[int, ...] = (0, 1, 2, 3, 4, 5)
_HUMAN_STORE = 6
_CPU_PITS: tuple[int, ...] = (7, 8, 9, 10, 11, 12)
_CPU_STORE = 13
_INITIAL_STONES = 4
_BOARD_SIZE = 14
# Hard cap on half-moves so the loop is guaranteed to terminate even if a future
# rule tweak ever broke natural termination. A 48-stone Kalah game ends in far
# fewer moves than this.
_MAX_TURNS = 400


def _new_board() -> list[int]:
    board = [_INITIAL_STONES] * 6 + [0] + [_INITIAL_STONES] * 6 + [0]
    return board


def _legal_pits(board: list[int], pits: tuple[int, ...]) -> list[int]:
    return [i for i in pits if board[i] > 0]


def _sow(board: list[int], start: int, player: int) -> int:
    """Sow the stones from ``start`` counter-clockwise. Returns the last index.

    The opponent's store is skipped, per Kalah rules. Mutates ``board``.
    """
    stones = board[start]
    board[start] = 0
    skip = _CPU_STORE if player == 0 else _HUMAN_STORE
    idx = start
    while stones > 0:
        idx = (idx + 1) % _BOARD_SIZE
        if idx == skip:
            continue
        board[idx] += 1
        stones -= 1
    return idx


def _apply_capture(board: list[int], last: int, player: int) -> int:
    """Kalah capture: a last stone landing in your own previously-empty pit
    sweeps it plus the opposite pit into your store. Returns the count captured.
    """
    own_pits = _HUMAN_PITS if player == 0 else _CPU_PITS
    own_store = _HUMAN_STORE if player == 0 else _CPU_STORE
    if last not in own_pits or board[last] != 1:
        return 0
    opposite = 12 - last
    if board[opposite] == 0:
        return 0
    captured = board[opposite] + 1
    board[own_store] += captured
    board[opposite] = 0
    board[last] = 0
    return captured


def _game_over(board: list[int]) -> bool:
    return all(board[i] == 0 for i in _HUMAN_PITS) or all(board[i] == 0 for i in _CPU_PITS)


def _sweep(board: list[int]) -> None:
    """End of game: rake each side's leftover stones into its own store."""
    for i in _HUMAN_PITS:
        board[_HUMAN_STORE] += board[i]
        board[i] = 0
    for i in _CPU_PITS:
        board[_CPU_STORE] += board[i]
        board[i] = 0


def _render_board(board: list[int]) -> str:
    """Plain-text board snapshot (dynamic string — not routed through i18n)."""
    cpu = [board[i] for i in range(12, 6, -1)]
    human = [board[i] for i in range(0, 6)]
    cpu_row = "  ".join(f"{n:>2}" for n in cpu)
    human_row = "  ".join(f"{n:>2}" for n in human)
    move_row = "  ".join(f"{i:>2}" for i in range(1, 7))
    return (
        f"        CPU (opponent)   store: {board[_CPU_STORE]:>2}\n"
        f"   +------------------------------+\n"
        f"   |  {cpu_row}  |\n"
        f"   |  {human_row}  |\n"
        f"   +------------------------------+\n"
        f"   move:  {move_row}\n"
        f"        YOU (human)      store: {board[_HUMAN_STORE]:>2}"
    )


class MancalaScenario(InteractiveScenario):
    """Interactive Mancala (Kalah). You vs. a deterministic heuristic CPU."""

    name = "mancala"
    i18n_key = "mancala"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _cpu_choose(self, board: list[int]) -> int | None:
        """One-ply heuristic: maximise store gain, bonus for an extra turn."""
        legal = _legal_pits(board, _CPU_PITS)
        if not legal:
            return None
        scored: list[tuple[int, int]] = []
        for i in legal:
            probe = board[:]
            last = _sow(probe, i, 1)
            _apply_capture(probe, last, 1)
            extra = 3 if last == _CPU_STORE else 0
            gain = probe[_CPU_STORE] - board[_CPU_STORE]
            scored.append((gain + extra, i))
        best = max(score for score, _ in scored)
        top = [i for score, i in scored if score == best]
        return self._rng.choice(top)

    def _move_audit(self, side: str, pit_no: int, stones: int, captured: int) -> Event:
        who = "YOU" if side == "human" else "CPU"
        return Event(
            kind=EventKind.AUDIT,
            source_id="mancala",
            payload={
                "event": "mancala.move",
                "side": side,
                "pit": pit_no,
                "stones": stones,
                "captured": captured,
                "display": f"{who} sow pit {pit_no} ({stones})"
                + (f" capture x{captured}" if captured else ""),
            },
        )

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.mancala.intro", title_key="scenario.mancala.intro_title")

        board = _new_board()
        yield narrate(_render_board(board), title=t("scenario.mancala.turn"))

        human_turn = True
        for _ in range(_MAX_TURNS):
            if _game_over(board):
                break

            if human_turn:
                legal = _legal_pits(board, _HUMAN_PITS)
                if not legal:
                    break
                options = [
                    ChoiceOption(
                        f"pit{i}",
                        t("scenario.mancala.move_label", pit=i + 1, stones=board[i]),
                    )
                    for i in legal
                ]
                default_id = f"pit{legal[0]}"
                choice = await self.ask(
                    t("scenario.mancala.your_move"), options, default_id=default_id
                )
                pit = _legal_pits(board, _HUMAN_PITS)[0]
                try:
                    candidate = int(choice.removeprefix("pit"))
                except ValueError:
                    candidate = pit
                if candidate in legal:
                    pit = candidate

                stones = board[pit]
                last = _sow(board, pit, 0)
                captured = _apply_capture(board, last, 0)
                yield self._move_audit("human", pit + 1, stones, captured)
                if captured:
                    yield narrate(
                        t("scenario.mancala.capture", stones=captured),
                        title=t("scenario.mancala.turn"),
                    )
                yield narrate(_render_board(board), title=t("scenario.mancala.turn"))

                if _game_over(board):
                    break
                if last == _HUMAN_STORE:
                    yield narrate(
                        t("scenario.mancala.extra_turn"), title=t("scenario.mancala.turn")
                    )
                else:
                    human_turn = False
            else:
                cpu_pit = self._cpu_choose(board)
                if cpu_pit is None:
                    break
                stones = board[cpu_pit]
                last = _sow(board, cpu_pit, 1)
                captured = _apply_capture(board, last, 1)
                yield self._move_audit("cpu", cpu_pit - 6, stones, captured)
                yield narrate(
                    t("scenario.mancala.cpu_move", pit=cpu_pit - 6, stones=stones)
                    + "\n"
                    + _render_board(board),
                    title=t("scenario.mancala.cpu_turn"),
                )
                if captured:
                    yield narrate(
                        t("scenario.mancala.capture", stones=captured),
                        title=t("scenario.mancala.cpu_turn"),
                    )
                if _game_over(board):
                    break
                if last == _CPU_STORE:
                    yield narrate(
                        t("scenario.mancala.extra_turn"),
                        title=t("scenario.mancala.cpu_turn"),
                    )
                else:
                    human_turn = True

        _sweep(board)
        you = board[_HUMAN_STORE]
        cpu = board[_CPU_STORE]
        yield narrate(_render_board(board), title=t("scenario.mancala.result_title"))

        if you > cpu:
            result_key = "scenario.mancala.result_win"
        elif you < cpu:
            result_key = "scenario.mancala.result_lose"
        else:
            result_key = "scenario.mancala.result_draw"
        yield narrate_key(
            result_key, title_key="scenario.mancala.result_title", you=you, cpu=cpu
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="mancala",
            payload={
                "event": "mancala.game_end",
                "human": you,
                "cpu": cpu,
                "display": f"Final — YOU {you}, CPU {cpu}",
            },
        )


__all__ = ["MancalaScenario"]
