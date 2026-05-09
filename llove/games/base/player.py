"""``GamePlayer`` ABC — 全ゲーム横断の async プレイヤ抽象.

shogi の ``llove.shogi.players.base.Player`` の汎用版. 観測を受け取り
着手 (or 投了) を返す. async を前提にすることで Anthropic / Ollama /
llmesh peer の HTTP 呼び出しが LoveApp の asyncio ループに自然に乗る.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from llove.games.base.types import Move, Observation


@dataclass(frozen=True)
class ThinkResult:
    """``GamePlayer.think`` の戻り値.

    ``move=None`` + ``resign=True`` で投了。``resign_reason`` は audit
    ペインに表示される人間可読文字列.
    """

    move: Move | None
    resign: bool = False
    resign_reason: str = ""


class GamePlayer(ABC):
    """全ゲーム横断の async player ABC.

    Concrete subclasses (``MockPlayer`` / ``AnthropicPlayer`` /
    ``OllamaPlayer`` / ``LlmeshPeerPlayer`` / ``HumanPlayer``) は
    ``think(observation)`` だけ実装すれば良い.

    F18 Rust 移植時は ``trait GamePlayer { async fn think(...) }``
    に対応.
    """

    #: 表示用名前 (audit / 棋譜先頭で見せる). 例: ``"mock:script (sente)"``.
    name: str = "?"

    #: プロバイダ識別子 (``"mock"`` / ``"anthropic"`` / ``"ollama"`` / ``"llmesh"`` / ``"human"``).
    provider: str = "?"

    #: モデル文字列 (``"claude-haiku-4-5"`` / ``"llama3:70b"`` / ...).
    model: str = ""

    #: 担当する player_id (Engine.player_ids() のいずれか). マルチプレイヤゲーム対応.
    player_id: str = ""

    @abstractmethod
    async def think(self, observation: Observation) -> ThinkResult:
        """観測を受けて着手 (or 投了) を返す.

        実装側の責務:
        - ``observation.legal_moves`` を **必ずしも検証しない** で良い —
          ループ側で push の戻り値を見て illegal_attempt をハンドルする.
        - ただし LLM プロバイダは合法手リストをプロンプトに入れて
          幅員制限するのが普通 (合法手提示でハルシネ大幅減).
        """

    async def aclose(self) -> None:
        """HTTP クライアント等の片付け. デフォルトは no-op."""
