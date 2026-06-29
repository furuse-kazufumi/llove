"""highlow — a Higher-Lower streak cartridge (card game, interactive).

A card is shown each turn; you call whether the **next** card is *higher* or
*lower*. Ties lose. You and a deterministic CPU each build a parallel streak
across a fixed number of cards, and the longest streak wins. Like every llove
demo it runs fully offline with synthetic data — the new part is that you steer
each call from the choice palette.

The opponent is a tiny deterministic policy (guess relative to the deck
midpoint), **not** a real LLM. An LLM-vs-human card duel is future work
(next session). With no asker wired (CI / ``--list`` / unit tests) the
deterministic default branch always calls ``higher``, so playback stays
reproducible and the run always reaches a result.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator
from typing import NamedTuple

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_MIN_RANK = 2
_MAX_RANK = 14  # 11=J 12=Q 13=K 14=A
_MAX_TURNS = 10  # hard cap on rounds — guarantees termination
_MIDPOINT = 8  # below → next card likely higher; above → likely lower
_RANK_LABELS = {11: "J", 12: "Q", 13: "K", 14: "A"}
_SUITS = ("♠", "♥", "♦", "♣")  # ♠ ♥ ♦ ♣


class _Card(NamedTuple):
    rank: int
    suit: str


class HighLowScenario(InteractiveScenario):
    """Higher-Lower streak duel against a deterministic CPU (card game)."""

    name = "highlow"
    i18n_key = "highlow"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _draw(self) -> _Card:
        return _Card(self._rng.randint(_MIN_RANK, _MAX_RANK), self._rng.choice(_SUITS))

    @staticmethod
    def _rank_label(rank: int) -> str:
        return _RANK_LABELS.get(rank, str(rank))

    def _card_str(self, card: _Card) -> str:
        return f"{self._rank_label(card.rank)}{card.suit}"

    def _card_art(self, card: _Card) -> str:
        top = self._rank_label(card.rank).ljust(2)
        bot = self._rank_label(card.rank).rjust(2)
        return (
            "┌─────┐\n"
            f"│{top}   │\n"
            f"│  {card.suit}  │\n"
            f"│   {bot}│\n"
            "└─────┘"
        )

    @staticmethod
    def _beats(move: str, current: int, nxt: int) -> bool:
        """True if the guess wins. Ties always lose; default move is higher."""
        if nxt == current:
            return False
        if move == "lower":
            return nxt < current
        return nxt > current

    @staticmethod
    def _cpu_move(current: int) -> str:
        """Deterministic opponent: bet toward the deck midpoint."""
        return "higher" if current <= _MIDPOINT else "lower"

    def _board(
        self,
        card: _Card,
        *,
        turn: int,
        h_cur: int,
        h_best: int,
        c_best: int,
    ) -> str:
        return (
            f"{self._card_art(card)}\n"
            f"Turn {turn}/{_MAX_TURNS}  ·  "
            f"your streak {h_cur} (best {h_best})  ·  CPU best {c_best}"
        )

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.highlow.intro",
            title_key="scenario.highlow.intro_title",
            rounds=_MAX_TURNS,
        )

        opts = [
            ChoiceOption(
                "higher",
                t("scenario.highlow.move_higher"),
                t("scenario.highlow.move_higher_desc"),
            ),
            ChoiceOption(
                "lower",
                t("scenario.highlow.move_lower"),
                t("scenario.highlow.move_lower_desc"),
            ),
        ]

        human_card = self._draw()
        cpu_card = self._draw()
        h_cur = h_best = 0
        c_cur = c_best = 0

        for turn in range(1, _MAX_TURNS + 1):
            yield narrate(
                self._board(
                    human_card, turn=turn, h_cur=h_cur, h_best=h_best, c_best=c_best
                ),
                title=t("scenario.highlow.turn"),
            )

            move = await self.ask(
                t("scenario.highlow.your_move"), opts, default_id="higher"
            )
            nxt = self._draw()
            correct = self._beats(move, human_card.rank, nxt.rank)
            h_cur = h_cur + 1 if correct else 0
            h_best = max(h_best, h_cur)
            mark = "✓" if correct else "✗"
            yield Event(
                kind=EventKind.AUDIT,
                source_id="highlow",
                payload={
                    "event": "highlow.player_guess",
                    "guess": move,
                    "from": self._card_str(human_card),
                    "to": self._card_str(nxt),
                    "correct": correct,
                    "streak": h_cur,
                    "display": (
                        f"You {move}: {self._card_str(human_card)} → "
                        f"{self._card_str(nxt)} {mark} streak {h_cur}"
                    ),
                },
            )
            human_card = nxt

            cpu_move = self._cpu_move(cpu_card.rank)
            cpu_nxt = self._draw()
            cpu_ok = self._beats(cpu_move, cpu_card.rank, cpu_nxt.rank)
            c_cur = c_cur + 1 if cpu_ok else 0
            c_best = max(c_best, c_cur)
            cpu_mark = "✓" if cpu_ok else "✗"
            yield Event(
                kind=EventKind.AUDIT,
                source_id="highlow",
                payload={
                    "event": "highlow.cpu_guess",
                    "guess": cpu_move,
                    "from": self._card_str(cpu_card),
                    "to": self._card_str(cpu_nxt),
                    "correct": cpu_ok,
                    "streak": c_cur,
                    "display": (
                        f"CPU {cpu_move}: {self._card_str(cpu_card)} → "
                        f"{self._card_str(cpu_nxt)} {cpu_mark} streak {c_cur}"
                    ),
                },
            )
            cpu_card = cpu_nxt

        if h_best > c_best:
            result = "result_win"
        elif h_best < c_best:
            result = "result_lose"
        else:
            result = "result_draw"
        yield narrate_key(
            f"scenario.highlow.{result}",
            title_key="scenario.highlow.result_title",
            you=h_best,
            cpu=c_best,
        )


__all__ = ["HighLowScenario"]
