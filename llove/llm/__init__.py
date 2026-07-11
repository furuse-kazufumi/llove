"""``llove.llm`` — プロバイダ非依存の LLM チャット連携.

llove の合成デモを卒業させ, 実バックエンド (anthropic / ollama / llmesh peer)
を games / scenario / palette に配線するための共通基盤. stdlib のみ・
transport DI・fail-closed.

    from llove.llm import LLMConfig, make_client, ChatMessage, ChatRequest

    cfg = LLMConfig.from_env()
    client = make_client("ollama:llama3.2", config=cfg)
    resp = await client.complete(
        ChatRequest(messages=(ChatMessage("user", "hello"),), model=client.model)
    )
"""

from __future__ import annotations

from llove.llm.client import (
    PRICING_USD_PER_MTOK,
    LLMClient,
    estimate_cost_usd,
    timed_call,
)
from llove.llm.config import (
    DEFAULT_ANTHROPIC_BASE_URL,
    DEFAULT_OLLAMA_BASE_URL,
    LLMConfig,
    ProviderStatus,
)
from llove.llm.factory import (
    DEFAULT_MODELS,
    KNOWN_PROVIDERS,
    make_client,
    parse_llm_spec,
)
from llove.llm.transport import (
    HttpTransport,
    UrllibHttpTransport,
    make_fake_http_transport,
)
from llove.llm.types import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    LLMBackendError,
    LLMConfigError,
    LLMError,
    Usage,
)

__all__ = [
    "DEFAULT_ANTHROPIC_BASE_URL",
    "DEFAULT_MODELS",
    "DEFAULT_OLLAMA_BASE_URL",
    "KNOWN_PROVIDERS",
    "PRICING_USD_PER_MTOK",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "HttpTransport",
    "LLMBackendError",
    "LLMClient",
    "LLMConfig",
    "LLMConfigError",
    "LLMError",
    "ProviderStatus",
    "UrllibHttpTransport",
    "Usage",
    "estimate_cost_usd",
    "make_client",
    "make_fake_http_transport",
    "parse_llm_spec",
    "timed_call",
]
