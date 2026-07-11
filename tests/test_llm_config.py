"""``llove.llm.config.LLMConfig`` の単体テスト.

env 注入で純粋に検証する (os.environ を汚さない). 「設定済み ≠ 到達可能」の
区別が honest に保たれているかを重点的に確認する.
"""

from __future__ import annotations

import pytest

from llove.llm.config import (
    DEFAULT_ANTHROPIC_BASE_URL,
    DEFAULT_OLLAMA_BASE_URL,
    LLMConfig,
)
from llove.llm.types import LLMConfigError


def test_from_env_reads_anthropic_key() -> None:
    cfg = LLMConfig.from_env({"ANTHROPIC_API_KEY": "sk-test"})
    assert cfg.anthropic_api_key == "sk-test"
    assert cfg.anthropic_base_url == DEFAULT_ANTHROPIC_BASE_URL


def test_from_env_empty_and_whitespace_treated_as_unset() -> None:
    cfg = LLMConfig.from_env({"ANTHROPIC_API_KEY": "   "})
    assert cfg.anthropic_api_key is None
    assert cfg.status("anthropic").configured is False


def test_ollama_default_endpoint_and_always_configured() -> None:
    cfg = LLMConfig.from_env({})
    assert cfg.ollama_base_url == DEFAULT_OLLAMA_BASE_URL
    st = cfg.status("ollama")
    assert st.configured is True
    assert st.has_api_key is False


def test_ollama_host_env_precedence() -> None:
    # OLLAMA_HOST が LLOVE_OLLAMA_URL より優先.
    cfg = LLMConfig.from_env(
        {"OLLAMA_HOST": "http://box:11434", "LLOVE_OLLAMA_URL": "http://other:1"}
    )
    assert cfg.ollama_base_url == "http://box:11434"


def test_ollama_fallback_env() -> None:
    cfg = LLMConfig.from_env({"LLOVE_OLLAMA_URL": "http://other:1"})
    assert cfg.ollama_base_url == "http://other:1"


def test_anthropic_not_configured_without_key() -> None:
    cfg = LLMConfig.from_env({})
    st = cfg.status("anthropic")
    assert st.configured is False
    assert "ANTHROPIC_API_KEY" in st.reason


def test_llmesh_configured_only_with_url() -> None:
    assert LLMConfig.from_env({}).status("llmesh").configured is False
    cfg = LLMConfig.from_env({"LLMESH_PEER_URL": "http://peer:8080"})
    st = cfg.status("llmesh")
    assert st.configured is True
    assert st.base_url == "http://peer:8080"


def test_available_providers_stable_order() -> None:
    cfg = LLMConfig.from_env(
        {"ANTHROPIC_API_KEY": "k", "LLMESH_PEER_URL": "http://p:1"}
    )
    # ollama は常に含まれる. 順序は anthropic, ollama, llmesh で安定.
    assert cfg.available_providers() == ["anthropic", "ollama", "llmesh"]


def test_available_providers_minimal_env_has_only_ollama() -> None:
    assert LLMConfig.from_env({}).available_providers() == ["ollama"]


def test_require_raises_when_unconfigured() -> None:
    cfg = LLMConfig.from_env({})
    with pytest.raises(LLMConfigError, match="anthropic is not configured"):
        cfg.require("anthropic")


def test_require_returns_status_when_ok() -> None:
    cfg = LLMConfig.from_env({"ANTHROPIC_API_KEY": "k"})
    st = cfg.require("anthropic")
    assert st.provider == "anthropic"
    assert st.configured is True


def test_status_unknown_provider_raises() -> None:
    with pytest.raises(LLMConfigError, match="unknown provider"):
        LLMConfig.from_env({}).status("gpt5")
