"""実 LLM を指す shogi :class:`Player` (MVP2b).

``shogi.players.base.make_player`` の ``anthropic`` / ``ollama`` / ``llmesh``
分岐が返す実体. ``LLMClient`` をラップし, engine の SFEN・合法 USI・棋譜から
プロンプトを組み立て, 応答から USI を取り出す.

汎用の :class:`llove.games.base.llm_player.LLMGamePlayer` と兄弟だが, shogi は
独自の ``Player`` ABC (engine を直接受け取る) を持つため, 薄い専用アダプタを
置く. 着手抽出ロジック (:mod:`llove.llm.parsing`) は共有する.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llove.llm.client import LLMClient
from llove.llm.parsing import extract_move
from llove.llm.types import ChatMessage, ChatRequest, LLMBackendError, LLMConfigError
from llove.shogi.players.base import Move, Player, ThinkResult

if TYPE_CHECKING:  # pragma: no cover — type-only
    from llove.llm.config import LLMConfig
    from llove.llm.transport import HttpTransport
    from llove.shogi.engine import Engine

_SYSTEM_PROMPT = (
    "You are a strong shogi engine playing as {side}. You are given the current "
    "position in SFEN and the exhaustive list of legal moves in USI notation. "
    "Reply with ONLY one USI move chosen from that list — no explanation."
)

DEFAULT_MAX_TOKENS = 32
DEFAULT_TEMPERATURE = 0.3


class LLMShogiPlayer(Player):
    """``LLMClient`` を相手にする shogi player."""

    def __init__(
        self,
        client: LLMClient,
        *,
        side: str = "sente",
        name: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        self._client = client
        self.provider = client.provider
        self.model = client.model
        self._side = side
        self.name = name or f"{client.provider}:{client.model} ({side})"
        self._max_tokens = max_tokens
        self._temperature = temperature

    def _build_messages(
        self, sfen: str, legal: list[str], history: list[str]
    ) -> tuple[ChatMessage, ...]:
        system = _SYSTEM_PROMPT.format(side=self._side)
        lines = [
            f"You are {self._side}.",
            f"Position (SFEN): {sfen}",
        ]
        if history:
            lines.append("Moves so far (USI): " + " ".join(history))
        lines.append("Legal moves (USI): " + " ".join(legal))
        lines.append("Reply with exactly one USI move from the list above, nothing else.")
        return (
            ChatMessage("system", system),
            ChatMessage("user", "\n".join(lines)),
        )

    async def think(self, engine: Engine) -> ThinkResult:
        legal = engine.legal_moves_usi()
        if not legal:
            # 合法手ゼロ = 詰み等. ループが engine.is_terminated で処理する想定だが
            # 念のため resign を返す (fail-closed).
            return ThinkResult(
                move=None, resign=True, resign_reason="no legal moves available"
            )
        request = ChatRequest(
            messages=self._build_messages(engine.sfen, legal, engine.move_history_usi),
            model=self.model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        try:
            resp = await self._client.complete(request)
        except (LLMBackendError, LLMConfigError) as exc:
            return ThinkResult(
                move=None, resign=True, resign_reason=f"backend_error: {exc}"
            )

        # legal は上で非空を保証済み. 一致 USI が無ければ resign (fail-closed) —
        # ゴミ手を返して違法ストライクを浪費しない.
        usi = extract_move(resp.text, legal)
        if usi is None:
            return ThinkResult(
                move=None,
                resign=True,
                resign_reason=(
                    "LLM did not return a listed legal USI move; said: "
                    + _commentary(resp.text, "")
                ),
            )
        return ThinkResult(
            move=Move(
                usi=usi,
                thinking_ms=resp.latency_ms,
                commentary=_commentary(resp.text, usi),
                raw_response=resp.text,
            )
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _commentary(text: str, usi: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if s and s != usi:
            return s[:120]
    return ""


def make_shogi_llm_player(
    spec: str,
    *,
    side: str,
    config: LLMConfig | None = None,
    transport: HttpTransport | None = None,
) -> LLMShogiPlayer:
    """``"anthropic:claude-haiku-4-5"`` 等の spec から shogi LLM player を作る.

    ``config`` 省略時は ``LLMConfig.from_env()``. ``transport`` はテスト用 fake.
    設定不足は ``make_client`` が ``LLMConfigError`` を投げる (fail-closed).
    """
    from llove.llm.config import LLMConfig
    from llove.llm.factory import make_client

    cfg = config if config is not None else LLMConfig.from_env()
    client = make_client(spec, config=cfg, transport=transport)
    return LLMShogiPlayer(client, side=side)


__all__ = ["LLMShogiPlayer", "make_shogi_llm_player"]
