"""環境変数から LLM バックエンド設定を解決する (fail-closed).

llove は公開 OSS なので **秘密情報をコードに埋めない**. API キー・
エンドポイントは環境変数からのみ読む (既存の ``LLOVE_*`` / ``XDG_*``
規約と一致):

- ``ANTHROPIC_API_KEY``            — anthropic (必須, 無ければ anthropic 使用不可)
- ``ANTHROPIC_BASE_URL``           — anthropic ゲートウェイ差し替え (任意)
- ``OLLAMA_HOST`` / ``LLOVE_OLLAMA_URL`` — ローカル ollama (既定 http://localhost:11434)
- ``LLMESH_PEER_URL`` / ``LLOVE_LLMESH_URL`` — llmesh peer OpenAI 互換ゲートウェイ
- ``LLMESH_PEER_API_KEY``          — llmesh peer 認証 (任意)

``available_providers`` は「静的設定が満たされているか」を返す —
**到達可能性 (endpoint が実際に生きているか) は保証しない**. 疎通は呼び出し
時に判明し, 失敗は ``LLMBackendError`` で fail-closed に扱う. ollama は既定
localhost を持つので常に「設定済み」だが, 実際に起動しているかは呼んで初めて
分かる (この区別を honest に保つ).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from llove.llm.transport import DEFAULT_TIMEOUT_S
from llove.llm.types import LLMConfigError

DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

#: 静的設定だけで使える (キー不要な) プロバイダ.
_KEYLESS_PROVIDERS = ("ollama",)


@dataclass(frozen=True)
class ProviderStatus:
    """1 プロバイダの設定状態.

    ``configured`` は「静的に呼べる準備が整っているか」で, 疎通の可否では
    ない (:mod:`llove.llm.config` の docstring 参照).
    """

    provider: str
    configured: bool
    reason: str
    base_url: str
    has_api_key: bool


@dataclass(frozen=True)
class LLMConfig:
    """LLM バックエンド設定のスナップショット (env から構築).

    不変. テストは ``from_env(env={...})`` で環境を注入できる.
    """

    anthropic_api_key: str | None = None
    anthropic_base_url: str = DEFAULT_ANTHROPIC_BASE_URL
    ollama_base_url: str = DEFAULT_OLLAMA_BASE_URL
    llmesh_base_url: str | None = None
    llmesh_api_key: str | None = None

    # -------- 構築 --------

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> LLMConfig:
        """環境変数 (既定 ``os.environ``) から設定を構築する."""
        e = env if env is not None else dict(os.environ)

        def _clean(*keys: str) -> str | None:
            for k in keys:
                v = e.get(k, "").strip()
                if v:
                    return v
            return None

        return cls(
            anthropic_api_key=_clean("ANTHROPIC_API_KEY"),
            anthropic_base_url=_clean("ANTHROPIC_BASE_URL") or DEFAULT_ANTHROPIC_BASE_URL,
            ollama_base_url=_clean("OLLAMA_HOST", "LLOVE_OLLAMA_URL") or DEFAULT_OLLAMA_BASE_URL,
            llmesh_base_url=_clean("LLMESH_PEER_URL", "LLOVE_LLMESH_URL"),
            llmesh_api_key=_clean("LLMESH_PEER_API_KEY"),
        )

    # -------- 状態照会 --------

    def status(self, provider: str) -> ProviderStatus:
        """指定プロバイダの設定状態を返す (未知プロバイダは ``LLMConfigError``)."""
        p = provider.lower()
        if p == "anthropic":
            ok = self.anthropic_api_key is not None
            return ProviderStatus(
                provider="anthropic",
                configured=ok,
                reason="ready" if ok else "ANTHROPIC_API_KEY not set",
                base_url=self.anthropic_base_url,
                has_api_key=ok,
            )
        if p == "ollama":
            return ProviderStatus(
                provider="ollama",
                configured=True,
                reason=f"local endpoint {self.ollama_base_url}",
                base_url=self.ollama_base_url,
                has_api_key=False,
            )
        if p == "llmesh":
            ok = self.llmesh_base_url is not None
            return ProviderStatus(
                provider="llmesh",
                configured=ok,
                reason="ready" if ok else "LLMESH_PEER_URL not set",
                base_url=self.llmesh_base_url or "",
                has_api_key=self.llmesh_api_key is not None,
            )
        raise LLMConfigError(
            f"unknown provider {provider!r}; known: anthropic, ollama, llmesh"
        )

    def available_providers(self) -> list[str]:
        """静的設定が満たされているプロバイダ名を安定順で返す.

        「到達可能」ではなく「設定済み」. ollama は常に含まれる (既定 localhost).
        """
        out: list[str] = []
        for p in ("anthropic", "ollama", "llmesh"):
            if self.status(p).configured:
                out.append(p)
        return out

    def require(self, provider: str) -> ProviderStatus:
        """設定済みでなければ ``LLMConfigError`` を投げて状態を返す (fail-closed)."""
        st = self.status(provider)
        if not st.configured:
            raise LLMConfigError(f"{provider} is not configured: {st.reason}")
        return st


__all__ = [
    "DEFAULT_ANTHROPIC_BASE_URL",
    "DEFAULT_OLLAMA_BASE_URL",
    "LLMConfig",
    "ProviderStatus",
]
