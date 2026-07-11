"""LLM チャット連携の共通データ型 + エラー階層.

``llove.llm`` の背骨. プロバイダ (anthropic / ollama / llmesh-peer) は
すべてこの ``ChatRequest`` を受け ``ChatResponse`` を返す — 呼び出し側
(ゲームプレイヤ / シナリオ / パレット) はプロバイダ差を知らずに済む.

設計の柱:

- **frozen dataclass** — リクエスト/レスポンスは不変. audit ログに乗せても
  後から書き換わらない (棋譜署名と同じ思想, :mod:`llove.games.base.types`).
- **stdlib のみ** — 外部 SDK に依存しない. HTTP は :mod:`llove.llm.transport`
  が stdlib ``urllib`` で行う.
- **fail-closed** — 設定不足 (``LLMConfigError``) と実行時失敗
  (``LLMBackendError``) を型で分ける. 呼び出し側は前者を「使えない」後者を
  「使えるはずが失敗した」と区別してハンドルできる.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# エラー階層
# ---------------------------------------------------------------------------


class LLMError(Exception):
    """``llove.llm`` の基底例外."""


class LLMConfigError(LLMError):
    """設定不足 — API キー欠如 / エンドポイント未設定 / 未知プロバイダ.

    「そもそもこのバックエンドは使えない」を表す. TUI はこれを捕まえて
    「ANTHROPIC_API_KEY を設定してください」等の案内に落とす (凍結させない).
    """


class LLMBackendError(LLMError):
    """実行時失敗 — HTTP エラー / JSON パース失敗 / 接続不可 / 空応答.

    「使えるはずのバックエンドが呼び出しに失敗した」を表す. ゲームプレイヤは
    これを捕まえて resign に落とす (ループを巻き込まない).
    """


# ---------------------------------------------------------------------------
# メッセージ / リクエスト
# ---------------------------------------------------------------------------

#: 許容ロール. anthropic は system を別フィールドに, ollama/OpenAI 互換は
#: messages 内に置く — プロバイダ側で正規化する.
VALID_ROLES = ("system", "user", "assistant")


@dataclass(frozen=True)
class ChatMessage:
    """1 メッセージ (role + content).

    ``role`` は ``"system"`` / ``"user"`` / ``"assistant"`` のいずれか.
    範囲外は ``__post_init__`` で ``LLMConfigError`` (プログラミングエラー扱い).
    """

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in VALID_ROLES:
            raise LLMConfigError(
                f"invalid message role {self.role!r}; must be one of {VALID_ROLES}"
            )


@dataclass(frozen=True)
class ChatRequest:
    """プロバイダ非依存の補完リクエスト.

    Fields
    ------
    messages
        会話履歴. 先頭に ``system`` ロールを 1 つ置ける (プロバイダが適切な
        場所へ振り分ける). ``user`` / ``assistant`` が交互でなくても各
        プロバイダが許す限り通す (検証はプロバイダ責務).
    model
        モデル文字列 (``"claude-haiku-4-5"`` / ``"llama3.2"`` / ...).
    max_tokens
        出力上限. ゲーム着手は短いので既定は控えめ.
    temperature
        0.0 = 決定的寄り. ゲームでは低め, 会話では高めが自然.
    stop
        停止文字列. 空タプルなら送らない.
    """

    messages: tuple[ChatMessage, ...]
    model: str
    max_tokens: int = 512
    temperature: float = 0.7
    stop: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.messages:
            raise LLMConfigError("ChatRequest.messages must not be empty")
        if self.max_tokens <= 0:
            raise LLMConfigError(f"max_tokens must be positive, got {self.max_tokens}")

    def system_text(self) -> str:
        """先頭 system メッセージの content (無ければ空文字)."""
        first = self.messages[0]
        return first.content if first.role == "system" else ""

    def non_system_messages(self) -> tuple[ChatMessage, ...]:
        """system を除いた本文メッセージ列."""
        return tuple(m for m in self.messages if m.role != "system")


# ---------------------------------------------------------------------------
# 使用量 / レスポンス
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Usage:
    """トークン使用量. 取れなければ ``None`` (捏造しない)."""

    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


@dataclass(frozen=True)
class ChatResponse:
    """プロバイダ非依存の補完レスポンス.

    Fields
    ------
    text
        モデルの生成テキスト (連結済み).
    provider / model
        どのバックエンド・モデルが答えたか (audit / 表示用).
    usage
        トークン使用量 (取れなければ ``None`` 内包).
    latency_ms
        実測レイテンシ (ms). 呼び出し側で計測して詰める.
    cost_usd
        推定コスト. 価格表に無いモデルは ``None`` (捏造しない).
    raw
        パース済みレスポンス全文 (audit / debug 用).
    """

    text: str
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    cost_usd: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "VALID_ROLES",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "LLMBackendError",
    "LLMConfigError",
    "LLMError",
    "Usage",
]
