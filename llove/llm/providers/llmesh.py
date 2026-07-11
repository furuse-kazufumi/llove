"""llmesh peer プロバイダ — OpenAI 互換 chat completions (stdlib のみ).

FullSense の on-prem LLM ハブ llmesh は OpenAI 互換ゲートウェイを提供する
(LLM ハブの事実上の標準). ``POST {base}/v1/chat/completions`` を叩く.
同じクライアントは LM Studio / vLLM / OpenAI 本体など OpenAI 互換な任意の
エンドポイントにも使える.

honest 注記
-----------
本クライアントは OpenAI 互換スキーマに対する fake transport 単体テストで
検証済み. ただし **稼働中の llmesh に対する live 疎通は本セッションでは
未検証** — llmesh の chat エンドポイント形状が将来変わる可能性がある
(feedback_benchmark_honest_disclosure に従い誇張しない).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from llove.llm.client import LLMClient, estimate_cost_usd, timed_call
from llove.llm.transport import HttpTransport, UrllibHttpTransport
from llove.llm.types import ChatRequest, ChatResponse, LLMBackendError, Usage


@dataclass
class LlmeshPeerClient(LLMClient):
    """OpenAI 互換 ``/v1/chat/completions`` クライアント (llmesh peer 既定)."""

    model: str
    base_url: str
    api_key: str | None = None
    #: provider タグ. 既定 ``"llmesh"`` だが OpenAI 互換なら差し替え可.
    provider: str = "llmesh"
    transport: HttpTransport = field(default_factory=UrllibHttpTransport)

    def _build_body(self, request: ChatRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.stop:
            body["stop"] = list(request.stop)
        return body

    async def complete(self, request: ChatRequest) -> ChatResponse:
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        payload = json.dumps(self._build_body(request)).encode("utf-8")
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"

        def _do() -> tuple[int, bytes]:
            return self.transport.request("POST", url, headers=headers, body=payload)

        status, body, latency_ms = await timed_call(_do)
        if status != 200:
            raise LLMBackendError(f"{self.provider} http_{status}: {_short(body)}")
        try:
            doc = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LLMBackendError(f"{self.provider} json_parse_error: {exc}") from exc
        if not isinstance(doc, dict):
            raise LLMBackendError(
                f"{self.provider} unexpected_response_type: {type(doc).__name__}"
            )

        text = _extract_text(doc)
        usage = _extract_usage(doc)
        model = str(doc.get("model") or self.model)
        return ChatResponse(
            text=text,
            provider=self.provider,
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            # peer は on-prem 前提なので既定 0.0. クラウド OpenAI 互換に使う場合は
            # 価格表に載っていれば estimate 側で拾える — ここでは既知価格を優先.
            cost_usd=estimate_cost_usd(model, usage) if _looks_priced(model) else 0.0,
            raw=doc,
        )


def _looks_priced(model: str) -> bool:
    """価格表に載りうるモデル (claude-*) かの粗い判定."""
    return model.startswith("claude-")


def _extract_text(doc: dict[str, Any]) -> str:
    choices = doc.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message")
    if isinstance(msg, dict):
        return str(msg.get("content", ""))
    # 一部互換実装は ``text`` を直接返す (completions 系).
    if isinstance(first.get("text"), str):
        return str(first["text"])
    return ""


def _extract_usage(doc: dict[str, Any]) -> Usage:
    raw = doc.get("usage")
    if not isinstance(raw, dict):
        return Usage()
    return Usage(
        input_tokens=_int_or_none(raw.get("prompt_tokens")),
        output_tokens=_int_or_none(raw.get("completion_tokens")),
    )


def _int_or_none(v: Any) -> int | None:
    return int(v) if isinstance(v, int) else None


def _short(body: bytes, limit: int = 200) -> str:
    return body.decode("utf-8", errors="replace")[:limit]


__all__ = ["LlmeshPeerClient"]
