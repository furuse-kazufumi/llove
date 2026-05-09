"""``GameEngine`` ABC — N-player + 不完全情報対応の汎用エンジン.

設計:

- ``current_player_id()`` がそのターンに動くプレイヤを返す
- ``observation_for(player_id)`` がそのプレイヤ視点の観測を返す
- ``push(move, player_id)`` が着手を適用 + 合法性検証
- ``is_terminated()`` が終局していれば ``TermResult`` を返す

各ゲーム実装 (``llove.games.shogi.ShogiEngine`` 等) はこれを継承して
具体的なルールを書く. 共通ループ ``run_game`` はこの ABC のみに依存
するので、ゲーム横断で再利用できる.

将来 Rust 移植時 (F18 v2.0+) は ``llove-core`` クレートの
``trait GameEngine`` がこれと同形になる.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from llove.games.base.types import Move, Observation, TermReason


@dataclass(frozen=True)
class LegalityResult:
    """``GameEngine.push`` の戻り値.

    ``ok=False`` のとき ``reason`` は安定文字列 (``"illegal: nifu"`` 等).
    JSONL ログに直接乗るので、値を変えると後方互換が壊れる. 新しい
    reason は追加で.
    """

    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class TermResult:
    """``GameEngine.is_terminated`` の戻り値.

    Fields
    ------
    reason
        ``TermReason`` enum (string 互換).
    winner_id
        勝者プレイヤ ID. 引き分けなら ``None``. 1v1 ゲームのときは
        opponent を判定するのに使う; 多人数ゲームで複数勝者を表現
        したいときは ``winners`` を使う (将来拡張).
    detail
        ゲーム固有の人間可読詳細 (例: 麻雀の点数、shogi の最終 SFEN).
    """

    reason: TermReason
    winner_id: str | None = None
    detail: str = ""


class GameEngine(ABC):
    """全ゲームの基底クラス.

    Concrete subclasses must implement:
    - ``player_ids``         (順序付き player ID リスト)
    - ``current_player_id``  (今動くプレイヤ)
    - ``ply``                (経過した手数)
    - ``observation_for``    (player 視点観測)
    - ``push``               (着手適用)
    - ``is_terminated``      (終局判定)

    Optional:
    - ``state_summary``      (ログ向け短い要約)
    """

    #: ゲームの安定識別子 (``"shogi"`` / ``"chess"`` / ``"go"`` / ``"mahjong"`` ...).
    #: CLI ``llove play <game>`` の <game> と一致させる.
    game: str = "?"

    # ---- 全 player の列挙 ---------------------------------------------
    @abstractmethod
    def player_ids(self) -> list[str]:
        """ゲームに参加するプレイヤ ID を順序付きで返す."""

    @abstractmethod
    def current_player_id(self) -> str:
        """現在の手番プレイヤ ID."""

    # ---- 状態 ---------------------------------------------------------
    @property
    @abstractmethod
    def ply(self) -> int:
        """経過した着手数."""

    def state_summary(self) -> str:
        """ログ向け短い要約 (default = 空; 各ゲームで override)."""
        return ""

    # ---- 観測 ---------------------------------------------------------
    @abstractmethod
    def observation_for(self, player_id: str) -> Observation:
        """``player_id`` 視点の観測を返す.

        不完全情報ゲームでは他プレイヤの非公開状態を private から落とす.
        完全情報ゲームでは全プレイヤに同じ観測を返してよい.
        """

    # ---- 着手 ---------------------------------------------------------
    @abstractmethod
    def push(self, move: Move, player_id: str) -> LegalityResult:
        """着手 ``move`` を ``player_id`` の名義で適用.

        ok=False の場合、エンジン状態は変えない.
        ok=True の場合、内部状態を進める + 次のプレイヤを current にする.
        """

    # ---- 終局判定 -----------------------------------------------------
    @abstractmethod
    def is_terminated(self) -> TermResult | None:
        """終局していれば ``TermResult`` を、未了なら ``None`` を返す."""
