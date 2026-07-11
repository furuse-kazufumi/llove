"""Ollama ローカルプロバイダ (stdlib のみ).

``POST {base}/api/chat`` (``stream=false``) を叩く. ローカル完結・キー不要・
ネットワーク送出ゼロ — FullSense の「Local こそ AI の本来の居場所」に最も
沿うバックエンド. usage は ``prompt_eval_count`` (入力) / ``eval_count``
(出力) から取る.

参考: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from llove.llm.client import LLMClient, estimate_cost_usd, timed_call
from llove.llm.transport import HttpTransport, UrllibHttpTransport
from llove.llm.types import ChatRequest, ChatResponse, LLMBackendError, Usage


@dataclass
class OllamaClient(LLMClient):
    """Ollama ``/api/chat`` クライアント (ローカル)."""

    model: str
    base_url: str = "http://localhost:11434"
    transport: HttpTransport = field(default_factory=UrllibHttpTransport)
    provider: str = field(default="ollama", init=False)

    def _build_body(self, request: ChatRequest) -> dict[str, Any]:
        options: dict[str, Any] = {"temperature": request.temperature}
        # num_predict = 出力上限 (Ollama の名称).
        options["num_predict"] = request.max_tokens
        if request.stop:
            options["stop"] = list(request.stop)
        return {
            "model": self.model,
            # system は role="system" のメッセージとしてそのまま渡す.
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ],
            "stream": False,
            "options": options,
        }

    async def complete(self, request: ChatRequest) -> ChatResponse:
        url = f"{self.base_url.rstrip('/')}/api/chat"
        payload = json.dumps(self._build_body(request)).encode("utf-8")
        headers = {"content-type": "application/json"}

        def _do() -> tuple[int, bytes]:
            return self.transport.request("POST", url, headers=headers, body=payload)

        status, body, latency_ms = await timed_call(_do)
        if status != 200:
            raise LLMBackendError(f"ollama http_{status}: {_short(body)}")
        try:
            doc = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise LLMBackendError(f"ollama json_parse_error: {exc}") from exc
        if not isinstance(doc, dict):
            raise LLMBackendError(
                f"ollama unexpected_response_type: {type(doc).__name__}"
            )

        text = _extract_text(doc)
        usage = Usage(
            input_tokens=_int_or_none(doc.get("prompt_eval_count")),
            output_tokens=_int_or_none(doc.get("eval_count")),
        )
        model = str(doc.get("model") or self.model)
        return ChatResponse(
            text=text,
            provider="ollama",
            model=model,
            usage=usage,
            latency_ms=latency_ms,
            # ローカルは金銭コスト 0.0 を明示 (未知価格の None とは区別).
            cost_usd=0.0,
            raw=doc,
        )


def _extract_text(doc: dict[str, Any]) -> str:
    msg = doc.get("message")
    if isinstance(msg, dict):
        return str(msg.get("content", ""))
    # 一部バージョンは非 chat の ``response`` を返すことがある — 後方互換.
    if isinstance(doc.get("response"), str):
        return str(doc["response"])
    return ""


def _int_or_none(v: Any) -> int | None:
    return int(v) if isinstance(v, int) else None


def _short(body: bytes, limit: int = 200) -> str:
    return body.decode("utf-8", errors="replace")[:limit]


__all__ = ["OllamaClient"]
