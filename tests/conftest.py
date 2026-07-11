"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from llove.i18n import set_locale
from llove.sources.mock import MockSource


@pytest.fixture(autouse=True)
def _force_en_locale():
    """All tests use the 'en' locale unless they opt out explicitly.

    This keeps assertions on literal strings stable on JP-locale dev machines.
    """
    set_locale("en")
    yield
    set_locale("en")


@pytest.fixture
def mock_source() -> MockSource:
    """Deterministic mock source for unit tests."""
    return MockSource(seed=42, tick_seconds=0.001)


@pytest.fixture
def llm_backends_offline():
    """Patcher that pins the (real-call) backends scenario to offline fakes.

    The backends scenario now performs *real* LLM calls via ``llove.llm``.
    Suite-wide smoke tests must never touch the network (or spend API money),
    so they call this patcher on the scenario instance to inject an
    empty-env config plus a canned fake client. Detailed behaviour is
    covered separately in ``tests/test_llm_backends_scenario.py``.
    """
    from llove.llm import ChatRequest, ChatResponse, LLMConfig, Usage
    from llove.llm.client import LLMClient

    class _FakeClient(LLMClient):
        def __init__(self, provider: str) -> None:
            self.provider = provider
            self.model = "fake-model"

        async def complete(self, request: ChatRequest) -> ChatResponse:
            return ChatResponse(
                text="stub answer (offline test)",
                provider=self.provider,
                model=self.model,
                usage=Usage(input_tokens=1, output_tokens=1),
                latency_ms=1,
                cost_usd=0.0,
            )

    def _factory(spec: str, config: LLMConfig) -> LLMClient:
        return _FakeClient(spec.split(":", 1)[0])

    def _patch(scenario) -> None:
        scenario._config = LLMConfig.from_env({})  # ollama only, no real env leakage
        scenario._client_factory = _factory

    return _patch
