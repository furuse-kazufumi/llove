"""war - a simplified *War* card-game cartridge (interactive, branching).

Each round both players flip the top card of their pile; the higher rank wins
both cards (placed at the bottom of the winner's pile). On a **tie** llove stops
and asks *you* how to settle it:

    war   -> both ante three cards face-down + one face-up; the higher up-card
             takes the whole pot (the branching decision-point).
    peace -> split the pot; each player simply takes their own card back.

The deck is small and fixed (ranks 2-9, two of each = 16 cards) and the game is
hard-capped at ``_MAX_TURNS`` rounds, so every run terminates. Whoever holds
more cards at the cap (or when an opponent runs out) wins.

The opponent is a **deterministic toy AI**: it has no policy of its own - its
plays are simply the order of its shuffled pile (a seeded ``random.Random``).
This is *not* a real LLM. Wiring two LLMs to play War against each other (with
an own-card / legality check, like the shogi cartridge's MVP2) is future work.

Runs fully offline. With no asker wired (CI / ``--list``) the deterministic
default path is ``flip`` every round, settling ties by ``war``.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_MAX_TURNS = 40
_HAND = 8  # cards dealt to each player (deck = 2 * _HAND = 16 cards)


class WarScenario(InteractiveScenario):
    name = "war"
    i18n_key = "war"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        # The opponent is deterministic: the seed fixes the shuffle, which *is*
        # its whole "strategy". Real LLM-vs-LLM play is a future upgrade.
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _audit(self, event: str, display: str) -> Event:
        return Event(
            kind=EventKind.AUDIT,
            source_id="war",
            payload={"event": event, "display": display},
        )

    def _deal(self) -> tuple[list[int], list[int]]:
        """Build the small fixed deck, shuffle it, and deal 8 cards each."""
        deck = list(range(2, 2 + _HAND)) * 2
        self._rng.shuffle(deck)
        return deck[0::2], deck[1::2]

    def _resolve_war(self, you: list[int], opp: list[int], pot: list[int]) -> str:
        """Settle a tie by 'war': ante up to 3 down-cards, then one up-card.

        Mutates ``you`` / ``opp`` / ``pot`` in place and returns the winner key
        (``"you"`` / ``"opp"`` / ``"split"``). There is no recursion, so a war
        always resolves in a bounded number of steps.
        """
        for _ in range(3):
            if you:
                pot.append(you.pop(0))
            if opp:
                pot.append(opp.pop(0))
        you_up = you.pop(0) if you else None
        opp_up = opp.pop(0) if opp else None
        if you_up is not None:
            pot.append(you_up)
        if opp_up is not None:
            pot.append(opp_up)
        if you_up is None and opp_up is None:
            return "split"
        if opp_up is None or (you_up is not None and you_up > opp_up):
            you.extend(pot)
            return "you"
        if you_up is None or opp_up > you_up:
            opp.extend(pot)
            return "opp"
        # A second tie: award the pot to whoever still holds more cards.
        if len(you) >= len(opp):
            you.extend(pot)
            return "you"
        opp.extend(pot)
        return "opp"

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.war.intro", title_key="scenario.war.intro_title")

        you, opp = self._deal()
        turn_title = t("scenario.war.turn")

        for turn in range(1, _MAX_TURNS + 1):
            # Hard guarantees of termination: empty hand -> stop; otherwise the
            # ``range(_MAX_TURNS)`` cap forces a break no matter what.
            if not you or not opp:
                break

            # State of play (dynamic board string - no i18n key needed).
            yield narrate(
                f"Round {turn}  -  you: {len(you)} cards   opponent: {len(opp)} cards",
                title=turn_title,
            )

            # Human move: the per-turn choice is to flip the top card.
            flip = [
                ChoiceOption(
                    "flip",
                    t("scenario.war.flip_label"),
                    t("scenario.war.flip_desc"),
                )
            ]
            await self.ask(t("scenario.war.your_move"), flip, default_id="flip")

            you_card = you.pop(0)
            opp_card = opp.pop(0)
            pot = [you_card, opp_card]
            yield narrate(
                f"You flip {you_card}, opponent flips {opp_card}.",
                title=turn_title,
            )
            yield self._audit(
                "war.flip", f"round {turn}: you {you_card} vs opponent {opp_card}"
            )

            if you_card > opp_card:
                you.extend(pot)
                yield self._audit("war.round", f"round {turn}: you win the pot")
            elif opp_card > you_card:
                opp.extend(pot)
                yield self._audit("war.round", f"round {turn}: opponent wins the pot")
            else:
                # Tie - the branching decision-point: war or peace?
                settle = [
                    ChoiceOption(
                        "war",
                        t("scenario.war.war_label"),
                        t("scenario.war.war_desc"),
                    ),
                    ChoiceOption(
                        "peace",
                        t("scenario.war.peace_label"),
                        t("scenario.war.peace_desc"),
                    ),
                ]
                decision = await self.ask(
                    t("scenario.war.tie_prompt"), settle, default_id="war"
                )
                if decision == "peace":
                    you.append(you_card)
                    opp.append(opp_card)
                    msg = f"round {turn}: tie at {you_card} - split the pot"
                    yield self._audit("war.peace", msg)
                else:
                    winner = self._resolve_war(you, opp, pot)
                    msg = f"round {turn}: tie at {you_card} - war won by {winner}"
                    yield self._audit("war.war", msg)

        # Final tally - whoever holds more cards wins.
        if len(you) > len(opp):
            key = "scenario.war.result_win"
        elif len(opp) > len(you):
            key = "scenario.war.result_lose"
        else:
            key = "scenario.war.result_draw"
        yield self._audit(
            "war.game_end", f"final: you {len(you)} - opponent {len(opp)}"
        )
        yield narrate_key(
            key,
            title_key="scenario.war.result_title",
            you=len(you),
            opp=len(opp),
        )


__all__ = ["WarScenario"]
