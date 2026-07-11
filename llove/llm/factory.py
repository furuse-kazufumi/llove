"""``provider:model`` spec を具象 :class:`LLMClient` に解決する.

:func:`llove.shogi.players.base.parse_provider_spec` の汎用版. lazy import で
プロバイダモジュールを必要時のみ読む (mock しか使わないなら anthropic 由来の
コードにも触れない).

例::

    cfg = LLMConfig.from_env()
    client = make_client("anthropic:claude-haiku-4-5", config=cfg)
    client = make_client("ollama:llama3.2", config=cfg)
    client = make_client("llmesh:my-model", config=cfg)
"""

from __future__ import annotations

from typing import Any

from llove.llm.client import LLMClient
from llove.llm.config import LLMConfig
from llove.llm.transport import HttpTransport, UrllibHttpTransport
from llove.llm.types import LLMConfigError

KNOWN_PROVIDERS = ("anthropic", "ollama", "llmesh")

#: model 未指定時の既定モデル.
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "ollama": "llama3.2",
    "llmesh": "default",
}


def parse_llm_spec(spec: str) -> tuple[str, str]:
    """``"provider:model"`` を ``(provider, model)`` に分ける.

    model は ``:`` を含んでよい (``ollama:llama3:70b`` → ``("ollama","llama3:70b")``).
    provider 省略時 (``:`` 無し) は model を既定に落とす. 未知 provider は
    ``LLMConfigError``.
    """
    if ":" in spec:
        provider, model = spec.split(":", 1)
    else:
        provider, model = spec, ""
    provider = provider.strip().lower()
    model = model.strip()
    if provider not in KNOWN_PROVIDERS:
        known = ", ".join(KNOWN_PROVIDERS)
        raise LLMConfigError(
            f"unknown provider {provider!r}. Known: {known}. "
            "Use e.g. 'anthropic:claude-haiku-4-5' / 'ollama:llama3.2' / 'llmesh:<model>'."
        )
    if not model:
        model = DEFAULT_MODELS[provider]
    return provider, model


def make_client(
    spec: str,
    *,
    config: LLMConfig,
    transport: HttpTransport | None = None,
) -> LLMClient:
    """spec を具象クライアントに解決する (設定不足は ``LLMConfigError``).

    ``transport`` を渡すとテスト用 fake に差し替えられる. 省略時は
    ``config.request_timeout_s`` (env ``LLOVE_LLM_TIMEOUT`` で調整可) を反映した
    ``UrllibHttpTransport`` を組む — 大型ローカルモデルのコールドロードに備える.
    """
    provider, model = parse_llm_spec(spec)
    tr: HttpTransport = (
        transport
        if transport is not None
        else UrllibHttpTransport(timeout=config.request_timeout_s)
    )

    if provider == "anthropic":
        st = config.require("anthropic")
        from llove.llm.providers.anthropic import AnthropicClient

        assert config.anthropic_api_key is not None  # require() が保証
        return AnthropicClient(
            model=model,
            api_key=config.anthropic_api_key,
            base_url=st.base_url,
            transport=tr,
        )

    if provider == "ollama":
        st = config.require("ollama")
        from llove.llm.providers.ollama import OllamaClient

        return OllamaClient(model=model, base_url=st.base_url, transport=tr)

    if provider == "llmesh":
        st = config.require("llmesh")
        from llove.llm.providers.llmesh import LlmeshPeerClient

        return LlmeshPeerClient(
            model=model,
            base_url=st.base_url,
            api_key=config.llmesh_api_key,
            transport=tr,
        )

    raise LLMConfigError(f"no factory for provider {provider!r}")  # pragma: no cover


__all__ = ["DEFAULT_MODELS", "KNOWN_PROVIDERS", "make_client", "parse_llm_spec"]
