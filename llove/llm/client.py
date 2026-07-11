"""``LLMClient`` ABC + コスト推定.

全プロバイダ (anthropic / ollama / llmesh-peer) が実装する共通契約は 1 つ:

    class LLMClient(ABC):
        async def complete(self, request: ChatRequest) -> ChatResponse: ...

``async`` に統一するのは LoveApp が既に asyncio ループを回しており, 実
プロバイダは全て network-bound だから (:mod:`llove.games.base.player` と同じ
理由). 具象クラスは同期 transport を ``asyncio.to_thread`` で包んで実装する.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from llove.llm.transport import HttpTransport
from llove.llm.types import ChatRequest, ChatResponse, Usage

# ---------------------------------------------------------------------------
# コスト推定
# ---------------------------------------------------------------------------
#
# USD / 100 万トークン (input, output). あくまで **参考値** で価格改定により
# ずれる. 表に無いモデルは ``None`` を返す — 捏造しない
# (feedback_benchmark_honest_disclosure). ローカル (ollama / llmesh-peer) は
# 送電コスト以外ゼロなので 0.0 を明示.

PRICING_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic (参考値, 2026 時点の公表水準に基づく概算)
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-opus-4-8": (15.0, 75.0),
}

#: モデル名の family マッチ用フォールバック (完全一致に無いとき部分一致).
_FAMILY_PREFIXES: tuple[tuple[str, tuple[float, float]], ...] = (
    ("claude-haiku", (1.0, 5.0)),
    ("claude-sonnet", (3.0, 15.0)),
    ("claude-opus", (15.0, 75.0)),
)


def estimate_cost_usd(model: str, usage: Usage) -> float | None:
    """モデルと使用量から推定コスト (USD) を返す.

    価格表に無い / usage が欠けているなら ``None`` (捏造しない).
    ローカルプロバイダは価格 ``(0.0, 0.0)`` を登録しておけば 0.0 を返す.
    """
    rate = PRICING_USD_PER_MTOK.get(model)
    if rate is None:
        for prefix, r in _FAMILY_PREFIXES:
            if model.startswith(prefix):
                rate = r
                break
    if rate is None:
        return None
    if usage.input_tokens is None and usage.output_tokens is None:
        return None
    in_rate, out_rate = rate
    cost = (usage.input_tokens or 0) / 1_000_000 * in_rate
    cost += (usage.output_tokens or 0) / 1_000_000 * out_rate
    return round(cost, 6)


# ---------------------------------------------------------------------------
# LLMClient ABC
# ---------------------------------------------------------------------------


class LLMClient(ABC):
    """全 LLM プロバイダの async 基底クラス.

    具象は ``complete`` だけ実装すれば良い. ``provider`` / ``model`` は表示・
    audit 用に必ずセットする.
    """

    #: プロバイダ識別子 (``"anthropic"`` / ``"ollama"`` / ``"llmesh"``).
    provider: str = "?"
    #: モデル文字列.
    model: str = ""

    @abstractmethod
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """補完を 1 回行う.

        実装の責務:
        - HTTP 呼び出しは ``asyncio.to_thread`` で同期 transport を包む.
        - HTTP エラー / 空応答 / パース失敗は ``LLMBackendError`` を送出.
        - ``latency_ms`` / ``cost_usd`` を詰める (:func:`timed_call` が補助).
        """

    async def aclose(self) -> None:
        """HTTP クライアント等の後始末. デフォルト no-op."""


async def timed_call(
    fn: Callable[[], tuple[int, bytes]],
) -> tuple[int, bytes, int]:
    """同期 transport 呼び出しを別スレッドで実行し, レイテンシ(ms) を測る.

    戻り値 ``(status, body, latency_ms)``. ``time.perf_counter`` で計測.
    """
    import asyncio

    start = time.perf_counter()
    status, body = await asyncio.to_thread(fn)
    latency_ms = int((time.perf_counter() - start) * 1000)
    return status, body, latency_ms


def _unused_transport_hint(_t: HttpTransport) -> None:  # pragma: no cover
    """型 import を保持するためだけのダミー (mypy unused-import 回避)."""


__all__ = [
    "PRICING_USD_PER_MTOK",
    "LLMClient",
    "estimate_cost_usd",
    "timed_call",
]
