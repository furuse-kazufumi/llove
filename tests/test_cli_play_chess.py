"""`llove play chess` CLI のテスト (Click CliRunner, オフライン).

fake transport を make_game_player に注入して実サーバ無しでフル対局まで走らせる。
設定エラー / 未知 provider は exit 2 で install/設定ヒントを返すことも確認する。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from llove.cli import main
from llove.llm import make_fake_http_transport


def _ollama_body(text: str) -> bytes:
    return json.dumps(
        {"model": "m", "message": {"role": "assistant", "content": text}, "done": True}
    ).encode()


def _fixed_move_transport(move: str = "e2e4"):  # type: ignore[no-untyped-def]
    def handler(method, url, headers, body):  # type: ignore[no-untyped-def]
        return 200, _ollama_body(move)

    return make_fake_http_transport(handler)


def test_play_group_lists_chess_and_shogi() -> None:
    res = CliRunner().invoke(main, ["play", "--help"])
    assert res.exit_code == 0
    assert "chess" in res.output
    assert "shogi" in res.output


def test_play_chess_help() -> None:
    res = CliRunner().invoke(main, ["play", "chess", "--help"])
    assert res.exit_code == 0
    for opt in ("--white", "--black", "--max-ply", "--no-tui", "--log"):
        assert opt in res.output


def test_play_chess_anthropic_without_key_exits_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    res = CliRunner().invoke(
        main,
        ["play", "chess", "--white", "anthropic:claude-haiku-4-5",
         "--black", "ollama:m", "--no-tui"],
    )
    assert res.exit_code == 2
    assert "anthropic is not configured" in res.output


def test_play_chess_unknown_provider_exits_2() -> None:
    res = CliRunner().invoke(
        main, ["play", "chess", "--white", "bogus:x", "--no-tui"]
    )
    assert res.exit_code == 2
    assert "unknown provider" in res.output


def test_play_chess_no_tui_offline_full_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # make_game_player に fake transport を注入して実サーバ無しでフル対局を走らせる。
    from llove.games.base import llm_player as lp

    real = lp.make_game_player
    fake = _fixed_move_transport("e2e4")

    def _maker(spec: str, **kw: object) -> object:
        kw["transport"] = fake
        return real(spec, **kw)  # type: ignore[arg-type]

    monkeypatch.setattr(lp, "make_game_player", _maker)

    log = tmp_path / "kifu.jsonl"
    res = CliRunner().invoke(
        main,
        ["play", "chess", "--white", "ollama:m", "--black", "ollama:m",
         "--no-tui", "--max-ply", "4", "--log", str(log)],
    )
    assert res.exit_code == 0, res.output
    assert log.exists()
    rows = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    events = [r["payload"].get("event") for r in rows]
    assert events[0] == "game.start"
    assert events[-1] == "game.end"
    # white は e2e4 を合法に指す(fixed fake)→ 少なくとも 1 手。
    assert "game.move" in events
    # stdout にも同じ JSONL がストリームされる(--no-tui)。
    assert '"game.start"' in res.output
