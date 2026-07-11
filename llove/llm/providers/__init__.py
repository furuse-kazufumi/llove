"""``llove.llm.providers`` — 具象 LLM プロバイダ実装.

通常は :func:`llove.llm.factory.make_client` 経由で解決する. 直接 import する
場合は各モジュールから (lazy import を活かすため ``providers/__init__`` では
再 export しない)::

    from llove.llm.providers.anthropic import AnthropicClient
    from llove.llm.providers.ollama import OllamaClient
    from llove.llm.providers.llmesh import LlmeshPeerClient
"""

from __future__ import annotations
