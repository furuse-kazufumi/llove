"""draw_poker — an interactive five-card-draw cartridge (card game).

A tiny, fully-offline poker match you *steer*. Each round both you and the CPU
are dealt five cards from a freshly shuffled deck. You choose **how many of your
worst cards to discard** (0..3); the engine throws away the weakest ones and
deals you replacements. The CPU does the same with a fixed heuristic. The better
five-card hand wins the round; the player who wins the most rounds wins the
match.

Hand ranking is the standard ladder, capped at four-of-a-kind:
``high-card < pair < two-pair < trips < straight < flush < full-house < quads``.

The opponent is a **deterministic, simple AI** (a draw heuristic over its own
hand) — *not* a real LLM. Wiring two real LLMs into a draw-poker arena (each
reasoning over its hand in natural language) is a planned future session; this
MVP keeps the focus on the TUI fit and a clean, terminating game loop.

With no asker wired (CI / ``--list`` / a unit test), each round falls back to a
deterministic recommended discard, so the whole match always completes.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

# A round is one dealt hand; the match is a fixed, small number of rounds so the
# generator is guaranteed to terminate (hard cap — no open-ended loop).
_MAX_TURNS = 3
_MAX_DISCARD = 3  # you may pitch at most 3 of your worst cards per round

Card = tuple[int, str]  # (rank 2..14, suit glyph)

_SUITS = ("♠", "♥", "♦", "♣")  # spade heart diamond club
_RANK_GLYPH: dict[int, str] = {10: "T", 11: "J", 12: "Q", 13: "K", 14: "A"}


def _fmt_card(card: Card) -> str:
    rank, suit = card
    return f"{_RANK_GLYPH.get(rank, str(rank))}{suit}"


def _fmt_hand(cards: list[Card]) -> str:
    return " ".join(_fmt_card(c) for c in cards)


def _fresh_deck(rng: random.Random) -> list[Card]:
    deck: list[Card] = [(rank, suit) for suit in _SUITS for rank in range(2, 15)]
    rng.shuffle(deck)
    return deck


def _hand_rank(cards: list[Card]) -> tuple[int, tuple[int, ...]]:
    """Return a comparable (category, tiebreakers) key. Higher = better.

    category: 0 high-card, 1 pair, 2 two-pair, 3 trips, 4 straight, 5 flush,
    6 full-house, 7 quads. Straight-flush is intentionally not a separate
    category (the ladder is capped at quads); it scores as a flush.
    """
    ranks = sorted((c[0] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    is_flush = len(set(suits)) == 1
    distinct = sorted(set(ranks), reverse=True)
    is_straight = False
    straight_high = 0
    if len(distinct) == 5:
        if distinct[0] - distinct[4] == 4:
            is_straight, straight_high = True, distinct[0]
        elif distinct == [14, 5, 4, 3, 2]:  # wheel: A-2-3-4-5
            is_straight, straight_high = True, 5
    counts = Counter(ranks)
    by_rank = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    pattern = [c for _, c in by_rank]
    ordered = tuple(r for r, _ in by_rank)
    if pattern == [4, 1]:
        return 7, ordered
    if pattern == [3, 2]:
        return 6, ordered
    if is_flush:
        return 5, tuple(ranks)
    if is_straight:
        return 4, (straight_high,)
    if pattern == [3, 1, 1]:
        return 3, ordered
    if pattern == [2, 2, 1]:
        return 2, ordered
    if pattern == [2, 1, 1, 1]:
        return 1, ordered
    return 0, tuple(ranks)


def _worst_indices(cards: list[Card], n: int) -> list[int]:
    """Indices of the ``n`` weakest cards (singletons first, lowest rank first).

    Cards that form a pair/trip/quad have a higher keep-score, so they survive
    until every singleton is gone — you never break a made combo by accident.
    """
    counts = Counter(c[0] for c in cards)
    order = sorted(range(len(cards)), key=lambda i: (counts[cards[i][0]], cards[i][0]))
    return order[:n]


def _redraw(cards: list[Card], n: int, deck: list[Card]) -> list[Card]:
    """Discard the ``n`` worst cards and deal replacements from ``deck``."""
    drop = set(_worst_indices(cards, n))
    kept = [c for i, c in enumerate(cards) if i not in drop]
    for _ in range(n):
        kept.append(deck.pop())
    return kept


def _recommended_discards(cards: list[Card]) -> int:
    """A sane default draw: keep made combos, pitch the loose low cards."""
    cat, _ = _hand_rank(cards)
    singletons = sum(1 for _, c in Counter(x[0] for x in cards).items() if c == 1)
    if cat >= 4:  # straight / flush / full / quads — stand pat
        return 0
    if cat == 3:  # trips → draw 2
        return min(2, singletons)
    if cat == 2:  # two pair → draw 1
        return min(1, singletons)
    return min(_MAX_DISCARD, singletons)  # pair / high card → draw up to 3


class DrawPokerScenario(InteractiveScenario):
    """A best-of-3 five-card-draw match against a deterministic CPU."""

    name = "draw_poker"
    i18n_key = "draw_poker"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _cat_name(self, cards: list[Card]) -> str:
        cat, _ = _hand_rank(cards)
        return t(f"scenario.draw_poker.cat_{cat}")

    def _deal_narration(self, round_no: int, hand: list[Card]) -> Event:
        text = (
            f"**{t('scenario.draw_poker.label_round', round=round_no, total=_MAX_TURNS)}**\n"
            f"{t('scenario.draw_poker.label_your_hand')}: "
            f"**{_fmt_hand(hand)}**  ({self._cat_name(hand)})"
        )
        return narrate(text, title=t("scenario.draw_poker.turn"))

    def _showdown_narration(
        self, you: list[Card], cpu: list[Card], verdict_key: str
    ) -> Event:
        text = (
            f"{t('scenario.draw_poker.label_your_hand')}: "
            f"**{_fmt_hand(you)}**  ({self._cat_name(you)})\n"
            f"{t('scenario.draw_poker.label_cpu_hand')}: "
            f"**{_fmt_hand(cpu)}**  ({self._cat_name(cpu)})\n"
            f"{t(verdict_key)}"
        )
        return narrate(text, title=t("scenario.draw_poker.turn"))

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.draw_poker.intro",
            title_key="scenario.draw_poker.intro_title",
            rounds=_MAX_TURNS,
        )

        you_score = 0
        cpu_score = 0

        for round_no in range(1, _MAX_TURNS + 1):  # hard cap → always terminates
            deck = _fresh_deck(self._rng)
            you: list[Card] = [deck.pop() for _ in range(5)]
            cpu: list[Card] = [deck.pop() for _ in range(5)]

            yield self._deal_narration(round_no, you)

            rec = _recommended_discards(you)
            opts = [
                ChoiceOption(
                    f"discard_{k}",
                    t(f"scenario.draw_poker.discard{k}_label"),
                    t(f"scenario.draw_poker.discard{k}_desc"),
                )
                for k in range(_MAX_DISCARD + 1)
            ]
            choice = await self.ask(
                t("scenario.draw_poker.your_move"), opts, default_id=f"discard_{rec}"
            )
            you_n = int(choice.split("_")[1])
            yield Event(
                kind=EventKind.AUDIT,
                source_id="draw_poker",
                payload={
                    "event": "draw_poker.discard",
                    "round": round_no,
                    "who": "you",
                    "discarded": you_n,
                    "display": t("scenario.draw_poker.audit_you_discard", n=you_n),
                },
            )
            you = _redraw(you, you_n, deck)

            cpu_n = _recommended_discards(cpu)
            cpu = _redraw(cpu, cpu_n, deck)
            yield Event(
                kind=EventKind.AUDIT,
                source_id="draw_poker",
                payload={
                    "event": "draw_poker.discard",
                    "round": round_no,
                    "who": "cpu",
                    "discarded": cpu_n,
                    "display": t("scenario.draw_poker.audit_cpu_discard", n=cpu_n),
                },
            )

            you_rank = _hand_rank(you)
            cpu_rank = _hand_rank(cpu)
            if you_rank > cpu_rank:
                you_score += 1
                verdict_key, outcome = "scenario.draw_poker.round_win", "you"
            elif you_rank < cpu_rank:
                cpu_score += 1
                verdict_key, outcome = "scenario.draw_poker.round_lose", "cpu"
            else:
                verdict_key, outcome = "scenario.draw_poker.round_tie", "tie"

            yield self._showdown_narration(you, cpu, verdict_key)
            yield Event(
                kind=EventKind.AUDIT,
                source_id="draw_poker",
                payload={
                    "event": "draw_poker.round_result",
                    "round": round_no,
                    "outcome": outcome,
                    "you_cat": you_rank[0],
                    "cpu_cat": cpu_rank[0],
                    "score": [you_score, cpu_score],
                },
            )

        if you_score > cpu_score:
            result_key = "scenario.draw_poker.result_win"
        elif you_score < cpu_score:
            result_key = "scenario.draw_poker.result_lose"
        else:
            result_key = "scenario.draw_poker.result_draw"
        yield Event(
            kind=EventKind.AUDIT,
            source_id="draw_poker",
            payload={
                "event": "draw_poker.match_result",
                "score": [you_score, cpu_score],
            },
        )
        yield narrate_key(
            result_key,
            title_key="scenario.draw_poker.result_title",
            you_score=you_score,
            cpu_score=cpu_score,
        )


__all__ = ["DrawPokerScenario"]
