"""``llove.games.chess`` — F16 マルチゲームアリーナの chess 実装.

F16(a) で確立した ``llove.games.base`` 抽象に乗る最初の他ゲーム実装.
shogi (`llove/shogi/` 直下) は MVP2a で先行整備したため別ディレクトリ
にあるが、chess は最初から ``llove/games/chess/`` 配下に作る. shogi も
MVP2b 完了後に ``llove/games/shogi/`` へ移行予定 (手戻り許容).

公開 API:

    from llove.games.chess import ChessEngine, EngineUnavailable

依存: ``[chess]`` extras (`python-chess` 1.11+, MIT, 14k★ GitHub).
"""

from __future__ import annotations

from llove.games.chess.engine import ChessEngine, EngineUnavailable

__all__ = ["ChessEngine", "EngineUnavailable"]
