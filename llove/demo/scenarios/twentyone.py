"""twentyone — the 21 counting game (a Nim-variant cartridge).

Starting from 0, you and the CPU take turns adding **1, 2, or 3** to a shared
running count. Whoever lands on **exactly 21 wins**. A move that would overshoot
21 is illegal, so near the end only the smaller adds stay on the menu.

The CPU plays the classic *multiples-of-four* optimal strategy: it tries to leave
the count on one of the control numbers ``1, 5, 9, 13, 17`` (each ``== 1 (mod 4)``)
from which 21 is forced. It is **not** a real LLM — just a deterministic
``random.Random``-seeded policy with the occasional **slip** so a sharp human can
beat it. (A genuine LLM-vs-human opponent is the future-session upgrade; the
Event payloads already carry enough state — count, last add, legal moves — for
that swap and for an external viewer.)

Runs fully offline and deterministically under a fixed seed. With no asker wired
(CI / ``--list`` / a unit test) every human turn takes the ``+1`` default, so the
generator still terminates and emits a result narration.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_GOAL = 21
_CONTROL_MOD = 4  # control numbers are count == 1 (mod 4): 1, 5, 9, 13, 17


class TwentyOneScenario(InteractiveScenario):
    name = "twentyone"
    i18n_key = "twentyone"
    default_pause = 0.1

    # Hard turn cap — each full round adds at least 2 to the count, so the
    # game always ends in <= 11 rounds; the cap is a belt-and-braces guard
    # that guarantees the generator terminates even if the rules ever change.
    _MAX_TURNS = 21

    def __init__(self, *, seed: int = 42) -> None:
        self._rng: random.Random = random.Random(seed)
        # Probability the CPU fluffs an available optimal move (gives the
        # human a real chance to win). Deterministic under the seed.
        self._slip: float = 0.15

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _legal(count: int) -> list[int]:
        """Adds that keep the count from overshooting 21 (exactly-21 wins)."""
        return [a for a in (1, 2, 3) if count + a <= _GOAL]

    @staticmethod
    def _board(count: int, legal: list[int]) -> str:
        bar = "#" * count + "." * (_GOAL - count)
        moves = ", ".join(f"+{a}" for a in legal)
        return f"Count: {count} / {_GOAL}\n[{bar}]\nLegal: {moves}"

    def _cpu_move(self, count: int) -> int:
        """Multiples-of-four optimal policy with seeded slips.

        The CPU wants to leave the count ``== 1 (mod 4)``. The add that does so
        is ``(1 - count) % 4``; when that is ``0`` the human already holds a
        control number, so the CPU is lost and just plays on.
        """
        legal = self._legal(count)
        optimal = (1 - count) % _CONTROL_MOD
        if optimal in legal and self._rng.random() >= self._slip:
            return optimal
        return self._rng.choice(legal)

    def _audit(self, who: str, add: int, count: int) -> Event:
        return Event(
            kind=EventKind.AUDIT,
            source_id="twentyone",
            payload={
                "event": "twentyone.move",
                "actor": who,
                "add": add,
                "count": count,
                "display": f"{who}: +{add} -> {count}",
            },
        )

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.twentyone.intro",
            title_key="scenario.twentyone.intro_title",
        )

        count = 0
        winner: str | None = None

        for _ in range(self._MAX_TURNS):
            if count >= _GOAL:
                break

            # --- human turn ------------------------------------------------
            legal = self._legal(count)
            yield narrate(
                self._board(count, legal),
                title=t("scenario.twentyone.turn"),
            )
            opts = [
                ChoiceOption(
                    str(a),
                    t(f"scenario.twentyone.move_{a}_label"),
                    t(f"scenario.twentyone.move_{a}_desc"),
                )
                for a in legal
            ]
            choice = await self.ask(
                t("scenario.twentyone.your_move"), opts, default_id="1"
            )
            add = int(choice) if choice in {str(a) for a in legal} else legal[0]
            count += add
            yield self._audit("You", add, count)
            if count >= _GOAL:
                winner = "human"
                break

            # --- CPU turn --------------------------------------------------
            k = self._cpu_move(count)
            count += k
            yield self._audit("CPU", k, count)
            yield narrate(
                f"Count: {count} / {_GOAL}\nCPU played +{k}.",
                title=t("scenario.twentyone.cpu_turn"),
            )
            if count >= _GOAL:
                winner = "cpu"
                break

        result_key = (
            "scenario.twentyone.result_win"
            if winner == "human"
            else "scenario.twentyone.result_lose"
        )
        yield narrate_key(result_key, title_key="scenario.twentyone.result_title")


__all__ = ["TwentyOneScenario"]
