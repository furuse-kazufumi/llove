"""Anthropic Messages API プロバイダ (stdlib のみ, SDK 不使用).

``POST {base}/v1/messages`` を叩く. ``anthropic`` SDK を **敢えて使わない**:

- 依存ゼロを保つ (Apache-2.0 コア wheel を汚さない).
- mypy ``ignore_missing_imports=false`` 下でスタブ無し SDK が壊さない.
- transport DI で実 HTTP を踏まずにテストできる.

参考: https://docs.anthropic.com/en/api/messages
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from llove.llm.client import LLMClient, estimate_cost_usd, timed_call
from llove.llm.transport import HttpTransport, UrllibHttpTransport
from llove.llm.types import (
    ChatRequest,
    ChatResponse,
    LLMBackendError,
    Usage,
)

DEFAULT_ANTHROPIC_VERSION = "2023-06-01"


@dataclass
class AnthropicClient(LLMClient):
    """Anthropic Messages API クライアント."""

    model: str
    api_key: str
    base_url: str = "https://api.anthropic.com"
    anthropic_version: str = DEFAULT_ANTHROPIC_VERSION
    transport: HttpTransport = field(default_factory=UrllibHttpTransport)
    provider: str = field(default="anthropic", init=False)

    def _build_body(self, request: ChatRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [
                {"role": m.role, "content": m.content}
                for m in request.non_system_messages()
            ],
        }
        system = request.system_text()
        if system:
            body["system"] = system
        if request.stop:
            body["stop_sequences"] = list(request.stop)
        return body

    async def complete(self, request: ChatRequest) -> ChatResponse:
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        payload = json.dumps(self._build_body(request)).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
        }

        def _do() -> tuple[int, bytes]:
            return self.transport.request("POST", url, headers=headers, body=payload)

        status, body, latency_ms = await timed_call(_do)
        if status != 200:
            raise LLMBackendError(
                f"anthropic http_{status}: {_short(body)}"
            )
        try:
            doc = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LLMBackendError(f"anthropic json_parse_error: {exc}") from exc
        if not isinstance(doc, dict):
            raise LLMBackendError(
                f"anthropic unexpected_response_type: {type(doc).__name__}"
            )

        text = _extract_text(doc)
        usage = _extract_usage(doc)
        return ChatResponse(
            text=text,
            provider="anthropic",
            model=str(doc.get("model") or self.model),
            usage=usage,
            latency_ms=latency_ms,
            cost_usd=estimate_cost_usd(str(doc.get("model") or self.model), usage),
            raw=doc,
        )


def _extract_text(doc: dict[str, Any]) -> str:
    """``content`` 配列の text ブロックを連結する."""
    content = doc.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
    return "".join(parts)


def _extract_usage(doc: dict[str, Any]) -> Usage:
    raw = doc.get("usage")
    if not isinstance(raw, dict):
        return Usage()
    return Usage(
        input_tokens=_int_or_none(raw.get("input_tokens")),
        output_tokens=_int_or_none(raw.get("output_tokens")),
    )


def _int_or_none(v: Any) -> int | None:
    return int(v) if isinstance(v, int) else None


def _short(body: bytes, limit: int = 200) -> str:
    try:
        s = body.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover — decode with replace 済なので稀
        return "<undecodable>"
    return s[:limit]


__all__ = ["AnthropicClient", "DEFAULT_ANTHROPIC_VERSION"]
