"""blackjack — an interactive Blackjack (21) cartridge (you vs the dealer).

You are dealt two cards and play against a dealer. On every turn you *choose*
to **hit** (draw another card) or **stand** (keep your hand). Aces count as 1
or 11 (whichever keeps you alive), face cards count as 10. Go over 21 and you
bust and lose. When you stand, the dealer reveals the hole card and hits until
reaching 17 — then the closer-to-21 hand wins.

The dealer is a *deterministic* simple policy (``self._rng`` only shuffles the
deck; the dealer always hits below 17). It is **not** a real LLM opponent —
wiring an LLM player in is a future-session task (cf. the shogi MVP2 plan).

Runs fully offline. With no asker wired (CI / ``--list``), the deterministic
default path is ``stand`` on the opening hand, so the dealer plays out and the
hand always reaches a verdict.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_RANKS: list[str] = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_SUITS: list[str] = ["S", "H", "D", "C"]
_VALUES: dict[str, int] = {
    "A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10,
}
_DEALER_STANDS_AT = 17
_BLACKJACK = 21
_MAX_TURNS = 12  # hard cap so the loop always terminates (deck never runs dry)

Card = tuple[str, str]  # (rank, suit), e.g. ("A", "S")


def _hand_value(hand: list[Card]) -> int:
    """Best blackjack total: aces count as 11, demoted to 1 to avoid a bust."""
    total = sum(_VALUES[rank] for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == "A")
    while total > _BLACKJACK and aces > 0:
        total -= 10
        aces -= 1
    return total


def _fmt_hand(hand: list[Card]) -> str:
    return " ".join(f"{rank}{suit}" for rank, suit in hand)


def _fmt_card(card: Card) -> str:
    return f"{card[0]}{card[1]}"


class BlackjackScenario(InteractiveScenario):
    """Play Blackjack (21) against a deterministic dealer; you steer hit/stand."""

    name = "blackjack"
    i18n_key = "blackjack"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    def _new_deck(self) -> list[Card]:
        deck: list[Card] = [(rank, suit) for suit in _SUITS for rank in _RANKS]
        self._rng.shuffle(deck)
        return deck

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.blackjack.intro", title_key="scenario.blackjack.intro_title"
        )

        deck = self._new_deck()
        player: list[Card] = [deck.pop(), deck.pop()]
        dealer: list[Card] = [deck.pop(), deck.pop()]

        yield Event(
            kind=EventKind.AUDIT,
            source_id="blackjack",
            payload={
                "event": "deal",
                "display": t(
                    "scenario.blackjack.deal",
                    player=_fmt_hand(player),
                    dealer_up=_fmt_card(dealer[0]),
                ),
            },
        )

        # ---- Player's turn: hit/stand until 21, bust, stand, or the cap. ----
        player_bust = False
        for _ in range(_MAX_TURNS):
            pv = _hand_value(player)
            yield narrate(
                t(
                    "scenario.blackjack.state",
                    player=_fmt_hand(player),
                    player_total=pv,
                    dealer_up=_fmt_card(dealer[0]),
                ),
                title=t("scenario.blackjack.turn"),
            )
            if pv >= _BLACKJACK:
                break  # 21 (or already bust) — nothing left to decide.

            opts = [
                ChoiceOption(
                    "hit",
                    t("scenario.blackjack.hit_label"),
                    t("scenario.blackjack.hit_desc"),
                ),
                ChoiceOption(
                    "stand",
                    t("scenario.blackjack.stand_label"),
                    t("scenario.blackjack.stand_desc"),
                ),
            ]
            move = await self.ask(
                t("scenario.blackjack.your_move"), opts, default_id="stand"
            )

            if move == "hit":
                card = deck.pop()
                player.append(card)
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id="blackjack",
                    payload={
                        "event": "player_hit",
                        "display": t(
                            "scenario.blackjack.player_hit",
                            card=_fmt_card(card),
                            total=_hand_value(player),
                        ),
                    },
                )
                if _hand_value(player) > _BLACKJACK:
                    player_bust = True
                    break
            else:  # stand (default branch)
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id="blackjack",
                    payload={
                        "event": "player_stand",
                        "display": t(
                            "scenario.blackjack.player_stand",
                            total=_hand_value(player),
                        ),
                    },
                )
                break

        # ---- Dealer's turn: only if the player is still alive. ----
        if not player_bust:
            for _ in range(_MAX_TURNS):
                dv = _hand_value(dealer)
                yield narrate(
                    t(
                        "scenario.blackjack.dealer_state",
                        dealer=_fmt_hand(dealer),
                        dealer_total=dv,
                    ),
                    title=t("scenario.blackjack.turn"),
                )
                if dv >= _DEALER_STANDS_AT:
                    break
                card = deck.pop()
                dealer.append(card)
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id="blackjack",
                    payload={
                        "event": "dealer_hit",
                        "display": t(
                            "scenario.blackjack.dealer_hit",
                            card=_fmt_card(card),
                            total=_hand_value(dealer),
                        ),
                    },
                )

        # ---- Verdict. ----
        pv = _hand_value(player)
        dv = _hand_value(dealer)
        if player_bust or pv > _BLACKJACK:
            result = "lose"
        elif dv > _BLACKJACK or pv > dv:
            result = "win"
        elif pv < dv:
            result = "lose"
        else:
            result = "draw"

        yield Event(
            kind=EventKind.AUDIT,
            source_id="blackjack",
            payload={
                "event": "result",
                "result": result,
                "player_total": pv,
                "dealer_total": dv,
                "display": t(
                    f"scenario.blackjack.result_{result}",
                    player_total=pv,
                    dealer_total=dv,
                ),
            },
        )
        yield narrate_key(
            f"scenario.blackjack.result_{result}",
            title_key="scenario.blackjack.result_title",
            player_total=pv,
            dealer_total=dv,
        )


__all__ = ["BlackjackScenario"]
