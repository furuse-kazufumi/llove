"""snap — an interactive Snap card-game cartridge (you vs a simple bot).

Cards flip one at a time onto a shared pile. When the freshly flipped card
matches the *rank* of the card beneath it, it is a **Snap!** moment: the
first player to call wins the whole pile. Each turn *you* decide — call
``Snap!`` or ``pass`` — and a deterministic bot races you. Calling Snap when
there is no match is a *false snap* and forfeits the pile to the bot. When the
deck runs out, whoever has collected the most cards wins.

Like every llove cartridge this is synthetic and fully offline. The opponent
is a small deterministic policy seeded from ``seed`` (a reaction coin-flip on
each match) — **not** a real LLM. Wiring an LLM opponent that reasons about
timing and bluffing is a future-session task; the Event payloads already carry
enough state (pile, deck size, scores) for a viewer or an LLM driver to replay
the game.

With no asker wired (CI / ``--list``), the deterministic default is to
``pass`` every turn, so the run always completes, the deck always empties, and
a winner (or draw) is declared.
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

_RANKS: tuple[str, ...] = ("A", "K", "Q", "J")
_SUITS: tuple[str, ...] = ("S", "H", "D", "C")
_SUIT_GLYPH: dict[str, str] = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}

# Hard turn cap so the loop is provably finite even if the deck logic changes.
_MAX_TURNS = 40
# Chance the bot reacts to a match at all (deterministic via the seeded RNG).
_AI_REACT_P = 0.65
# When both you and the bot call Snap on a match, you win with this probability
# (a small edge that rewards a correctly-timed call).
_HUMAN_EDGE = 0.55


class _Card(NamedTuple):
    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank}{_SUIT_GLYPH[self.suit]}"


class SnapScenario(InteractiveScenario):
    """Play Snap against a deterministic bot — call ``Snap!`` on a match."""

    name = "snap"
    i18n_key = "snap"
    default_pause = 0.1

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _make_deck(self) -> list[_Card]:
        deck = [_Card(r, s) for r in _RANKS for s in _SUITS]
        self._rng.shuffle(deck)
        return deck

    def _render_board(
        self,
        *,
        pile: list[_Card],
        deck_left: int,
        you: int,
        ai: int,
        note: str,
    ) -> str:
        top = str(pile[-1]) if pile else "—"
        under = str(pile[-2]) if len(pile) >= 2 else "—"
        return "\n".join(
            [
                f"Pile top: **{top}**   (under: {under})   pile size: {len(pile)}",
                f"Deck left: {deck_left}    You: {you}   Bot: {ai}",
                note,
            ]
        )

    def _resolve(
        self,
        move: str,
        match: bool,
        pile: list[_Card],
        you: int,
        ai: int,
    ) -> tuple[str, int, int, list[_Card]]:
        """Apply one decision. Returns (outcome_text, you, ai, new_pile)."""
        n = len(pile)
        if move == "snap":
            if match:
                bot_reacts = self._rng.random() < _AI_REACT_P
                bot_faster = bot_reacts and self._rng.random() >= _HUMAN_EDGE
                if bot_faster:
                    msg = f"You called Snap, but the bot was faster — it takes {n}."
                    return (msg, you, ai + n, [])
                msg = f"Snap! You were first and take the pile of {n} cards."
                return (msg, you + n, ai, [])
            msg = f"False Snap — no match. The pile of {n} cards goes to the bot."
            return (msg, you, ai + n, [])
        # move == "pass"
        if match:
            if self._rng.random() < _AI_REACT_P:
                msg = f"You passed; the bot snapped the match and takes {n}."
                return (msg, you, ai + n, [])
            return ("You passed; the bot missed the match. The pile carries over.", you, ai, pile)
        return ("You passed; no match. The next card flips.", you, ai, pile)

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.snap.intro", title_key="scenario.snap.intro_title")

        deck = self._make_deck()
        pile: list[_Card] = []
        you = 0
        ai = 0
        turn_title = t("scenario.snap.turn")

        for turn in range(1, _MAX_TURNS + 1):
            if not deck:
                break
            card = deck.pop()
            pile.append(card)
            match = len(pile) >= 2 and pile[-1].rank == pile[-2].rank

            yield Event(
                kind=EventKind.AUDIT,
                source_id="snap",
                payload={
                    "event": "card.flip",
                    "turn": turn,
                    "card": str(card),
                    "match": match,
                    "pile": len(pile),
                    "display": f"flip {card} ({'match' if match else 'no match'})",
                },
            )

            hint = "rank match — Snap is live!" if match else "no match"
            yield narrate(
                self._render_board(
                    pile=pile,
                    deck_left=len(deck),
                    you=you,
                    ai=ai,
                    note=f"Turn {turn}: flipped {card} — {hint}",
                ),
                title=turn_title,
            )

            opts = [
                ChoiceOption(
                    "snap",
                    t("scenario.snap.snap_label"),
                    t("scenario.snap.snap_desc"),
                ),
                ChoiceOption(
                    "pass",
                    t("scenario.snap.pass_label"),
                    t("scenario.snap.pass_desc"),
                ),
            ]
            move = await self.ask(t("scenario.snap.your_move"), opts, default_id="pass")

            outcome, you, ai, pile = self._resolve(move, match, pile, you, ai)
            yield Event(
                kind=EventKind.AUDIT,
                source_id="snap",
                payload={
                    "event": "turn.resolved",
                    "turn": turn,
                    "move": move,
                    "match": match,
                    "you": you,
                    "ai": ai,
                    "display": outcome,
                },
            )
            yield narrate(
                self._render_board(
                    pile=pile, deck_left=len(deck), you=you, ai=ai, note=outcome
                ),
                title=turn_title,
            )

        # End of deck — leftover pile belongs to nobody. Decide the winner.
        if you > ai:
            result_key = "scenario.snap.result_win"
        elif you < ai:
            result_key = "scenario.snap.result_lose"
        else:
            result_key = "scenario.snap.result_draw"

        yield Event(
            kind=EventKind.AUDIT,
            source_id="snap",
            payload={
                "event": "game.end",
                "you": you,
                "ai": ai,
                "leftover": len(pile),
                "display": f"final score — You: {you}  Bot: {ai}",
            },
        )
        yield narrate(
            self._render_board(
                pile=pile,
                deck_left=0,
                you=you,
                ai=ai,
                note=f"Deck empty. Final — You: {you}  Bot: {ai}",
            ),
            title=turn_title,
        )
        yield narrate_key(result_key, title_key="scenario.snap.result_title")


__all__ = ["SnapScenario"]
