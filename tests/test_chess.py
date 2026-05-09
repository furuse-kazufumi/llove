"""F16 ChessEngine — F16 抽象が他ゲームでも動くことを実証するテスト."""

from __future__ import annotations

import pytest

chess_lib = pytest.importorskip("chess")

from llove.games.base import Move
from llove.games.base.types import TermReason
from llove.games.chess import ChessEngine


def test_initial_position_white_to_move_with_20_legal() -> None:
    e = ChessEngine()
    assert e.current_player_id() == "white"
    assert e.ply == 0
    obs = e.observation_for("white")
    assert len(obs.legal_moves) == 20


def test_player_ids_are_white_and_black() -> None:
    assert ChessEngine().player_ids() == ["white", "black"]


def test_legal_pawn_push_advances_state() -> None:
    e = ChessEngine()
    res = e.push(Move(notation="e2e4"), "white")
    assert res.ok is True
    assert e.current_player_id() == "black"
    assert e.ply == 1


def test_pushing_on_wrong_turn_is_illegal() -> None:
    e = ChessEngine()
    res = e.push(Move(notation="e7e5"), "white")  # black's pawn but white's turn
    assert res.ok is False


def test_illegal_pawn_double_step_after_first_move() -> None:
    e = ChessEngine()
    e.push(Move(notation="e2e4"), "white")
    e.push(Move(notation="e7e5"), "black")
    # e4 から e6 に飛び越えるのは違法
    res = e.push(Move(notation="e4e6"), "white")
    assert res.ok is False
    assert "illegal" in res.reason


def test_parse_error_on_garbage_uci() -> None:
    e = ChessEngine()
    res = e.push(Move(notation="zzzz"), "white")
    assert res.ok is False
    assert "parse_error" in res.reason or "illegal" in res.reason


def test_san_helper_converts_uci_to_san() -> None:
    e = ChessEngine()
    assert e.san("e2e4") == "e4"
    assert e.san("g1f3") == "Nf3"


def test_observation_includes_check_flag() -> None:
    e = ChessEngine()
    obs = e.observation_for("white")
    assert "is_check" in obs.public_state
    assert obs.public_state["is_check"] is False


def test_fools_mate_detected_as_checkmate() -> None:
    """4 手の Fool's Mate で詰みを検出 + 勝者は black."""
    e = ChessEngine()
    e.push(Move(notation="f2f3"), "white")
    e.push(Move(notation="e7e5"), "black")
    e.push(Move(notation="g2g4"), "white")
    res = e.push(Move(notation="d8h4"), "black")
    assert res.ok is True
    term = e.is_terminated()
    assert term is not None
    assert term.reason == TermReason.CHECKMATE
    assert term.winner_id == "black"


def test_stalemate_detected() -> None:
    """構成された stalemate 局面で stalemate 判定."""
    # 既知の stalemate FEN
    fen = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
    e = ChessEngine(fen=fen)
    term = e.is_terminated()
    assert term is not None
    assert term.reason == TermReason.STALEMATE
    assert term.winner_id is None


def test_state_summary_returns_fen() -> None:
    e = ChessEngine()
    fen = e.state_summary()
    assert fen.startswith("rnbqkbnr/pppppppp/")  # 初期局面


def test_engine_game_id_is_chess() -> None:
    assert ChessEngine().game == "chess"
