"""LLM プロバイダ + factory + コスト推定の単体テスト.

fake transport でリクエスト形状 (URL / headers / body JSON) と応答パースを
実挙動として検証する. 実 HTTP は踏まない. タウトロジー (定数を返して定数を
assert) を避け, プロバイダが本当に body を組み立て応答を解釈することを見る.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from llove.llm import (
    ChatMessage,
    ChatRequest,
    LLMBackendError,
    LLMConfig,
    LLMConfigError,
    Usage,
    estimate_cost_usd,
    make_client,
    make_fake_http_transport,
    parse_llm_spec,
    timed_call,
)
from llove.llm.providers.anthropic import AnthropicClient
from llove.llm.providers.llmesh import LlmeshPeerClient
from llove.llm.providers.ollama import OllamaClient


def _req(text: str = "hi", *, system: str = "", model: str = "m") -> ChatRequest:
    msgs: list[ChatMessage] = []
    if system:
        msgs.append(ChatMessage("system", system))
    msgs.append(ChatMessage("user", text))
    return ChatRequest(messages=tuple(msgs), model=model, max_tokens=64, temperature=0.2)


def _capture_handler(status: int, body: bytes) -> tuple[Any, Any]:
    """(handler, captured) を返す. captured に method/url/headers/body を記録."""
    captured: dict[str, Any] = {}

    def handler(method: str, url: str, headers: dict[str, str], body_bytes: bytes | None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json.loads(body_bytes.decode()) if body_bytes else None
        return status, body

    return handler, captured


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


ANTHROPIC_OK = json.dumps(
    {
        "model": "claude-haiku-4-5",
        "content": [
            {"type": "text", "text": "7g7f"},
            {"type": "text", "text": " is best"},
        ],
        "usage": {"input_tokens": 30, "output_tokens": 5},
    }
).encode()


@pytest.mark.asyncio
async def test_anthropic_request_shape_and_parse() -> None:
    handler, captured = _capture_handler(200, ANTHROPIC_OK)
    client = AnthropicClient(
        model="claude-haiku-4-5",
        api_key="sk-xyz",
        transport=make_fake_http_transport(handler),
    )
    resp = await client.complete(_req("what move?", system="You are a shogi engine."))

    # URL / method
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/v1/messages")
    # headers
    assert captured["headers"]["x-api-key"] == "sk-xyz"
    assert captured["headers"]["anthropic-version"]
    # body: system は別フィールド, messages は非 system のみ
    body = captured["body"]
    assert body["model"] == "claude-haiku-4-5"
    assert body["max_tokens"] == 64
    assert body["system"] == "You are a shogi engine."
    assert body["messages"] == [{"role": "user", "content": "what move?"}]
    # parse: text ブロック連結
    assert resp.text == "7g7f is best"
    assert resp.usage.input_tokens == 30
    assert resp.usage.output_tokens == 5
    assert resp.provider == "anthropic"
    # 既知モデルなのでコスト推定される (>0)
    assert resp.cost_usd is not None and resp.cost_usd > 0


@pytest.mark.asyncio
async def test_anthropic_includes_stop_sequences() -> None:
    handler, captured = _capture_handler(200, ANTHROPIC_OK)
    client = AnthropicClient(
        model="claude-haiku-4-5", api_key="k", transport=make_fake_http_transport(handler)
    )
    req = ChatRequest(
        messages=(ChatMessage("user", "x"),), model="claude-haiku-4-5", stop=("\n\n",)
    )
    await client.complete(req)
    assert captured["body"]["stop_sequences"] == ["\n\n"]


@pytest.mark.asyncio
async def test_anthropic_http_error_raises_backend_error() -> None:
    handler, _ = _capture_handler(401, b'{"error":{"message":"invalid key"}}')
    client = AnthropicClient(
        model="m", api_key="bad", transport=make_fake_http_transport(handler)
    )
    with pytest.raises(LLMBackendError, match="anthropic http_401"):
        await client.complete(_req())


@pytest.mark.asyncio
async def test_anthropic_bad_json_raises_backend_error() -> None:
    handler, _ = _capture_handler(200, b"not json")
    client = AnthropicClient(
        model="m", api_key="k", transport=make_fake_http_transport(handler)
    )
    with pytest.raises(LLMBackendError, match="json_parse_error"):
        await client.complete(_req())


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------


OLLAMA_OK = json.dumps(
    {
        "model": "llama3.2",
        "message": {"role": "assistant", "content": "e2e4"},
        "prompt_eval_count": 42,
        "eval_count": 3,
        "done": True,
    }
).encode()


@pytest.mark.asyncio
async def test_ollama_request_shape_and_parse() -> None:
    handler, captured = _capture_handler(200, OLLAMA_OK)
    client = OllamaClient(
        model="llama3.2", transport=make_fake_http_transport(handler)
    )
    resp = await client.complete(_req("go", system="be brief"))

    assert captured["url"].endswith("/api/chat")
    body = captured["body"]
    assert body["stream"] is False
    assert body["options"]["num_predict"] == 64
    assert body["options"]["temperature"] == 0.2
    # system は messages にそのまま残る (ollama 流儀)
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": "go"}

    assert resp.text == "e2e4"
    assert resp.usage.input_tokens == 42
    assert resp.usage.output_tokens == 3
    # ローカルはコスト 0.0 を明示 (None ではない)
    assert resp.cost_usd == 0.0
    assert resp.provider == "ollama"


@pytest.mark.asyncio
async def test_ollama_response_field_fallback() -> None:
    body = json.dumps({"model": "m", "response": "fallback-text", "done": True}).encode()
    handler, _ = _capture_handler(200, body)
    client = OllamaClient(model="m", transport=make_fake_http_transport(handler))
    resp = await client.complete(_req())
    assert resp.text == "fallback-text"


@pytest.mark.asyncio
async def test_ollama_http_error_raises() -> None:
    handler, _ = _capture_handler(500, b'{"error":"model not found"}')
    client = OllamaClient(model="m", transport=make_fake_http_transport(handler))
    with pytest.raises(LLMBackendError, match="ollama http_500"):
        await client.complete(_req())


# ---------------------------------------------------------------------------
# llmesh peer (OpenAI 互換)
# ---------------------------------------------------------------------------


LLMESH_OK = json.dumps(
    {
        "model": "local-model",
        "choices": [{"message": {"role": "assistant", "content": "resign"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }
).encode()


@pytest.mark.asyncio
async def test_llmesh_request_shape_and_auth_header() -> None:
    handler, captured = _capture_handler(200, LLMESH_OK)
    client = LlmeshPeerClient(
        model="local-model",
        base_url="http://peer:8080",
        api_key="peer-key",
        transport=make_fake_http_transport(handler),
    )
    resp = await client.complete(_req("move?"))

    assert captured["url"] == "http://peer:8080/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer peer-key"
    assert captured["body"]["model"] == "local-model"
    assert resp.text == "resign"
    assert resp.usage.input_tokens == 10
    assert resp.usage.output_tokens == 2
    # llmesh peer の課金元は不明(ローカル無料 or 有料クラウド)→ 捏造せず None(N/A)
    assert resp.cost_usd is None
    assert resp.provider == "llmesh"


@pytest.mark.asyncio
async def test_llmesh_no_auth_header_when_keyless() -> None:
    handler, captured = _capture_handler(200, LLMESH_OK)
    client = LlmeshPeerClient(
        model="m", base_url="http://peer:8080", transport=make_fake_http_transport(handler)
    )
    await client.complete(_req())
    assert "authorization" not in captured["headers"]


@pytest.mark.asyncio
async def test_llmesh_claude_model_gets_cost_estimate() -> None:
    body = json.dumps(
        {
            "model": "claude-haiku-4-5",
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 1000},
        }
    ).encode()
    handler, _ = _capture_handler(200, body)
    client = LlmeshPeerClient(
        model="claude-haiku-4-5",
        base_url="http://gw:1",
        transport=make_fake_http_transport(handler),
    )
    resp = await client.complete(_req())
    # claude 系は価格表で見積もる (>0)
    assert resp.cost_usd is not None and resp.cost_usd > 0


# ---------------------------------------------------------------------------
# コスト推定
# ---------------------------------------------------------------------------


def test_estimate_cost_known_model() -> None:
    c = estimate_cost_usd("claude-haiku-4-5", Usage(input_tokens=1_000_000, output_tokens=0))
    assert c == pytest.approx(1.0)


def test_estimate_cost_family_prefix_fallback() -> None:
    # 完全一致に無いが family 前方一致で拾う.
    c = estimate_cost_usd("claude-haiku-4-5-20990101", Usage(input_tokens=0, output_tokens=1_000_000))
    assert c == pytest.approx(5.0)


def test_estimate_cost_unknown_model_is_none() -> None:
    assert estimate_cost_usd("mystery-model", Usage(input_tokens=100, output_tokens=100)) is None


def test_estimate_cost_missing_usage_is_none() -> None:
    assert estimate_cost_usd("claude-haiku-4-5", Usage()) is None


# ---------------------------------------------------------------------------
# factory / spec
# ---------------------------------------------------------------------------


def test_parse_llm_spec_basic() -> None:
    assert parse_llm_spec("anthropic:claude-haiku-4-5") == ("anthropic", "claude-haiku-4-5")


def test_parse_llm_spec_model_with_colon() -> None:
    assert parse_llm_spec("ollama:llama3:70b") == ("ollama", "llama3:70b")


def test_parse_llm_spec_default_model() -> None:
    assert parse_llm_spec("ollama") == ("ollama", "llama3.2")
    assert parse_llm_spec("anthropic") == ("anthropic", "claude-haiku-4-5")


def test_parse_llm_spec_unknown_provider() -> None:
    with pytest.raises(LLMConfigError, match="unknown provider"):
        parse_llm_spec("gpt5:whatever")


def test_make_client_ollama_with_transport() -> None:
    cfg = LLMConfig.from_env({})
    handler, _ = _capture_handler(200, OLLAMA_OK)
    client = make_client("ollama:llama3.2", config=cfg, transport=make_fake_http_transport(handler))
    assert isinstance(client, OllamaClient)
    assert client.model == "llama3.2"


def test_make_client_anthropic_requires_key() -> None:
    cfg = LLMConfig.from_env({})  # no key
    with pytest.raises(LLMConfigError, match="anthropic is not configured"):
        make_client("anthropic:claude-haiku-4-5", config=cfg)


def test_make_client_anthropic_with_key() -> None:
    cfg = LLMConfig.from_env({"ANTHROPIC_API_KEY": "k"})
    client = make_client("anthropic", config=cfg)
    assert isinstance(client, AnthropicClient)
    assert client.model == "claude-haiku-4-5"
    assert client.api_key == "k"


def test_make_client_llmesh_requires_url() -> None:
    cfg = LLMConfig.from_env({})
    with pytest.raises(LLMConfigError, match="llmesh is not configured"):
        make_client("llmesh:m", config=cfg)


# ---------------------------------------------------------------------------
# timed_call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timed_call_returns_status_body_latency() -> None:
    def fn() -> tuple[int, bytes]:
        return 200, b"ok"

    status, body, latency_ms = await timed_call(fn)
    assert status == 200
    assert body == b"ok"
    assert latency_ms >= 0
