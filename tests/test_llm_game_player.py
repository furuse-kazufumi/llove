"""``llove.games.base.llm_player.LLMGamePlayer`` の単体テスト.

ollama 形状の fake transport で実 HTTP を踏まずに検証する. プロンプトに合法手が
載ること・chatty 応答から着手を抽出できること・fail-closed 経路を重点確認.
"""

from __future__ import annotations

import json

import pytest

from llove.games.base import (
    GameEngine,
    LegalityResult,
    Observation,
    make_game_player,
    run_game,
)
from llove.games.base.engine import TermResult
from llove.games.base.types import Move, TermReason
from llove.llm import LLMConfig, make_fake_http_transport


def _ollama_body(text: str) -> bytes:
    return json.dumps(
        {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": text},
            "prompt_eval_count": 10,
            "eval_count": 3,
            "done": True,
        }
    ).encode()


def _player(text: str, *, captured: dict | None = None, status: int = 200,
            game: str = "shogi", player_id: str = "a"):
    def handler(method, url, headers, body):
        if captured is not None and body is not None:
            captured["body"] = json.loads(body.decode())
        return status, _ollama_body(text)

    return make_game_player(
        "ollama:llama3.2",
        game=game,
        player_id=player_id,
        config=LLMConfig.from_env({}),
        transport=make_fake_http_transport(handler),
    )


@pytest.mark.asyncio
async def test_extracts_move_from_prose_and_prompt_lists_legal_moves() -> None:
    captured: dict = {}
    player = _player("I'll play 7g7f to open the bishop's diagonal.", captured=captured)
    obs = Observation(player_id="a", public_state={"turn": "a"}, legal_moves=["7g7f", "2g2f"])
    res = await player.think(obs)

    assert res.move is not None
    assert res.move.notation == "7g7f"
    assert res.move.thinking_ms is not None
    assert res.move.raw_response.startswith("I'll play")
    # プロンプト (user メッセージ) に合法手が列挙される.
    user_content = captured["body"]["messages"][-1]["content"]
    assert "7g7f" in user_content
    assert "2g2f" in user_content


@pytest.mark.asyncio
async def test_backend_error_resigns() -> None:
    player = _player("whatever", status=500)
    obs = Observation(player_id="a", legal_moves=["7g7f"])
    res = await player.think(obs)
    assert res.resign is True
    assert res.move is None
    assert "backend_error" in res.resign_reason


@pytest.mark.asyncio
async def test_no_listed_legal_move_resigns_instead_of_garbage() -> None:
    # 応答に合法手が無い → ゴミ手で違法ストライクを浪費せず resign.
    player = _player("I resign, this position is hopeless.")
    obs = Observation(player_id="a", legal_moves=["7g7f", "2g2f"])
    res = await player.think(obs)
    assert res.resign is True
    assert "legal move" in res.resign_reason


@pytest.mark.asyncio
async def test_no_legal_moves_passes_raw_token_to_engine() -> None:
    # legal_moves 空 = engine が唯一の legality oracle → 生トークンを渡す.
    player = _player("inc")
    obs = Observation(player_id="a", legal_moves=[])
    res = await player.think(obs)
    assert res.move is not None
    assert res.move.notation == "inc"


@pytest.mark.asyncio
async def test_empty_response_resigns_when_no_legal_moves() -> None:
    player = _player("   ")
    obs = Observation(player_id="a", legal_moves=[])
    res = await player.think(obs)
    assert res.resign is True


def test_make_game_player_sets_provider_model_name() -> None:
    player = _player("x")
    assert player.provider == "ollama"
    assert player.model == "llama3.2"
    assert "ollama" in player.name


@pytest.mark.asyncio
async def test_make_game_player_anthropic_requires_key() -> None:
    from llove.llm import LLMConfigError

    with pytest.raises(LLMConfigError, match="anthropic is not configured"):
        make_game_player("anthropic:claude-haiku-4-5", config=LLMConfig.from_env({}))


# ---------------------------------------------------------------------------
# run_game 統合 — LLM player が実ループに乗ることを確認
# ---------------------------------------------------------------------------


class _OneMoveEngine(GameEngine):
    """"go" を 1 回受けたら終局する最小 engine (run_game 配線確認用)."""

    game = "toy"

    def __init__(self) -> None:
        self._done = False

    def player_ids(self) -> list[str]:
        return ["a", "b"]

    def current_player_id(self) -> str:
        return "a"

    @property
    def ply(self) -> int:
        return 1 if self._done else 0

    def state_summary(self) -> str:
        return "done" if self._done else "start"

    def observation_for(self, player_id: str) -> Observation:
        return Observation(player_id=player_id, legal_moves=["go"])

    def push(self, move: Move, player_id: str) -> LegalityResult:
        if move.notation != "go":
            return LegalityResult(ok=False, reason="illegal")
        self._done = True
        return LegalityResult(ok=True)

    def is_terminated(self) -> TermResult | None:
        return TermResult(reason=TermReason.CUSTOM, winner_id="a") if self._done else None


@pytest.mark.asyncio
async def test_llm_player_drives_run_game() -> None:
    a = _player("The move is go.", player_id="a", game="toy")
    b = _player("go", player_id="b", game="toy")
    events = [ev async for ev in run_game(_OneMoveEngine(), {"a": a, "b": b}, max_ply=5)]
    moves = [ev for ev in events if ev.payload.get("event") == "game.move"]
    assert len(moves) == 1
    assert moves[0].payload["notation"] == "go"
