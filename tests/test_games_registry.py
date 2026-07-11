"""``llove.games.registry`` の単体テスト.

汎用ゲームレジストリ (games.base 上のゲーム; chess) の登録・構築・未知拒否を
確認する。shogi は別スタックなのでレジストリには載らない (module docstring)。
"""

from __future__ import annotations

import pytest

from llove.games.base.engine import GameEngine
from llove.games.registry import available_games, is_registered, make_engine


def test_available_games_lists_chess() -> None:
    games = available_games()
    assert "chess" in games
    # shogi は別スタック — レジストリには含めない.
    assert "shogi" not in games


def test_is_registered() -> None:
    assert is_registered("chess") is True
    assert is_registered("shogi") is False
    assert is_registered("go") is False


def test_make_engine_chess_returns_chess_engine() -> None:
    engine = make_engine("chess")
    assert isinstance(engine, GameEngine)
    assert engine.game == "chess"
    assert engine.player_ids() == ["white", "black"]


def test_make_engine_unknown_raises_with_available_list() -> None:
    with pytest.raises(ValueError, match="unknown game 'go'") as exc:
        make_engine("go")
    # 案内に利用可能なゲーム一覧を含む.
    assert "chess" in str(exc.value)


def test_make_engine_does_not_include_shogi() -> None:
    # shogi はレジストリ外 — make_engine では解決できない (呼び出し側が special-case).
    with pytest.raises(ValueError, match="unknown game 'shogi'"):
        make_engine("shogi")
