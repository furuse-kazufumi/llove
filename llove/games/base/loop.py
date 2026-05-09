"""汎用 ``run_game`` — N-player + 不完全情報対応のゲームループ.

shogi の ``llove.shogi.loop.run_game`` の汎用版. ``GameEngine`` ABC と
``GamePlayer`` ABC のみに依存し、ゲーム種類を知らない. ループから出る
``Event`` は LoveApp の TUI ペインで再生でき、JSONL ログにそのまま乗る.

Ed25519 署名 (F12 / shogi MVP2a で「仕様」化) も汎用化する: 各 move は
canonical bytes ``"{game}|{ply}|{player_id}|{notation}|{state_summary}"``
を署名対象とする (shogi は ``state_summary = sfen_after``).

F18 Rust 移植時は ``llove-core::run_game`` がこれと同じ API になる.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from llove.events import Event, EventKind
from llove.games.base.engine import GameEngine
from llove.games.base.player import GamePlayer
from llove.games.base.types import TermReason
from llove.identity import LoveIdentity, load_local_identity

#: 1 人 1 ターンあたり許される違法手連続数。デフォルト 3 で投了.
DEFAULT_ILLEGAL_STRIKES = 3
#: 安全網: ループが何があっても止まる ply 数.
DEFAULT_MAX_PLY = 1000


@dataclass
class GameOutcome:
    """終局結果. 観戦 / バッチ評価から JSON でも引ける."""

    game: str
    term: TermReason
    plies: int
    winner_id: str | None = None
    moves: list[dict[str, object]] = field(default_factory=list)
    final_state_summary: str = ""
    illegal_strikes: dict[str, int] = field(default_factory=dict)
    detail: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "game": self.game,
                "term": str(self.term),
                "winner_id": self.winner_id,
                "plies": self.plies,
                "moves": self.moves,
                "final_state_summary": self.final_state_summary,
                "illegal_strikes": self.illegal_strikes,
                "detail": self.detail,
            },
            ensure_ascii=False,
        )


def _sign_move_payload(
    identity: LoveIdentity | None,
    *,
    game: str,
    ply: int,
    player_id: str,
    notation: str,
    state_summary: str,
) -> dict[str, str | None]:
    """Per-move Ed25519 sign — 全ゲーム横断で同じ canonical 形式を使う.

    canonical = ``"{game}|{ply}|{player_id}|{notation}|{state_summary}"``

    1 個でも違うフィールドが書き換わると署名が壊れる → 棋譜の改竄検知.
    """
    canonical = f"{game}|{ply}|{player_id}|{notation}|{state_summary}".encode()
    if identity is None or not identity.can_sign:
        return {"signed_bytes": canonical.hex(), "signature": None}
    sig = identity.sign(canonical)
    return {
        "signed_bytes": canonical.hex(),
        "signature": sig.hex() if sig is not None else None,
        "signer_did": identity.did_key,
    }


async def run_game(
    engine: GameEngine,
    players: dict[str, GamePlayer],
    *,
    identity: LoveIdentity | None = None,
    illegal_strikes_allowed: int = DEFAULT_ILLEGAL_STRIKES,
    max_ply: int = DEFAULT_MAX_PLY,
) -> AsyncIterator[Event]:
    """汎用ゲームループ.

    Parameters
    ----------
    engine
        ``GameEngine`` インスタンス. 既に初期化済みでなければならない.
    players
        ``{player_id: GamePlayer}`` のマップ. ``engine.player_ids()`` の
        全 ID をカバーしていること.
    identity
        Ed25519 署名用. ``None`` なら ``load_local_identity()`` で発見.
    illegal_strikes_allowed
        違法手連続数の閾値. 越えたら ``RESIGN_ILLEGAL`` で終局.
    max_ply
        安全網. これに達したら ``MAX_PLY`` で終局.

    Yields
    ------
    Event
        ``shogi.*`` ではなく ``game.*`` 名前空間の AUDIT イベント:
        - ``game.start`` (1 回): 各プレイヤ identity / provider / model
        - ``game.move`` (合法手ごと): notation / signed_bytes / signature
        - ``game.illegal_attempt`` (違法手ごと): reason / strike count
        - ``game.resign`` (プレイヤ投了): reason
        - ``game.end`` (1 回): term / winner_id / plies
    """
    ident = identity if identity is not None else load_local_identity()
    strikes: dict[str, int] = {pid: 0 for pid in engine.player_ids()}
    moves_log: list[dict[str, object]] = []

    # ---- player_id ↔ Player の整合性チェック (fail-closed) ----------
    missing = [pid for pid in engine.player_ids() if pid not in players]
    if missing:
        raise ValueError(
            f"missing player(s) for {missing!r}; "
            f"engine expects {engine.player_ids()!r}, got {sorted(players)!r}"
        )

    # 各 Player に自分の player_id を伝える
    for pid, player in players.items():
        if not player.player_id:
            player.player_id = pid

    # ---- game.start --------------------------------------------------
    yield Event(
        kind=EventKind.AUDIT,
        source_id="judge",
        payload={
            "event": "game.start",
            "game": engine.game,
            "player_ids": engine.player_ids(),
            "players": {
                pid: {
                    "name": p.name,
                    "provider": p.provider,
                    "model": p.model,
                }
                for pid, p in players.items()
            },
            "signer_did": ident.did_key if ident else None,
            "signing_enabled": bool(ident and ident.can_sign),
            "display": (
                f"⚑ {engine.game} game start: "
                + " vs ".join(p.name for p in players.values())
                + (f"  (signed by {ident.did_key[:24]}…)" if ident and ident.can_sign else "")
            ),
        },
    )

    outcome: GameOutcome | None = None
    try:
        while True:
            if engine.ply >= max_ply:
                outcome = GameOutcome(
                    game=engine.game, term=TermReason.MAX_PLY, plies=engine.ply,
                    moves=moves_log,
                    final_state_summary=engine.state_summary(),
                    illegal_strikes=dict(strikes),
                )
                break

            # 既に終局しているか? (engine が独自に判定: 千日手等)
            term = engine.is_terminated()
            if term is not None:
                outcome = GameOutcome(
                    game=engine.game, term=term.reason, plies=engine.ply,
                    winner_id=term.winner_id,
                    moves=moves_log,
                    final_state_summary=engine.state_summary(),
                    illegal_strikes=dict(strikes),
                    detail=term.detail,
                )
                break

            current = engine.current_player_id()
            player = players[current]
            obs = engine.observation_for(current)
            think_result = await player.think(obs)

            # ---- voluntary resign --------------------------------------
            if think_result.resign or think_result.move is None:
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id=current,
                    payload={
                        "event": "game.resign",
                        "game": engine.game,
                        "player_id": current,
                        "reason": think_result.resign_reason or "(no reason given)",
                        "ply": engine.ply,
                        "display": f"☖ {current} resigns ({think_result.resign_reason})",
                    },
                )
                # 1v1 なら other player が勝者. N-player は engine 固有の処理が必要だが
                # MVP ではシンプルに「resigner 以外が勝者扱い (1v1 限定)」.
                others = [pid for pid in engine.player_ids() if pid != current]
                winner = others[0] if len(others) == 1 else None
                outcome = GameOutcome(
                    game=engine.game, term=TermReason.RESIGN_PLAYER, plies=engine.ply,
                    winner_id=winner, moves=moves_log,
                    final_state_summary=engine.state_summary(),
                    illegal_strikes=dict(strikes),
                )
                break

            # ---- validate + apply --------------------------------------
            move = think_result.move
            result = engine.push(move, current)
            if not result.ok:
                strikes[current] += 1
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id=current,
                    payload={
                        "event": "game.illegal_attempt",
                        "game": engine.game,
                        "player_id": current,
                        "notation": move.notation,
                        "reason": result.reason,
                        "strike": strikes[current],
                        "max_strikes": illegal_strikes_allowed,
                        "ply": engine.ply,
                        "display": (
                            f"⚠ {current} illegal ({move.notation}): {result.reason}  "
                            f"[{strikes[current]}/{illegal_strikes_allowed}]"
                        ),
                    },
                )
                if strikes[current] >= illegal_strikes_allowed:
                    others = [pid for pid in engine.player_ids() if pid != current]
                    winner = others[0] if len(others) == 1 else None
                    outcome = GameOutcome(
                        game=engine.game, term=TermReason.RESIGN_ILLEGAL, plies=engine.ply,
                        winner_id=winner, moves=moves_log,
                        final_state_summary=engine.state_summary(),
                        illegal_strikes=dict(strikes),
                    )
                    break
                continue  # 再プロンプト

            # legal move applied
            strikes[current] = 0
            sig_payload = _sign_move_payload(
                ident,
                game=engine.game, ply=engine.ply, player_id=current,
                notation=move.notation, state_summary=engine.state_summary(),
            )
            move_log = {
                "ply": engine.ply,
                "player_id": current,
                "notation": move.notation,
                "thinking_ms": move.thinking_ms,
                "commentary": move.commentary,
                **sig_payload,
            }
            moves_log.append(move_log)
            yield Event(
                kind=EventKind.AUDIT,
                source_id=current,
                payload={
                    "event": "game.move",
                    "game": engine.game,
                    "player_id": current,
                    "ply": engine.ply,
                    "notation": move.notation,
                    "thinking_ms": move.thinking_ms,
                    "commentary": move.commentary,
                    "state_summary": engine.state_summary(),
                    **sig_payload,
                    "display": (
                        f"{current}: {move.notation}"
                        + (f"  (think {move.thinking_ms}ms)" if move.thinking_ms else "")
                    ),
                },
            )

        assert outcome is not None
    finally:
        for player in players.values():
            try:
                await player.aclose()
            except Exception:  # nosec B110 — ベストエフォートクリーンアップ
                pass

    # ---- game.end ----------------------------------------------------
    yield Event(
        kind=EventKind.AUDIT,
        source_id="judge",
        payload={
            "event": "game.end",
            "game": outcome.game,
            "term": str(outcome.term),
            "winner_id": outcome.winner_id,
            "plies": outcome.plies,
            "final_state_summary": outcome.final_state_summary,
            "illegal_strikes": outcome.illegal_strikes,
            "detail": outcome.detail,
            "display": (
                f"⚑ game end: term={outcome.term}, "
                f"winner={outcome.winner_id or 'draw'}, plies={outcome.plies}"
            ),
        },
    )
