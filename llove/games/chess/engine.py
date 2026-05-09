"""ChessEngine — python-chess の薄いラッパ.

F16 GameEngine を継承し、shogi 同様 ``is_legal`` をルール判定の唯一の
真理として扱う (en passant / castling / promotion / pinned piece /
discovered check / 50-move rule / threefold repetition すべて
python-chess に委譲).

Move.notation は **UCI 形式** (``"e2e4"`` / ``"e7e8q"``) を使う.
SAN (``"Nxe4"`` 等) は表示用途で別 API として提供.
"""

from __future__ import annotations

from typing import Any

from llove.games.base import (
    GameEngine,
    LegalityResult,
    Move,
    Observation,
    TermReason,
)
from llove.games.base.engine import TermResult


class EngineUnavailable(RuntimeError):
    """``python-chess`` が無いときに投げる."""


def _import_chess() -> Any:
    try:
        import chess  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover — guarded by extras
        msg = (
            "python-chess is not installed. The chess engine needs it.\n"
            "Install with: pip install 'llmesh-llove[chess]'"
        )
        raise EngineUnavailable(msg) from exc
    return chess


# F16 内 player_id の規約: 1v1 ゲームは "white" / "black".
WHITE = "white"
BLACK = "black"


class ChessEngine(GameEngine):
    """1 game = 1 ChessEngine. python-chess の Board を保持."""

    game = "chess"

    def __init__(self, fen: str | None = None) -> None:
        self._chess = _import_chess()
        self._board = (
            self._chess.Board() if fen is None else self._chess.Board(fen)
        )

    # ---- F16 GameEngine API ------------------------------------------
    def player_ids(self) -> list[str]:
        return [WHITE, BLACK]

    def current_player_id(self) -> str:
        return WHITE if self._board.turn == self._chess.WHITE else BLACK

    @property
    def ply(self) -> int:
        return len(self._board.move_stack)

    def state_summary(self) -> str:
        return self._board.fen()

    def observation_for(self, player_id: str) -> Observation:
        # chess は完全情報 — public_state に board / legal moves を全て載せる.
        legal_uci = [m.uci() for m in self._board.legal_moves]
        return Observation(
            player_id=player_id,
            public_state={
                "fen": self._board.fen(),
                "turn": self.current_player_id(),
                "is_check": bool(self._board.is_check()),
                "halfmove_clock": self._board.halfmove_clock,
                "fullmove_number": self._board.fullmove_number,
            },
            legal_moves=legal_uci,
            metadata={"ply": self.ply},
        )

    def push(self, move: Move, player_id: str) -> LegalityResult:
        if player_id != self.current_player_id():
            return LegalityResult(
                ok=False,
                reason=f"illegal: not {player_id}'s turn",
            )

        # parse
        try:
            m = self._chess.Move.from_uci(move.notation)
        except (ValueError, IndexError, AssertionError) as exc:
            return LegalityResult(
                ok=False,
                reason=f"parse_error: {exc}",
            )

        # legality
        if not self._board.is_legal(m):
            if not self._board.is_pseudo_legal(m):
                return LegalityResult(ok=False, reason="illegal: not pseudo-legal")
            return LegalityResult(ok=False, reason="illegal: rule violation")

        # apply
        self._board.push(m)
        return LegalityResult(ok=True)

    def is_terminated(self) -> TermResult | None:
        if self._board.is_checkmate():
            # 手番側が詰まされた → 直前に動かした側が勝者
            winner = BLACK if self._board.turn == self._chess.WHITE else WHITE
            return TermResult(reason=TermReason.CHECKMATE, winner_id=winner)
        if self._board.is_stalemate():
            return TermResult(reason=TermReason.STALEMATE, winner_id=None)
        # threefold repetition は claim だが、 5-fold は自動.
        if self._board.is_fivefold_repetition() or self._board.is_repetition(3):
            return TermResult(reason=TermReason.REPETITION, winner_id=None)
        # 50 / 75 move rule
        if self._board.is_seventyfive_moves() or self._board.can_claim_fifty_moves():
            return TermResult(reason=TermReason.DRAW, winner_id=None, detail="fifty-move rule")
        # insufficient material
        if self._board.is_insufficient_material():
            return TermResult(
                reason=TermReason.DRAW,
                winner_id=None,
                detail="insufficient material",
            )
        return None

    # ---- 表示補助 ----------------------------------------------------
    def san(self, uci: str) -> str:
        """UCI を SAN (Nxe4 等) に変換. 未来手は不可なので、push 直後の
        履歴に対しては ``self._board.move_stack`` 経由で取り出す形がより
        確実 — このヘルパは「これから打つ手」用."""
        try:
            m = self._chess.Move.from_uci(uci)
        except Exception:
            return uci
        if not self._board.is_legal(m):
            return uci
        return self._board.san(m)
