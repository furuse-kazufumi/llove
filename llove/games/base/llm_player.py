"""実 LLM を相手にする汎用 :class:`GamePlayer`.

``LLMClient`` (anthropic / ollama / llmesh peer) をラップし, :class:`Observation`
からプロンプトを組み立て, 応答から着手 (:class:`Move`) を取り出す. これで
``run_game`` に乗る任意の ``GameEngine`` (chess 等) を実 LLM と対戦させられる —
合成の決定的 AI からの「卒業」の実体.

設計:

- **plain class** — ``MockPlayer`` / ``_ScriptedPlayer`` と同じ. ``GamePlayer``
  基底が値付きクラス属性 (``name="?"`` 等) を持つため, dataclass 化すると
  「非既定引数が既定引数の後」エラーになる. __init__ で明示設定する.
- **fail-closed** — ``LLMBackendError`` / ``LLMConfigError`` は resign に落とす.
  ゲームループを例外で巻き込まない (audit に理由が残る).
- **legality oracle はループ** — ここでは合法手を必ずしも保証しない. 合法手
  リストが観測に含まれれば拾って幅を絞る (ハルシネ減) が, 最終判定は engine.
"""

from __future__ import annotations

import json

from llove.games.base.player import GamePlayer, ThinkResult
from llove.games.base.types import Move, Observation
from llove.llm.client import LLMClient
from llove.llm.parsing import extract_move, first_move_token
from llove.llm.types import ChatMessage, ChatRequest, LLMBackendError, LLMConfigError

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert {game} player. Given the current position and the list "
    "of legal moves, pick the single strongest move. Answer with ONLY the move "
    "in the required notation — no explanation, no extra text."
)

#: 着手は短いので出力上限は控えめ (レイテンシ・コスト削減).
DEFAULT_MAX_TOKENS = 64
#: ゲームは低温で決定的寄りに.
DEFAULT_TEMPERATURE = 0.3


class LLMGamePlayer(GamePlayer):
    """``LLMClient`` を相手プレイヤとしてラップする汎用 player."""

    def __init__(
        self,
        client: LLMClient,
        *,
        player_id: str = "",
        game: str = "game",
        name: str | None = None,
        system_prompt: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._client = client
        self.provider = client.provider
        self.model = client.model
        self.player_id = player_id
        self.game = game
        self.name = name or f"{client.provider}:{client.model}"
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._temperature = temperature

    # -------- プロンプト構築 --------

    def _build_messages(self, observation: Observation) -> tuple[ChatMessage, ...]:
        system = (self._system_prompt or DEFAULT_SYSTEM_PROMPT).format(game=self.game)
        lines: list[str] = [
            f"You are player '{observation.player_id}' in a game of {self.game}."
        ]
        if observation.public_state:
            lines.append("Position / public state:")
            lines.append(json.dumps(observation.public_state, ensure_ascii=False))
        if observation.private_state:
            lines.append("Your private information:")
            lines.append(json.dumps(observation.private_state, ensure_ascii=False))
        if observation.metadata:
            lines.append("Info: " + json.dumps(observation.metadata, ensure_ascii=False))
        if observation.legal_moves:
            lines.append("Legal moves: " + ", ".join(observation.legal_moves))
            lines.append("Choose exactly ONE move from the legal moves listed above.")
        lines.append("Respond with only the move notation, nothing else.")
        return (
            ChatMessage("system", system),
            ChatMessage("user", "\n".join(lines)),
        )

    @staticmethod
    def _commentary(text: str, notation: str) -> str:
        """kifu ペイン用の短い人間可読コメンタリ (最初の非空行, 120 字上限)."""
        for line in text.splitlines():
            s = line.strip()
            if s and s != notation:
                return s[:120]
        return ""

    # -------- GamePlayer 契約 --------

    async def think(self, observation: Observation) -> ThinkResult:
        request = ChatRequest(
            messages=self._build_messages(observation),
            model=self.model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        try:
            resp = await self._client.complete(request)
        except (LLMBackendError, LLMConfigError) as exc:
            # fail-closed: バックエンド失敗はループを巻き込まず resign.
            return ThinkResult(
                move=None,
                resign=True,
                resign_reason=f"backend_error: {exc}",
            )

        notation = extract_move(resp.text, observation.legal_moves) or first_move_token(
            resp.text
        )
        if not notation:
            return ThinkResult(
                move=None,
                resign=True,
                resign_reason="LLM returned no interpretable move",
            )
        return ThinkResult(
            move=Move(
                notation=notation,
                thinking_ms=resp.latency_ms,
                commentary=self._commentary(resp.text, notation),
                raw_response=resp.text,
            )
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def make_game_player(
    spec: str,
    *,
    player_id: str = "",
    game: str = "game",
    config: object | None = None,
    transport: object | None = None,
    name: str | None = None,
    system_prompt: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> LLMGamePlayer:
    """``"provider:model"`` spec から LLM ゲームプレイヤを作る.

    ``config`` 省略時は ``LLMConfig.from_env()``. ``transport`` はテスト用 fake
    を差し込める. 設定不足は ``make_client`` が ``LLMConfigError`` を投げる.
    """
    from llove.llm.config import LLMConfig
    from llove.llm.factory import make_client

    cfg = config if isinstance(config, LLMConfig) else LLMConfig.from_env()
    client = make_client(spec, config=cfg, transport=transport)  # type: ignore[arg-type]
    return LLMGamePlayer(
        client,
        player_id=player_id,
        game=game,
        name=name,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )


__all__ = [
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_SYSTEM_PROMPT",
    "DEFAULT_TEMPERATURE",
    "LLMGamePlayer",
    "make_game_player",
]
