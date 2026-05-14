"""共通 dataclass: ``Move`` / ``Observation`` / ``TermReason``.

設計の柱として:

- **Move は ``notation`` 文字列を 1 本** ぶら下げる極小コンテナ. 各ゲーム
  は USI / SAN / SGF / sente.net / tenhou JSON など好きな形式で詰める。
  llove はこの文字列を解釈しない (ゲーム実装の Engine だけが解釈する).
- **Observation は player ごとに別** — 不完全情報ゲーム (麻雀, ポーカー)
  は他プレイヤの手牌を ``private`` から落として渡す.
- **TermReason は string 互換 enum** — JSONL ログにそのまま乗る.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Move
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Move:
    """1 着手 (1 player の 1 アクション).

    Fields
    ------
    notation
        ゲーム固有の文字列表現 (USI ``"7g7f"`` / SAN ``"e4"`` / SGF
        ``"B[pd]"`` / 麻雀打牌 ``"d:5m"`` 等). Engine がパースする.
    thinking_ms
        プレイヤが「考えた」時間 (ms). LLM プロバイダの場合は API レイテンシ.
    commentary
        プレイヤのナラティブコメンタリ (LLM が生成する手の意図など).
    raw_response
        LLM プロバイダの場合、生のレスポンス全文 (audit / debug 用).
    """

    notation: str
    thinking_ms: int | None = None
    commentary: str = ""
    raw_response: str = ""


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    """1 player に渡す観測スナップショット.

    完全情報ゲーム (shogi, chess, go) は ``private`` を空にする — Engine
    の状態がそのまま public_state にコピーされる。
    不完全情報ゲーム (麻雀, ポーカー) は他プレイヤの手牌を ``private``
    から落として、自分の手牌だけを ``private`` に入れる。

    Fields
    ------
    player_id
        この観測を渡される対象プレイヤの ID.
    public_state
        全プレイヤが見える状態 (盤面 / 場 / 共通カード / 履歴 / ...).
    private_state
        ``player_id`` だけが見える状態 (自分の手牌 / 持ち駒の隠し情報 / ...).
        完全情報ゲームでは ``{}``.
    legal_moves
        現在合法な着手 (``Move.notation``) のリスト. 空なら投了相当.
    metadata
        ゲーム固有の補助情報 (現在 ply / 残り時間 / 持ち時間 / 手番表示).
    """

    player_id: str
    public_state: dict[str, Any] = field(default_factory=dict)
    private_state: dict[str, Any] = field(default_factory=dict)
    legal_moves: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# TermReason
# ---------------------------------------------------------------------------


class TermReason(StrEnum):
    """終局理由.

    JSONL ログにそのまま文字列で乗るので、値を変えると後方互換が壊れる.
    新しい理由は **追加** で対応.
    """

    CHECKMATE = "checkmate"            # 詰み (shogi/chess)
    STALEMATE = "stalemate"            # ステイルメイト (chess); shogi では起きない
    RESIGN_PLAYER = "resign_player"    # プレイヤが投了
    RESIGN_ILLEGAL = "resign_illegal"  # 違法手 N 回で失格
    REPETITION = "repetition"          # 千日手 / 三回繰り返し
    MAX_PLY = "max_ply"                # 最大ply に達した (安全網)
    TIMEOUT = "timeout"                # 時間切れ
    SCORE = "score"                    # 持ち時間制 / 麻雀: ハコ等
    DRAW = "draw"                      # 合意による引き分け
    CUSTOM = "custom"                  # ゲーム固有の終局
