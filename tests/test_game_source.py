"""``llove.games.base.source.GameSource`` の単体 / e2e テスト.

汎用 ``run_game`` を LoveApp の ``DataSource`` として駆動できること (chess を
最後まで指し切る)、stdout tee、name の設定、欠員時の fail-closed を確認する。
実 HTTP は踏まず、ollama 形状の fake transport で「合法手の先頭」を返す
決定的プレイヤを両者に据える。
"""

from __future__ import annotations

import json

import pytest

from llove.games.base.llm_player import make_game_player
from llove.games.base.player import GamePlayer
from llove.games.base.source import GameSource
from llove.games.chess.engine import ChessEngine
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


def _first_legal_transport():  # type: ignore[no-untyped-def]
    """プロンプトに列挙された合法手の先頭を返す fake (常に合法 → 対局が進む)."""

    def handler(method, url, headers, body):  # type: ignore[no-untyped-def]
        doc = json.loads(body.decode())
        user = doc["messages"][-1]["content"]
        move = "e2e4"
        for line in user.splitlines():
            if line.startswith("Legal moves:"):
                first = line[len("Legal moves:") :].split(",")[0].strip()
                if first:
                    move = first
                break
        return 200, _ollama_body(move)

    return make_fake_http_transport(handler)


def _chess_players() -> tuple[ChessEngine, dict[str, GamePlayer]]:
    engine = ChessEngine()
    transport = _first_legal_transport()
    pids = engine.player_ids()
    players: dict[str, GamePlayer] = {
        pids[0]: make_game_player(
            "ollama:llama3.2",
            player_id=pids[0],
            game="chess",
            config=LLMConfig.from_env({}),
            transport=transport,
        ),
        pids[1]: make_game_player(
            "ollama:llama3.2",
            player_id=pids[1],
            game="chess",
            config=LLMConfig.from_env({}),
            transport=transport,
        ),
    }
    return engine, players


def test_name_is_taken_from_engine() -> None:
    engine, players = _chess_players()
    src = GameSource(engine, players)
    assert src.name == "chess"


@pytest.mark.asyncio
async def test_game_source_plays_chess_to_completion() -> None:
    engine, players = _chess_players()
    src = GameSource(engine, players, max_ply=6)
    events = [ev async for ev in src.stream()]
    kinds = [ev.payload.get("event") for ev in events]

    assert kinds[0] == "game.start"
    assert kinds[-1] == "game.end"
    assert kinds.count("game.move") == 6  # first-legal never terminates early

    end = events[-1].payload
    assert end["game"] == "chess"
    assert end["term"] == "max_ply"
    assert end["plies"] == 6
    # every move carried a UCI notation the engine accepted as legal.
    moves = [ev for ev in events if ev.payload.get("event") == "game.move"]
    assert all(m.payload["notation"] for m in moves)


@pytest.mark.asyncio
async def test_game_source_also_stdout_tees_one_json_line_per_event(
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine, players = _chess_players()
    src = GameSource(engine, players, max_ply=2, also_stdout=True)
    events = [ev async for ev in src.stream()]

    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    # one JSON line teed per yielded event.
    assert len(lines) == len(events)
    docs = [json.loads(ln) for ln in lines]
    assert docs[0]["payload"]["event"] == "game.start"
    assert docs[-1]["payload"]["event"] == "game.end"


@pytest.mark.asyncio
async def test_game_source_missing_player_fails_closed() -> None:
    engine = ChessEngine()
    # Only white provided → run_game must reject before any move (fail-closed).
    players: dict[str, GamePlayer] = {
        "white": make_game_player(
            "ollama:llama3.2",
            player_id="white",
            game="chess",
            config=LLMConfig.from_env({}),
            transport=_first_legal_transport(),
        )
    }
    src = GameSource(engine, players)
    with pytest.raises(ValueError, match="missing player"):
        _ = [ev async for ev in src.stream()]
