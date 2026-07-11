"""LLM backends scenario — real calls through :mod:`llove.llm`.

Historically this scenario replayed *synthetic* numbers. It now sends the
same prompt to every **configured** backend (anthropic / ollama / llmesh)
via :mod:`llove.llm` and reports **measured** latency / tokens / cost.

Fail-closed + honest (feedback_benchmark_honest_disclosure):

- a backend that raises ``LLMBackendError`` / ``LLMConfigError`` is reported
  as failed and skipped — one failure never aborts the whole scenario;
- when *no* backend is reachable the scenario says so and stops — it never
  substitutes synthetic numbers for real measurements;
- tokens / cost that the provider did not report are shown as ``N/A``,
  never fabricated.

Dependency injection: ``config`` and ``client_factory`` can be overridden so
tests drive the scenario through fake transports / fake clients without any
network access (see ``tests/test_llm_backends_scenario.py``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind
from llove.i18n import t
from llove.llm import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMBackendError,
    LLMClient,
    LLMConfig,
    LLMConfigError,
    make_client,
)

#: 全バックエンドに投げる共通プロンプト (旧合成版から据え置き).
_PROMPT = "Explain CUSUM control charts in 2 sentences."

#: narration に載せる応答本文の上限文字数 (パネルを溢れさせない).
_ANSWER_SNIPPET_CHARS = 300

#: ``client_factory`` の契約 — ``(spec, config) -> LLMClient``.
#: spec は "ollama" / "anthropic:claude-haiku-4-5" 等 (make_client と同じ).
ClientFactory = Callable[[str, LLMConfig], LLMClient]


def _default_client_factory(spec: str, config: LLMConfig) -> LLMClient:
    """既定 factory — :func:`llove.llm.make_client` をそのまま使う."""
    return make_client(spec, config=config)


def _fmt_count(v: int | None) -> str:
    """トークン数の表示. 取得不可 (None) は捏造せず N/A."""
    return str(v) if v is not None else "N/A"


def _fmt_cost(cost_usd: float | None) -> str:
    """コストの表示. 価格表に無い (None) は捏造せず N/A."""
    return f"${cost_usd:.6f}" if cost_usd is not None else "N/A"


def _snippet(text: str, limit: int = _ANSWER_SNIPPET_CHARS) -> str:
    """応答本文を narration 向けに切り詰める."""
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " …"


class LLMBackendsScenario(DemoScenario):
    """設定済みの全 LLM バックエンドに同一プロンプトを実送信して比較する."""

    name = "backends"
    i18n_key = "backends"
    default_pause = 0.6

    def __init__(
        self,
        *,
        config: LLMConfig | None = None,
        client_factory: ClientFactory | None = None,
        max_tokens: int = 160,
        temperature: float = 0.3,
    ) -> None:
        # config=None は「events() 実行時に環境変数から解決」— 構築時に
        # 環境を読まないことで, registry 経由の素の生成を安全に保つ.
        self._config = config
        self._client_factory: ClientFactory = client_factory or _default_client_factory
        self._max_tokens = max_tokens
        self._temperature = temperature

    # ------------------------------------------------------------------
    # script
    # ------------------------------------------------------------------

    async def events(self) -> AsyncIterator[Event]:
        config = self._config if self._config is not None else LLMConfig.from_env()
        providers = config.available_providers()

        yield narrate_key("scenario.backends.intro", title_key="scenario.backends.intro_title")
        yield narrate(
            t("scenario.backends.prompt", q=_PROMPT),
            title=t("scenario.backends.prompt_title"),
        )

        if not providers:
            # 現状 available_providers() は ollama を常に含むが, 設定側の
            # 進化に備えて fail-closed 分岐を明示しておく (偽データは出さない).
            yield narrate(
                t("scenario.backends.none_configured"),
                title=t("scenario.backends.none_configured_title"),
            )
            return

        messages = (ChatMessage("user", _PROMPT),)
        successes: list[ChatResponse] = []

        for provider in providers:
            try:
                client = self._client_factory(provider, config)
            except (LLMConfigError, LLMBackendError) as exc:
                # この provider だけ諦めて次へ (全体は止めない).
                yield self._failed(provider, str(exc))
                continue

            yield narrate(
                t("scenario.backends.calling", backend=client.provider, model=client.model),
                title=str(client.provider),
            )

            resp: ChatResponse | None = None
            error: str | None = None
            try:
                resp = await client.complete(
                    ChatRequest(
                        messages=messages,
                        model=client.model,
                        max_tokens=self._max_tokens,
                        temperature=self._temperature,
                    )
                )
            except (LLMBackendError, LLMConfigError) as exc:
                error = str(exc)
            finally:
                await client.aclose()

            if resp is None:
                yield self._failed(provider, error or "unknown error")
                continue

            successes.append(resp)
            yield Event(
                kind=EventKind.LLM_CALL,
                source_id=resp.provider,
                payload=self._call_payload(resp),
            )
            yield narrate(
                t(
                    "scenario.backends.result",
                    backend=resp.provider,
                    model=resp.model,
                    latency_ms=resp.latency_ms,
                    tokens=_fmt_count(resp.usage.total_tokens),
                    cost=_fmt_cost(resp.cost_usd),
                    answer=_snippet(resp.text),
                ),
                title=t("scenario.backends.result_title", backend=resp.provider),
            )

        if not successes:
            # 全滅 — honest に「到達不可」を宣言して終わる. 偽データは出さない.
            yield narrate(
                t("scenario.backends.all_failed"),
                title=t("scenario.backends.all_failed_title"),
            )
            return

        fastest = min(successes, key=lambda r: r.latency_ms)
        yield narrate(
            t(
                "scenario.backends.takeaway",
                ok=len(successes),
                total=len(providers),
                backend=fastest.provider,
                latency_ms=fastest.latency_ms,
            ),
            title=t("scenario.backends.takeaway_title"),
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _failed(provider: str, reason: str) -> Event:
        """provider 単体の失敗 narration (fail-closed だが全体は続行)."""
        return narrate(
            t("scenario.backends.failed", backend=provider, reason=reason),
            title=t("scenario.backends.failed_title", backend=provider),
        )

    @staticmethod
    def _call_payload(resp: ChatResponse) -> dict[str, Any]:
        """実測値のみで LLM_CALL payload を組む. 取得不可は None のまま (捏造しない)."""
        return {
            "backend": resp.provider,
            "model": resp.model,
            "tokens": resp.usage.total_tokens,
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "latency_ms": resp.latency_ms,
            "cost_usd": resp.cost_usd,
            "kind": "completion",
        }
