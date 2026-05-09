"""Game loop for ``llove play shogi``.

Drives two :class:`~llove.shogi.players.base.Player` instances against a
single :class:`~llove.shogi.engine.Engine`, yields :class:`Event`s into the
existing TUI / JSONL pipeline, and signs every move with the local llmesh
identity so the resulting kifu is tamper-evident.

Termination conditions (all map onto a stable ``term`` string in the
``shogi.game_end`` audit payload — never rename, only add):

* ``checkmate``      — one side is mated
* ``resign_player``  — a player returned ``ThinkResult(resign=True)``
* ``resign_illegal`` — a player produced 3 illegal-move strikes in a row
* ``sennichite``     — same position appeared 4 times
* ``max_ply``        — the safety cap was hit
* ``stalemate``      — only relevant in tests; not a real shogi outcome

Per-move signing uses the local :class:`~llove.identity.LoveIdentity`. The
signed payload is the canonical bytes of ``"{ply}|{side}|{usi}|{sfen_after}"``,
which pins the move to *both* the player and the resulting position.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from llove.events import Event, EventKind
from llove.identity import LoveIdentity, load_local_identity
from llove.shogi.engine import (
    TERM_CHECKMATE,
    TERM_MAX_PLY,
    TERM_RESIGN_ILLEGAL,
    TERM_RESIGN_PLAYER,
    TERM_SENNICHITE,
    TERM_STALEMATE,
    Engine,
)
from llove.shogi.players.base import Player

#: Each side gets this many illegal-move strikes before forfeiting.
DEFAULT_ILLEGAL_STRIKES = 3
#: Hard ceiling on half-moves so a runaway loop can't run forever.
DEFAULT_MAX_PLY = 400


@dataclass
class GameOutcome:
    """Result of a finished game (returned from ``run_game`` for callers
    that don't want to scrape the event stream)."""

    term: str
    plies: int
    winner: str | None  # "sente" / "gote" / None for draws
    moves_usi: list[str] = field(default_factory=list)
    final_sfen: str = ""
    illegal_strikes: dict[str, int] = field(default_factory=dict)


def _sign_move_payload(
    identity: LoveIdentity | None, ply: int, side: str, usi: str, sfen_after: str
) -> dict[str, str | None]:
    """Return ``{"signed_bytes": "<hex>", "signature": "<hex>" | None}``.

    The hash input pins ``(ply, side, usi, sfen_after)`` together so the
    signature is invalid if any of those fields are tampered with.
    """
    canonical = f"{ply}|{side}|{usi}|{sfen_after}".encode()
    if identity is None or not identity.can_sign:
        return {"signed_bytes": canonical.hex(), "signature": None}
    sig = identity.sign(canonical)
    return {
        "signed_bytes": canonical.hex(),
        "signature": sig.hex() if sig is not None else None,
        "signer_did": identity.did_key,
    }


async def run_game(
    sente: Player,
    gote: Player,
    *,
    engine: Engine | None = None,
    identity: LoveIdentity | None = None,
    illegal_strikes_allowed: int = DEFAULT_ILLEGAL_STRIKES,
    max_ply: int = DEFAULT_MAX_PLY,
) -> AsyncIterator[Event]:
    """Drive a full shogi game and yield events along the way.

    The caller decides how to consume the events — LoveApp's pipeline is
    happy to receive them as a DataSource, and a CLI ``--stream`` mode can
    just dump ``ev.model_dump_json()`` straight to stdout.

    Parameters
    ----------
    sente, gote
        :class:`Player` instances. The loop is responsible for closing them
        (via ``aclose``) on completion.
    engine
        Optional pre-existing :class:`Engine`. Default = a fresh start.
    identity
        Optional :class:`LoveIdentity` for signing. Falls through to
        ``load_local_identity()`` when not provided.
    illegal_strikes_allowed
        Max consecutive illegal-move strikes per side before forfeit.
    max_ply
        Hard cap on half-moves.

    Yields
    ------
    Event
        ``EventKind.AUDIT`` for game start, every move, every illegal
        attempt, and game end. ``EventKind.SENSOR`` carries an
        ``eval_score`` placeholder (always 0 for now — MVP2b adds an
        actual evaluator).
    """
    eng = engine if engine is not None else Engine()
    ident = identity if identity is not None else load_local_identity()
    strikes: dict[str, int] = {"sente": 0, "gote": 0}

    # ---- game_start audit -------------------------------------------------
    yield Event(
        kind=EventKind.AUDIT,
        source_id="judge",
        payload={
            "event": "shogi.game_start",
            "sente": sente.name,
            "gote": gote.name,
            "sente_provider": f"{sente.provider}:{sente.model}",
            "gote_provider": f"{gote.provider}:{gote.model}",
            "signer_did": ident.did_key if ident else None,
            "signing_enabled": bool(ident and ident.can_sign),
            "display": (
                f"☗ 先手: {sente.name}  ☖ 後手: {gote.name}"
                + (f"  (signed by {ident.did_key[:24]}…)" if ident and ident.can_sign else "")
            ),
        },
    )

    outcome: GameOutcome | None = None
    moves_usi: list[str] = []

    try:
        while True:
            if eng.ply >= max_ply:
                outcome = GameOutcome(
                    term=TERM_MAX_PLY, plies=eng.ply, winner=None,
                    moves_usi=moves_usi, final_sfen=eng.sfen,
                    illegal_strikes=dict(strikes),
                )
                break

            side = eng.turn
            player = sente if side == "sente" else gote
            opponent = "gote" if side == "sente" else "sente"

            think_result = await player.think(eng)

            # ---- Player resigns voluntarily -----------------------------
            if think_result.resign or think_result.move is None:
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id=side,
                    payload={
                        "event": "shogi.resign",
                        "side": side,
                        "reason": think_result.resign_reason or "(no reason given)",
                        "ply": eng.ply,
                        "display": f"{'☗' if side == 'sente' else '☖'} {side} resigns ({think_result.resign_reason})",
                    },
                )
                outcome = GameOutcome(
                    term=TERM_RESIGN_PLAYER, plies=eng.ply, winner=opponent,
                    moves_usi=moves_usi, final_sfen=eng.sfen,
                    illegal_strikes=dict(strikes),
                )
                break

            # ---- Validate + apply ---------------------------------------
            move = think_result.move
            result = eng.push_usi(move.usi)
            if not result.ok:
                strikes[side] += 1
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id=side,
                    payload={
                        "event": "shogi.illegal_attempt",
                        "side": side,
                        "usi": move.usi,
                        "reason": result.reason,
                        "strike": strikes[side],
                        "max_strikes": illegal_strikes_allowed,
                        "ply": eng.ply,
                        "display": (
                            f"⚠ {side} illegal ({move.usi}): {result.reason}  "
                            f"[{strikes[side]}/{illegal_strikes_allowed}]"
                        ),
                    },
                )
                if strikes[side] >= illegal_strikes_allowed:
                    outcome = GameOutcome(
                        term=TERM_RESIGN_ILLEGAL, plies=eng.ply, winner=opponent,
                        moves_usi=moves_usi, final_sfen=eng.sfen,
                        illegal_strikes=dict(strikes),
                    )
                    break
                # Not yet at the strike cap — re-prompt the same player on
                # the next loop iteration.
                continue

            # Legal: reset that side's strike counter, record + sign.
            strikes[side] = 0
            moves_usi.append(move.usi)
            sig_payload = _sign_move_payload(ident, eng.ply, side, move.usi, eng.sfen)

            yield Event(
                kind=EventKind.AUDIT,
                source_id=side,
                payload={
                    "event": "shogi.move",
                    "side": side,
                    "ply": eng.ply,
                    "usi": move.usi,
                    "thinking_ms": move.thinking_ms,
                    "commentary": move.commentary,
                    "sfen_after": eng.sfen,
                    "is_check": eng.is_check(),
                    **sig_payload,
                    "display": (
                        f"{'▲' if side == 'sente' else '△'}{move.usi}"
                        + (f"  (think {move.thinking_ms}ms)" if move.thinking_ms else "")
                    ),
                },
            )
            yield Event(
                kind=EventKind.SENSOR,
                source_id=side,
                payload={
                    "sensor_id": "eval_score",
                    "value": 0,  # MVP2b: real evaluator from the player's response
                    "ply": eng.ply,
                    "side": side,
                    "usi": move.usi,
                },
            )

            # ---- Termination checks (after the move) --------------------
            if eng.is_checkmate():
                outcome = GameOutcome(
                    term=TERM_CHECKMATE, plies=eng.ply, winner=side,
                    moves_usi=moves_usi, final_sfen=eng.sfen,
                    illegal_strikes=dict(strikes),
                )
                break
            if eng.is_fourfold_repetition():
                outcome = GameOutcome(
                    term=TERM_SENNICHITE, plies=eng.ply, winner=None,
                    moves_usi=moves_usi, final_sfen=eng.sfen,
                    illegal_strikes=dict(strikes),
                )
                break
            if eng.is_stalemate():  # impossible in real shogi; safety net.
                outcome = GameOutcome(
                    term=TERM_STALEMATE, plies=eng.ply, winner=None,
                    moves_usi=moves_usi, final_sfen=eng.sfen,
                    illegal_strikes=dict(strikes),
                )
                break

        assert outcome is not None
    finally:
        # Always close players, even on cancellation.
        try:
            await sente.aclose()
        finally:
            await gote.aclose()

    # ---- game_end audit ---------------------------------------------------
    yield Event(
        kind=EventKind.AUDIT,
        source_id="judge",
        payload={
            "event": "shogi.game_end",
            "term": outcome.term,
            "winner": outcome.winner,
            "plies": outcome.plies,
            "final_sfen": outcome.final_sfen,
            "moves_usi": outcome.moves_usi,
            "illegal_strikes": outcome.illegal_strikes,
            "display": (
                f"⚑ game end: term={outcome.term}, "
                f"winner={outcome.winner or 'draw'}, plies={outcome.plies}"
            ),
        },
    )


def outcome_summary_json(outcome: GameOutcome) -> str:
    """JSON serialisation helper — used by ``llove play shogi --stream``."""
    return json.dumps(
        {
            "term": outcome.term,
            "winner": outcome.winner,
            "plies": outcome.plies,
            "moves_usi": outcome.moves_usi,
            "final_sfen": outcome.final_sfen,
            "illegal_strikes": outcome.illegal_strikes,
        },
        ensure_ascii=False,
    )
