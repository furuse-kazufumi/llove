"""Tests for ``llove.shogi.engine`` — the python-shogi legality wrapper."""

from __future__ import annotations

import pytest

shogi_lib = pytest.importorskip("shogi")  # skip these tests if extras not installed.

from llove.shogi.engine import Engine, LegalityResult


def test_fresh_engine_has_30_legal_moves_and_sente_to_move() -> None:
    e = Engine()
    assert e.turn == "sente"
    assert e.ply == 0
    assert len(e.legal_moves_usi()) == 30  # canonical opening count


def test_push_legal_move_advances_state() -> None:
    e = Engine()
    r = e.push_usi("7g7f")
    assert r.ok
    assert e.turn == "gote"
    assert e.ply == 1
    assert e.move_history_usi == ["7g7f"]


def test_validate_does_not_mutate_engine() -> None:
    e = Engine()
    before = e.sfen
    r = e.validate("7g7f")
    assert r.ok
    # SFEN must be byte-identical — validation is read-only.
    assert e.sfen == before


def test_illegal_move_returns_reason_and_does_not_advance() -> None:
    e = Engine()
    # Sente's pawn cannot leap two squares.
    r = e.push_usi("7g7e")
    assert not r.ok
    assert "illegal" in r.reason
    assert e.ply == 0


def test_parse_error_for_nonsense_usi() -> None:
    e = Engine()
    r = e.validate("zz99")
    assert not r.ok
    assert "parse_error" in r.reason


def test_legality_result_dataclass_is_frozen() -> None:
    r = LegalityResult(ok=True, reason="")
    with pytest.raises(Exception):
        r.ok = False  # type: ignore[misc]


def test_engine_from_custom_sfen() -> None:
    # A position one move into the game.
    sfen = "lnsgkgsnl/1r5b1/ppppppppp/9/9/2P6/PP1PPPPPP/1B5R1/LNSGKGSNL w - 2"
    e = Engine(sfen=sfen)
    assert e.turn == "gote"
    # Gote should have a legal pawn push back.
    assert "3c3d" in e.legal_moves_usi()


def test_check_and_checkmate_default_false() -> None:
    e = Engine()
    assert e.is_check() is False
    assert e.is_checkmate() is False
    assert e.is_fourfold_repetition() is False
