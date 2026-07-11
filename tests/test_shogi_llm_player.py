"""``llove.shogi.players.llm.LLMShogiPlayer`` + ``make_player`` 配線のテスト.

python-shogi (shogi extra) 非依存で回すため, engine は fake スタブを使う —
``LLMShogiPlayer.think`` が触るのは ``sfen`` / ``legal_moves_usi()`` /
``move_history_usi`` だけなので duck-typing で十分.
"""

from __future__ import annotations

import json

import pytest

from llove.llm import LLMConfig, LLMConfigError, make_fake_http_transport
from llove.shogi.players.base import make_player
from llove.shogi.players.llm import LLMShogiPlayer, make_shogi_llm_player
from llove.shogi.players.mock import MockPlayer


class _FakeEngine:
    """LLMShogiPlayer が必要とする最小インターフェースだけ持つ fake."""

    def __init__(self, sfen: str, legal: list[str], history: list[str] | None = None) -> None:
        self.sfen = sfen
        self._legal = legal
        self.move_history_usi = history or []

    def legal_moves_usi(self) -> list[str]:
        return self._legal


def _ollama_body(text: str) -> bytes:
    return json.dumps(
        {"model": "llama3.2", "message": {"content": text}, "eval_count": 2, "done": True}
    ).encode()


def _player(text: str, *, side: str = "sente", captured: dict | None = None, status: int = 200):
    def handler(method, url, headers, body):
        if captured is not None and body is not None:
            captured["body"] = json.loads(body.decode())
        return status, _ollama_body(text)

    return make_shogi_llm_player(
        "ollama:llama3.2",
        side=side,
        config=LLMConfig.from_env({}),
        transport=make_fake_http_transport(handler),
    )


_START_SFEN = "lnsgkgsnl/1r5b1/ppppppppp/9/9/9/PPPPPPPPP/1B5R1/LNSGKGSNL b - 1"


@pytest.mark.asyncio
async def test_shogi_llm_extracts_usi_and_prompt_has_sfen_and_legal() -> None:
    captured: dict = {}
    player = _player("I choose 7g7f.", captured=captured)
    eng = _FakeEngine(_START_SFEN, ["7g7f", "2g2f", "6i7h"])
    res = await player.think(eng)

    assert res.move is not None
    assert res.move.usi == "7g7f"
    body = captured["body"]["messages"][-1]["content"]
    assert _START_SFEN in body
    assert "7g7f" in body


@pytest.mark.asyncio
async def test_shogi_llm_backend_error_resigns() -> None:
    player = _player("x", status=500)
    res = await player.think(_FakeEngine(_START_SFEN, ["7g7f"]))
    assert res.resign is True
    assert "backend_error" in res.resign_reason


@pytest.mark.asyncio
async def test_shogi_llm_no_legal_move_in_response_resigns() -> None:
    player = _player("I have no idea what to do here.")
    res = await player.think(_FakeEngine(_START_SFEN, ["7g7f", "2g2f"]))
    assert res.resign is True
    assert "legal" in res.resign_reason


@pytest.mark.asyncio
async def test_shogi_llm_empty_legal_moves_resigns() -> None:
    player = _player("7g7f")
    res = await player.think(_FakeEngine(_START_SFEN, []))
    assert res.resign is True
    assert "no legal moves" in res.resign_reason


def test_shogi_llm_player_name_and_provider() -> None:
    player = _player("x", side="gote")
    assert player.provider == "ollama"
    assert player.model == "llama3.2"
    assert "(gote)" in player.name


# ---------------------------------------------------------------------------
# make_player 配線 — mock 後方互換 + LLM プロバイダ実装
# ---------------------------------------------------------------------------


def test_make_player_mock_still_works() -> None:
    p = make_player("mock:script", side="sente")
    assert isinstance(p, MockPlayer)


def test_make_player_ollama_returns_llm_player() -> None:
    handler = make_fake_http_transport(lambda m, u, h, b: (200, _ollama_body("7g7f")))
    p = make_player("ollama:llama3.2", side="sente", config=LLMConfig.from_env({}), transport=handler)
    assert isinstance(p, LLMShogiPlayer)
    assert p.provider == "ollama"


def test_make_player_anthropic_without_key_fails_closed() -> None:
    # 空 env を明示注入して決定的に (実 os.environ のキー有無に左右されない).
    with pytest.raises(LLMConfigError, match="anthropic is not configured"):
        make_player("anthropic:claude-haiku-4-5", side="sente", config=LLMConfig.from_env({}))


def test_make_player_llmesh_without_url_fails_closed() -> None:
    with pytest.raises(LLMConfigError, match="llmesh is not configured"):
        make_player("llmesh:my-model", side="sente", config=LLMConfig.from_env({}))
