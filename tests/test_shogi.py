"""Unit tests for the shogi demo scenario internals.

Covers parts of `llove.demo.scenarios.shogi` that the *demo replay* alone
does not exercise — most importantly the captured-piece bookkeeping. The
default 20-half-move script does include trades now, but the underlying
helpers (`_apply`, `_format_hand`, `_usi_to_kifu`, `_render_board`) deserve
direct tests so a future regression doesn't sneak in via a board-rendering
change.
"""

from __future__ import annotations

import pytest

from llove.demo.scenarios.shogi import (
    _INITIAL_SFEN_BOARD,
    _apply,
    _format_hand,
    _piece_to_kanji,
    _render_board,
    _usi_to_indices,
    _usi_to_kifu,
)


def _fresh_board() -> list[list[str]]:
    return [row[:] for row in _INITIAL_SFEN_BOARD]


# ---------------------------------------------------------------------------
# _usi_to_indices  /  _usi_to_kifu
# ---------------------------------------------------------------------------


def test_usi_indices_initial_pawn_push() -> None:
    # 7g7f → from row 6 col 2 → to row 5 col 2, no promote
    r1, c1, r2, c2, promote = _usi_to_indices("7g7f")
    assert r1 == 6
    assert c1 == 2
    assert r2 == 5
    assert c2 == 2
    assert promote is False


def test_usi_indices_promotion() -> None:
    _, _, _, _, promote = _usi_to_indices("8h2b+")
    assert promote is True


def test_kifu_sente_pawn() -> None:
    # 7g7f with sente pawn → ▲７六歩
    assert _usi_to_kifu("P", "7g7f", "sente") == "▲７六歩"


def test_kifu_gote_pawn() -> None:
    # 3c3d with gote pawn → △３四歩
    assert _usi_to_kifu("p", "3c3d", "gote") == "△３四歩"


def test_kifu_promotion_marker() -> None:
    # Sente bishop captures and promotes on 2b
    assert _usi_to_kifu("B", "8h2b+", "sente") == "▲２二角成"


def test_kifu_king_glyph_split_sente_gyoku_gote_ou() -> None:
    # Traditional Shogi convention: sente plays 玉, gote plays 王.
    # The kifu and the board rendering must agree on this split.
    assert _usi_to_kifu("K", "5i5h", "sente") == "▲５八玉"
    assert _usi_to_kifu("k", "5a5b", "gote") == "△５二王"


def test_piece_to_kanji_king_split() -> None:
    from llove.demo.scenarios.shogi import _piece_to_kanji

    assert "玉" in _piece_to_kanji("K")  # sente
    assert "王" in _piece_to_kanji("k")  # gote
    # Promoted king doesn't exist in shogi but we shouldn't blow up.
    # (Defensive — make sure the K-special path is gated on `not promoted`.)


def test_kifu_thinking_seconds() -> None:
    assert _usi_to_kifu("P", "7g7f", "sente", thinking_ms=2400) == "▲７六歩 (2.4秒)"


def test_kifu_thinking_sub_second_uses_ms() -> None:
    # Below 1 s shouldn't round to "0.0秒" — show milliseconds instead.
    assert _usi_to_kifu("P", "7g7f", "sente", thinking_ms=480) == "▲７六歩 (480ms)"


# ---------------------------------------------------------------------------
# _apply  +  hand bookkeeping
# ---------------------------------------------------------------------------


def test_apply_simple_move_no_capture_returns_empty() -> None:
    board = _fresh_board()
    captured = _apply(board, "7g7f")
    assert captured == ""
    # Source square is now empty, destination has the sente pawn.
    assert board[6][2] == "."
    assert board[5][2] == "P"


def test_apply_capture_returns_taken_piece() -> None:
    # Place a gote pawn directly in front of a sente pawn so the trade
    # can run on a fresh board without doing the full opening dance.
    board = _fresh_board()
    board[5][2] = "p"  # gote pawn at 7f
    board[6][2] = "P"  # sente pawn at 7g (already there)
    captured = _apply(board, "7g7f")  # sente pawn takes the gote pawn
    # `_apply` returns the captured piece *as it was on the board*.
    assert captured == "p"
    assert board[5][2] == "P"  # sente pawn now occupies 7f
    assert board[6][2] == "."


def test_apply_promotion_marks_destination_with_plus() -> None:
    board = _fresh_board()
    # Move sente bishop 8h → 2b with a promotion flag. We don't care about
    # whether shogi rules really allow this in the opening: this test only
    # checks _apply's mechanics.
    captured = _apply(board, "8h2b+")
    # 2b held the gote bishop in the initial layout (lowercase 'b'),
    # so this is also a capture. The gote rook ('r') sits at 2b's
    # mirror image (8b = board[1][1]) — be careful not to confuse them.
    assert captured == "b"
    assert board[1][7] == "+B"  # sente bishop, promoted, now at 2b


# ---------------------------------------------------------------------------
# _format_hand
# ---------------------------------------------------------------------------


def test_format_hand_empty_says_nashi() -> None:
    out = _format_hand({}, side="sente")
    assert "なし" in out
    assert "先手" in out


def test_format_hand_single_piece_no_count() -> None:
    out = _format_hand({"P": 1}, side="sente")
    assert "歩" in out
    assert "x" not in out  # single piece never gets the multiplier


def test_format_hand_multiple_pieces_use_multiplier() -> None:
    out = _format_hand({"P": 2, "B": 1}, side="sente")
    assert "歩 x2" in out
    # Pieces should appear in fixed P/L/N/S/G/B/R order regardless of dict
    # insertion order.
    assert out.index("歩") < out.index("角")


def test_format_hand_gote_uses_red_marker() -> None:
    out = _format_hand({"P": 1}, side="gote")
    # gote header carries the [bright_red] tag so the audit pane shows it
    # in red — same logic as the on-board pieces.
    assert "[bright_red]" in out
    assert "後手" in out


# ---------------------------------------------------------------------------
# _piece_to_kanji  /  _render_board
# ---------------------------------------------------------------------------


def test_piece_to_kanji_empty_uses_full_width_dot() -> None:
    assert _piece_to_kanji(".") == "[default]・[/default]"


def test_piece_to_kanji_sente_default_colour() -> None:
    out = _piece_to_kanji("P")
    assert "[default]" in out
    assert "歩" in out


def test_piece_to_kanji_gote_bright_red() -> None:
    out = _piece_to_kanji("p")
    assert "[bright_red]" in out
    assert "歩" in out


def test_piece_to_kanji_promoted_sente() -> None:
    out = _piece_to_kanji("+P")
    assert "と" in out
    assert "[default]" in out


def test_piece_to_kanji_promoted_gote() -> None:
    out = _piece_to_kanji("+p")
    assert "と" in out
    assert "[bright_red]" in out


def test_render_board_includes_hand_lines() -> None:
    board = _fresh_board()
    out = _render_board(board, sente_hand={"P": 2}, gote_hand={"P": 1})
    # Both hand lines appear on their own row.
    assert "先手" in out
    assert "後手" in out
    assert "歩 x2" in out


# ---------------------------------------------------------------------------
# Integration: replay the script and assert the captures match expectations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_script_produces_pawn_captures() -> None:
    """The 20-half-move default script must end with both sides holding
    captured pieces, otherwise the demo no longer exercises the hand-
    rendering path (which is the whole point of MVP1's mid-game extension)."""
    from llove.demo.scenarios.shogi import ShogiScenario

    scenario = ShogiScenario()
    scenario.default_pause = 0.0
    captures_seen = []
    async for ev in scenario.events():
        if ev.kind.value == "audit" and ev.payload.get("event") == "shogi.move":
            cap = ev.payload.get("captured")
            if cap:
                captures_seen.append((ev.payload["side"], cap))

    sente_captures = [c for side, c in captures_seen if side == "sente"]
    gote_captures = [c for side, c in captures_seen if side == "gote"]
    # Each side should have taken at least one pawn after the 2-file and
    # 8-file trades.
    assert sente_captures, "sente never captured anything in the demo script"
    assert gote_captures, "gote never captured anything in the demo script"
