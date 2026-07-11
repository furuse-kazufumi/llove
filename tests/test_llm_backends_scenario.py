"""実呼び出し版 LLM backends シナリオのテスト (fail-closed / honest).

fake transport / fake client の DI でネットワークを踏まずに検証する:

- 成功時は **実測** の latency / tokens / cost が LLM_CALL payload に乗る
  (旧実装の合成 3 件は出ない).
- 全 provider 失敗時は偽データを一切出さず, honest な「到達不可」narration
  で終わる (feedback_benchmark_honest_disclosure).
- usage / cost が取れない provider は N/A 表示で捏造しない.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.demo.scenarios.backends import LLMBackendsScenario
from llove.events import Event, EventKind
from llove.i18n import active_locale, set_locale, t
from llove.llm import (
    ChatRequest,
    ChatResponse,
    LLMClient,
    LLMConfig,
    Usage,
    make_client,
    make_fake_http_transport,
)

# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

_ANSWER = "CUSUM charts accumulate small deviations from a target to detect drift early."

OLLAMA_OK = json.dumps(
    {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": _ANSWER},
        "prompt_eval_count": 40,
        "eval_count": 12,
        "done": True,
    }
).encode()


async def _run(scenario: LLMBackendsScenario) -> list[Event]:
    scenario.default_pause = 0.0
    return [ev async for ev in scenario.events()]


def _narrations(seen: list[Event]) -> list[str]:
    return [e.payload.get("text", "") for e in seen if e.kind == EventKind.NARRATION]


def _llm_calls(seen: list[Event]) -> list[Event]:
    return [e for e in seen if e.kind == EventKind.LLM_CALL]


def _factory_with_transport(handler: Any) -> Any:
    """実 factory (make_client) を fake transport 付きで使う client_factory."""

    def factory(spec: str, config: LLMConfig) -> LLMClient:
        return make_client(spec, config=config, transport=make_fake_http_transport(handler))

    return factory


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def test_backends_registered() -> None:
    assert SCENARIOS.get("backends") is LLMBackendsScenario
    assert isinstance(get_scenario("backends"), LLMBackendsScenario)


# ---------------------------------------------------------------------------
# 成功パス: 実測値が LLM_CALL に乗る
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_single_provider_success_emits_measured_llm_call() -> None:
    """env 空 = ollama のみ設定済. fake 応答の実測値が payload と narration に出る."""

    def handler(method: str, url: str, headers: dict[str, str], body: bytes | None):
        assert method == "POST"
        assert url.endswith("/api/chat")
        return 200, OLLAMA_OK

    scenario = LLMBackendsScenario(
        config=LLMConfig.from_env({}),
        client_factory=_factory_with_transport(handler),
    )
    seen = await _run(scenario)

    calls = _llm_calls(seen)
    assert len(calls) == 1  # ollama のみ — 旧実装の合成 3 件ではない
    payload = calls[0].payload
    assert payload["backend"] == "ollama"
    assert payload["model"] == "llama3.2"
    assert payload["tokens"] == 52  # 40 + 12 (fake 応答由来の実測)
    assert payload["input_tokens"] == 40
    assert payload["output_tokens"] == 12
    assert isinstance(payload["latency_ms"], int) and payload["latency_ms"] >= 0
    assert payload["cost_usd"] == 0.0  # ローカルは 0.0 明示 (None ではない)
    assert payload["kind"] == "completion"

    texts = _narrations(seen)
    # 応答本文 (LLM の実出力) が narration に載る
    assert any(_ANSWER[:30] in n for n in texts)
    # takeaway は成功 1/1 で実測 latency を報告する
    expected_takeaway = t(
        "scenario.backends.takeaway",
        ok=1,
        total=1,
        backend="ollama",
        latency_ms=payload["latency_ms"],
    )
    assert expected_takeaway in texts


@pytest.mark.asyncio
async def test_partial_failure_skips_only_failed_provider() -> None:
    """anthropic が 500 でも ollama は成功し, 全体は止まらない."""

    def handler(method: str, url: str, headers: dict[str, str], body: bytes | None):
        if url.endswith("/v1/messages"):
            return 500, b'{"error":"overloaded"}'
        return 200, OLLAMA_OK

    config = LLMConfig.from_env({"ANTHROPIC_API_KEY": "test-key"})
    assert config.available_providers() == ["anthropic", "ollama"]
    scenario = LLMBackendsScenario(
        config=config, client_factory=_factory_with_transport(handler)
    )
    seen = await _run(scenario)

    calls = _llm_calls(seen)
    assert [c.payload["backend"] for c in calls] == ["ollama"]  # anthropic は乗らない
    texts = _narrations(seen)
    # anthropic の失敗は理由付きで正直に表示される
    assert any("anthropic http_500" in n for n in texts)
    # takeaway は 1/2 (成功分のみ)
    expected_takeaway = t(
        "scenario.backends.takeaway",
        ok=1,
        total=2,
        backend="ollama",
        latency_ms=calls[0].payload["latency_ms"],
    )
    assert expected_takeaway in texts


# ---------------------------------------------------------------------------
# fail-closed: 全滅時に偽データを出さない
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_providers_failing_is_fail_closed() -> None:
    """env 空 (= ollama のみ) + 500 応答 → LLM_CALL ゼロ + honest な到達不可宣言."""

    def handler(method: str, url: str, headers: dict[str, str], body: bytes | None):
        return 500, b'{"error":"down"}'

    scenario = LLMBackendsScenario(
        config=LLMConfig.from_env({}),
        client_factory=_factory_with_transport(handler),
    )
    seen = await _run(scenario)

    assert _llm_calls(seen) == []  # 偽データ無し
    texts = _narrations(seen)
    assert t("scenario.backends.all_failed") in texts  # honest な到達不可 narration
    assert any("ollama http_500" in n for n in texts)  # 個別失敗も理由付きで表示
    # 旧実装の合成 latency (1840/540/720 ms) がどこにも復活していない
    joined = " ".join(texts)
    for fabricated in ("1840", "540", "720"):
        assert fabricated not in joined


@pytest.mark.asyncio
async def test_no_configured_provider_is_fail_closed() -> None:
    """available_providers() が空を返す設定でも偽データ無しで honest に終わる."""

    class _EmptyConfig(LLMConfig):
        def available_providers(self) -> list[str]:
            return []

    def _boom(spec: str, config: LLMConfig) -> LLMClient:
        raise AssertionError("client_factory must not be called when nothing is configured")

    scenario = LLMBackendsScenario(config=_EmptyConfig(), client_factory=_boom)
    seen = await _run(scenario)

    assert _llm_calls(seen) == []
    assert t("scenario.backends.none_configured") in _narrations(seen)


# ---------------------------------------------------------------------------
# DI: fake client 注入 + N/A 表示 (捏造しない)
# ---------------------------------------------------------------------------


class _CannedClient(LLMClient):
    """complete() が固定 ChatResponse を返すテスト用クライアント."""

    def __init__(self, resp: ChatResponse) -> None:
        self.provider = resp.provider
        self.model = resp.model
        self._resp = resp
        self.closed = False

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return self._resp

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_client_factory_di_and_na_display_for_missing_usage() -> None:
    """client_factory DI で fake client を注入. usage/cost 不明は N/A 表示."""
    resp = ChatResponse(
        text="hello from fake",
        provider="ollama",
        model="mystery-model",
        usage=Usage(),  # tokens 取得不可
        latency_ms=7,
        cost_usd=None,  # 価格表に無い
    )
    canned = _CannedClient(resp)
    received: list[tuple[str, LLMConfig]] = []

    def factory(spec: str, config: LLMConfig) -> LLMClient:
        received.append((spec, config))
        return canned

    config = LLMConfig.from_env({})
    scenario = LLMBackendsScenario(config=config, client_factory=factory)
    seen = await _run(scenario)

    assert received == [("ollama", config)]  # spec と config が factory に渡る
    assert canned.closed  # aclose が呼ばれる

    calls = _llm_calls(seen)
    assert len(calls) == 1
    payload = calls[0].payload
    assert payload["tokens"] is None  # 捏造しない
    assert payload["cost_usd"] is None
    assert payload["latency_ms"] == 7

    texts = _narrations(seen)
    assert any("tokens: N/A" in n for n in texts)
    assert any("cost: N/A" in n for n in texts)


# ---------------------------------------------------------------------------
# i18n: en / ja 両方でキーが解決される
# ---------------------------------------------------------------------------


def test_backends_i18n_resolves_under_en_and_ja() -> None:
    keys = (
        "title",
        "description",
        "intro",
        "prompt",
        "calling",
        "result",
        "result_title",
        "failed",
        "failed_title",
        "none_configured",
        "all_failed",
        "takeaway",
    )
    orig = active_locale()
    try:
        for loc in ("en", "ja"):
            set_locale(loc)
            for key in keys:
                full = f"scenario.backends.{key}"
                assert t(full) != full, (loc, key)  # 未定義ならキーがそのまま返る
    finally:
        set_locale(orig)
