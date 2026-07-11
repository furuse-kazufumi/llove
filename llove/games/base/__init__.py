"""``llove.games.base`` — N-player + 不完全情報対応の汎用ゲーム骨格.

将来 Rust 移植時の ``llove-core`` クレートに対応。

公開 API:

    from llove.games.base import (
        Move,                        # 汎用着手 (usi / san / sgf / ...)
        Observation,                 # 観測 (公開状態 + 非公開状態 + legal moves)
        GameEngine,                  # ABC: observation_for / push / 終局判定
        GamePlayer, ThinkResult,     # ABC: async think
        GameOutcome,                 # 終局 (term, winner, plies, signed_log)
        run_game,                    # 汎用ループ
        TermReason,                  # 終局理由 enum (string 互換)
        LegalityResult,              # push の結果
    )
"""

from __future__ import annotations

from llove.games.base.engine import GameEngine, LegalityResult
from llove.games.base.llm_player import LLMGamePlayer, make_game_player
from llove.games.base.loop import GameOutcome, run_game
from llove.games.base.player import GamePlayer, ThinkResult
from llove.games.base.types import Move, Observation, TermReason

__all__ = [
    "GameEngine",
    "GameOutcome",
    "GamePlayer",
    "LLMGamePlayer",
    "LegalityResult",
    "Move",
    "Observation",
    "TermReason",
    "ThinkResult",
    "make_game_player",
    "run_game",
]
