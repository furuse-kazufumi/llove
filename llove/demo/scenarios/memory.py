"""memory — an interactive Concentration / Memory card-game cartridge.

A small grid of face-down cards hides a handful of pairs. On *your* turn you
flip two cards: a match is yours and you go again, a miss flips them back. You
play against a deterministic CPU with **imperfect memory** — it only recalls
some of the cards it has seen, so out-remembering it is the whole game. Most
pairs wins.

The CPU here is a simple, seedable rule-based opponent (``self._rng``), **not a
real LLM**. Wiring a real LLM (or two LLMs) in as the opponent — so the demo
doubles as a memory/recall benchmark for a model — is the planned next-session
upgrade; the Event payloads already carry enough board state for it.

Runs fully offline and deterministically (``--seed``). With no asker wired
(CI / ``--list`` / a unit test), :meth:`ask` returns the default tile, so the
flow still completes and terminates on its own.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption


def _new_board(rng: random.Random, pairs: int) -> list[str]:
    """Build a shuffled deck of ``pairs`` symbols, each appearing twice."""
    deck = [chr(ord("A") + i) for i in range(pairs)] * 2
    rng.shuffle(deck)
    return deck


def _face_down(
    board: list[str], matched: set[int], exclude: tuple[int, ...] = ()
) -> list[int]:
    """Positions still face down (not matched, not in ``exclude``), in order."""
    return [i for i in range(len(board)) if i not in matched and i not in exclude]


def _known_pair(cpu_mem: dict[int, str], face_down: list[int]) -> tuple[int, int] | None:
    """Return two face-down positions the CPU remembers share a value, else None."""
    seen: dict[str, int] = {}
    for pos in face_down:
        value = cpu_mem.get(pos)
        if value is None:
            continue
        if value in seen:
            return seen[value], pos
        seen[value] = pos
    return None


def _render_board(
    board: list[str],
    matched: set[int],
    owners: dict[int, str],
    revealed: set[int],
) -> str:
    """Render the grid: matched cards show their value + owner, face-down show id."""
    cells: list[str] = []
    for i, value in enumerate(board):
        if i in matched:
            mark = "*" if owners.get(i) == "human" else "+"
            cell = f"[{value}{mark}]"
        elif i in revealed:
            cell = f"({value})"
        else:
            cell = f"{i + 1}"
        cells.append(cell.center(5))
    cols = 4
    rows = [" ".join(cells[r : r + cols]) for r in range(0, len(cells), cols)]
    return "\n".join(rows)


class MemoryScenario(InteractiveScenario):
    """Concentration / Memory: flip two cards a turn, beat a forgetful CPU."""

    name = "memory"
    i18n_key = "memory"
    default_pause = 0.1

    _PAIRS = 4  # 8 cards on a 2x4 grid → first-flip choices stay ≤ 9
    _MAX_TURNS = 40  # hard cap so a headless run always terminates
    _MEMORY_PROB = 0.7  # chance the CPU remembers any card it sees (imperfect)

    _last_matched: bool = False

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _remember(self, cpu_mem: dict[int, str], pos: int, value: str) -> None:
        """Imperfect memory: record a seen card only some of the time."""
        if self._rng.random() < self._MEMORY_PROB:
            cpu_mem[pos] = value

    def _board_event(
        self,
        board: list[str],
        matched: set[int],
        owners: dict[int, str],
        scores: dict[str, int],
        turn: int,
        mover: str,
    ) -> Event:
        body = _render_board(board, matched, owners, set())
        legend = f"You {scores['human']} — CPU {scores['cpu']}  (turn {turn}, {mover})"
        return narrate(f"{body}\n{legend}", title=t("scenario.memory.turn"))

    def _tile_options(self, board: list[str], positions: list[int]) -> list[ChoiceOption]:
        return [
            ChoiceOption(str(p), t("scenario.memory.tile", n=p + 1))
            for p in positions
        ]

    def _flip_audit(self, pos: int, value: str, by: str) -> Event:
        return Event(
            kind=EventKind.AUDIT,
            source_id="memory",
            payload={
                "event": "memory.flip",
                "by": by,
                "pos": pos,
                "value": value,
                "display": f"{by} flips card {pos + 1} = {value}",
            },
        )

    def _resolve_flip(
        self,
        board: list[str],
        matched: set[int],
        owners: dict[int, str],
        scores: dict[str, int],
        first: int,
        second: int,
        by: str,
    ) -> Event:
        """Apply a two-card flip: record a match or report the miss. Returns AUDIT."""
        if board[first] == board[second]:
            matched.add(first)
            matched.add(second)
            owners[first] = by
            owners[second] = by
            scores[by] += 1
            self._last_matched = True
            return Event(
                kind=EventKind.AUDIT,
                source_id="memory",
                payload={
                    "event": "memory.match",
                    "by": by,
                    "value": board[first],
                    "positions": [first, second],
                    "display": f"{by} matches {board[first]} "
                    f"({first + 1} & {second + 1})",
                },
            )
        self._last_matched = False
        return Event(
            kind=EventKind.AUDIT,
            source_id="memory",
            payload={
                "event": "memory.miss",
                "by": by,
                "positions": [first, second],
                "display": f"{by} misses ({first + 1} & {second + 1}) — flipped back",
            },
        )

    # ------------------------------------------------------------------ plies
    async def _human_ply(
        self,
        board: list[str],
        matched: set[int],
        cpu_mem: dict[int, str],
        owners: dict[int, str],
        scores: dict[str, int],
    ) -> AsyncIterator[Event]:
        fd = _face_down(board, matched)
        opts1 = self._tile_options(board, fd)
        first = int(
            await self.ask(t("scenario.memory.your_move"), opts1, default_id=str(fd[0]))
        )
        self._remember(cpu_mem, first, board[first])
        yield narrate(
            _render_board(board, matched, owners, {first}),
            title=t("scenario.memory.turn"),
        )
        yield self._flip_audit(first, board[first], "human")

        fd2 = _face_down(board, matched, exclude=(first,))
        opts2 = self._tile_options(board, fd2)
        second = int(
            await self.ask(t("scenario.memory.your_move"), opts2, default_id=str(fd2[0]))
        )
        self._remember(cpu_mem, second, board[second])
        yield narrate(
            _render_board(board, matched, owners, {first, second}),
            title=t("scenario.memory.turn"),
        )
        yield self._flip_audit(second, board[second], "human")
        yield self._resolve_flip(board, matched, owners, scores, first, second, "human")

    async def _cpu_ply(
        self,
        board: list[str],
        matched: set[int],
        cpu_mem: dict[int, str],
        owners: dict[int, str],
        scores: dict[str, int],
    ) -> AsyncIterator[Event]:
        fd = _face_down(board, matched)
        pair = _known_pair(cpu_mem, fd)
        if pair is not None:
            first, second = pair
        else:
            unknown = [p for p in fd if p not in cpu_mem]
            first = self._rng.choice(unknown or fd)
            value = board[first]
            second = next(
                (p for p in fd if p != first and cpu_mem.get(p) == value), -1
            )
            if second == -1:
                rest = [p for p in fd if p != first]
                unknown2 = [p for p in rest if p not in cpu_mem]
                second = self._rng.choice(unknown2 or rest)

        self._remember(cpu_mem, first, board[first])
        yield narrate(
            _render_board(board, matched, owners, {first}),
            title=t("scenario.memory.turn"),
        )
        yield self._flip_audit(first, board[first], "cpu")
        self._remember(cpu_mem, second, board[second])
        yield narrate(
            _render_board(board, matched, owners, {first, second}),
            title=t("scenario.memory.turn"),
        )
        yield self._flip_audit(second, board[second], "cpu")
        yield self._resolve_flip(board, matched, owners, scores, first, second, "cpu")

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.memory.intro", title_key="scenario.memory.intro_title")

        board = _new_board(self._rng, self._PAIRS)
        matched: set[int] = set()
        cpu_mem: dict[int, str] = {}
        owners: dict[int, str] = {}
        scores: dict[str, int] = {"human": 0, "cpu": 0}
        total = self._PAIRS * 2
        mover = "human"
        turn = 0

        while len(matched) < total and turn < self._MAX_TURNS:
            turn += 1
            yield self._board_event(board, matched, owners, scores, turn, mover)
            if mover == "human":
                async for ev in self._human_ply(board, matched, cpu_mem, owners, scores):
                    yield ev
            else:
                async for ev in self._cpu_ply(board, matched, cpu_mem, owners, scores):
                    yield ev
            # A match earns another go; a miss passes the turn to the opponent.
            if not self._last_matched:
                mover = "cpu" if mover == "human" else "human"

        yield Event(
            kind=EventKind.AUDIT,
            source_id="memory",
            payload={
                "event": "memory.game_end",
                "human": scores["human"],
                "cpu": scores["cpu"],
                "display": f"final: you {scores['human']} — cpu {scores['cpu']}",
            },
        )
        if scores["human"] > scores["cpu"]:
            result = "result_win"
        elif scores["human"] < scores["cpu"]:
            result = "result_lose"
        else:
            result = "result_draw"
        yield narrate_key(
            f"scenario.memory.{result}",
            title_key="scenario.memory.result_title",
            human=scores["human"],
            cpu=scores["cpu"],
        )


__all__ = ["MemoryScenario"]
