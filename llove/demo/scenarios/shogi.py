# ruff: noqa: RUF001
# RUF001 flags full-width digits / question marks etc. inside string literals
# because they look like ASCII counterparts. Here they are deliberate: the
# board uses full-width digit / kanji glyphs to keep the 2-cell column rhythm
# of CJK fonts.
"""Shogi scenario.

Two LLMs play a scripted game on a shared 9x9 board.

MVP1 (this file): no real LLM, no legality checker, no extra dependency.
Just replays a hand-curated short game so we can validate the TUI fit:
  - the board fits in the SensorStream pane (renamed to "Board"),
  - mock evaluation scores drift in the SPC pane and trigger an alarm
    when the lead flips,
  - every move lands in the audit log as standard 'usi' notation,
  - narration delivers the would-be LLM commentary in casual prose.

MVP2 will swap the scripted moves for real LLM calls behind a legality
check; MVP3 adds a human-vs-LLM input mode; MVP4 ships a Qt board viewer.
The Event payload already carries enough state (sfen-like board snapshot,
hands, last move, eval score) for those upgrades and for an external
viewer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind
from llove.i18n import t

# Piece codes — uppercase = sente (first player, bottom),
# lowercase = gote (second player, top). '+' prefix = promoted.
# Use single ASCII letters so the board grid stays 1 cell per piece for
# rendering; a kanji rendering can come later in MVP4.
#   P = pawn, L = lance, N = knight, S = silver, G = gold,
#   B = bishop, R = rook, K = king
# Player identities. MVP1 is scripted so the model names are mock; MVP2
# will replace these at runtime with the actual Anthropic / OpenAI handles
# the user wires in. Surfaced in the intro narration and the audit header
# so the user can see who is playing whom.
_PLAYERS: dict[str, str] = {
    "sente": "LLM-A (mock · MVP1)",
    "gote": "LLM-B (mock · MVP1)",
}


_INITIAL_SFEN_BOARD = [
    list("lnsgkgsnl"),
    [".", "r", ".", ".", ".", ".", ".", "b", "."],
    list("ppppppppp"),
    list("........."),
    list("........."),
    list("........."),
    list("PPPPPPPPP"),
    [".", "B", ".", ".", ".", ".", ".", "R", "."],
    list("LNSGKGSNL"),
]


# A short illustrative game. Each move is USI (file-rank-file-rank,
# files 9..1 left→right, ranks a..i top→bottom). 'p' suffix = promotion.
# This is a 14-half-move opening: Yagura formation buildup → first
# central exchange. Real game-quality moves are not the point in MVP1;
# we just need recognisable shogi state changes.
_MOVES: list[dict[str, Any]] = [
    {"usi": "7g7f", "side": "sente", "comment": "7g→7f: sente opens with the Yagura pawn push.", "eval": +35, "thinking_ms": 2400},
    {"usi": "3c3d", "side": "gote",  "comment": "3c→3d: gote mirrors. Symmetric so far.",        "eval":   0, "thinking_ms": 1800},
    {"usi": "2g2f", "side": "sente", "comment": "2g→2f: sente prepares the rook side push.",     "eval": +25, "thinking_ms": 3100},
    {"usi": "8c8d", "side": "gote",  "comment": "8c→8d: gote answers on the same wing.",         "eval":  -5, "thinking_ms": 2200},
    {"usi": "2f2e", "side": "sente", "comment": "2f→2e: sente claims more space.",                "eval": +60, "thinking_ms": 4700},
    {"usi": "8d8e", "side": "gote",  "comment": "8d→8e: gote pushes deeper, bishop diagonal stays open.", "eval": +20, "thinking_ms": 3500},
    {"usi": "6i7h", "side": "sente", "comment": "6i→7h: sente starts a Yagura castle (gold lifts).", "eval": +55, "thinking_ms": 5200},
    {"usi": "4a3b", "side": "gote",  "comment": "4a→3b: gote begins their own gold formation.",   "eval": +20, "thinking_ms": 4100},
    {"usi": "5g5f", "side": "sente", "comment": "5g→5f: central pawn push — building tension.",   "eval": +75, "thinking_ms": 6800},
    {"usi": "5c5d", "side": "gote",  "comment": "5c→5d: gote answers in the centre.",             "eval": +30, "thinking_ms": 5300},
    {"usi": "8h7g", "side": "sente", "comment": "8h→7g: bishop retreats to defend the Yagura.",   "eval": +60, "thinking_ms": 7900},
    {"usi": "7c7d", "side": "gote",  "comment": "7c→7d: gote opens a path for their bishop.",     "eval": +25, "thinking_ms": 6100},
    {"usi": "3i4h", "side": "sente", "comment": "3i→4h: silver lifts toward the Yagura.",         "eval": +85, "thinking_ms": 9400},
    {"usi": "2b3c", "side": "gote",  "comment": "2b→3c: gote rerouting bishop. Sente has the lead but the position stays playable.", "eval": +45, "thinking_ms": 8200},
    # Mid-game starts here — the Yagura buildup tilts into open trades so
    # the captured-pieces panel actually fills with content. The moves
    # come straight from a "2-suji push" (相掛かり風 2 筋交換) sequence:
    # sente trades pawns on the 2-file, gote retaliates on the 8-file,
    # both sides end up with pawns in hand.
    {"usi": "2e2d", "side": "sente", "comment": "▲2四歩: lance the 2-file pawn forward; opens the trade.", "eval": +110, "thinking_ms": 7100},
    {"usi": "2c2d", "side": "gote",  "comment": "△同歩: gote takes back with the rank-c pawn. Sente loses a pawn, gote captures one.", "eval":  +45, "thinking_ms": 4300},
    {"usi": "2h2d", "side": "sente", "comment": "▲同飛: rook lifts to 2d and recaptures. Sente now holds a pawn in hand.",            "eval":  +95, "thinking_ms": 6800},
    {"usi": "8e8f", "side": "gote",  "comment": "△8六歩: gote opens the 8-file trade.",                                                "eval":  +30, "thinking_ms": 5400},
    {"usi": "8g8f", "side": "sente", "comment": "▲同歩: sente recaptures with the 8g pawn — also picks up a pawn for the hand.",      "eval":  +75, "thinking_ms": 5900},
    {"usi": "8b8f", "side": "gote",  "comment": "△同飛: gote rook drops to 8f and takes; both sides now hold pawns.",                  "eval":  +25, "thinking_ms": 7200},
]

# Eval threshold for the SPC alarm — when |eval| swings by this much in a
# single half-move, the demo treats it as a "moment of truth".
_EVAL_SWING_ALARM = 35


def _usi_to_indices(usi: str) -> tuple[int, int, int, int, bool]:
    """USI '7g7f' → (from_row, from_col, to_row, to_col, promote)."""
    # File 1..9 (right to left). Col index 0 = file 9 (leftmost on screen).
    files = "987654321"
    ranks = "abcdefghi"
    f1 = files.index(usi[0])
    r1 = ranks.index(usi[1])
    f2 = files.index(usi[2])
    r2 = ranks.index(usi[3])
    promote = len(usi) > 4 and usi[4] == "+"
    return r1, f1, r2, f2, promote


_FILES_FULLWIDTH = "１２３４５６７８９"
_RANKS_KANJI = "一二三四五六七八九"


def _usi_to_kifu(
    piece_before: str,
    usi: str,
    side: str,
    *,
    thinking_ms: int | None = None,
) -> str:
    """Convert a USI half-move to traditional Japanese kifu notation.

    Examples (sente moves first, gote with △):
        '7g7f',  P  → '▲７六歩'
        '3c3d',  p  → '△３四歩'
        '8h2b+', B  → '▲２二角成'

    With ``thinking_ms`` set, append a parenthesised time so the audit
    pane reads like a real broadcast (``▲７六歩 (2.4秒)``).
    """
    base = piece_before.lstrip("+").upper()
    if base == "K" and not piece_before.startswith("+"):
        # Side-aware king glyph: ▲ → 玉, △ → 王.
        kanji = _king_kanji(is_gote=(side == "gote"))
    else:
        kanji = _PIECE_KANJI.get(base, "?")
    file_full = _FILES_FULLWIDTH[int(usi[2]) - 1]
    rank_kanji = _RANKS_KANJI["abcdefghi".index(usi[3])]
    side_mark = "▲" if side == "sente" else "△"
    promo_suffix = "成" if (len(usi) > 4 and usi[4] == "+") else ""
    time_suffix = ""
    if thinking_ms is not None:
        secs = thinking_ms / 1000.0
        time_suffix = f" ({secs:.1f}秒)" if secs >= 1.0 else f" ({thinking_ms}ms)"
    return f"{side_mark}{file_full}{rank_kanji}{kanji}{promo_suffix}{time_suffix}"


def _apply(board: list[list[str]], usi: str) -> str:
    """Apply USI move to the board in place. Returns the captured piece (if any)."""
    r1, c1, r2, c2, promote = _usi_to_indices(usi)
    piece = board[r1][c1]
    captured = board[r2][c2] if board[r2][c2] != "." else ""
    board[r2][c2] = piece if not promote else f"+{piece}"
    board[r1][c1] = "."
    return captured


_PIECE_KANJI: dict[str, str] = {
    "P": "歩", "L": "香", "N": "桂", "S": "銀", "G": "金",
    "B": "角", "R": "飛", "K": "玉",
    # Promoted pieces — single-kanji forms used in real Shogi notation.
    "+P": "と", "+L": "杏", "+N": "圭", "+S": "全",
    "+B": "馬", "+R": "龍",
}


def _king_kanji(*, is_gote: bool) -> str:
    """Traditional Shogi convention: sente (above-rank) plays 玉将 ("玉"),
    gote (below-rank) plays 王将 ("王"). Same piece, different glyph —
    showing both makes the side instantly readable in the kifu pane and on
    the board, even if the colour markup gets stripped (e.g. plain text
    log file)."""
    return "王" if is_gote else "玉"


def _piece_to_kanji(cell: str) -> str:
    """Map a board cell to a Rich-markup kanji glyph.

    - sente (uppercase)  → plain kanji         (default fg, e.g. white)
    - gote  (lowercase)  → [bright_red]kanji[/bright_red]
    - empty              → 中点 '・'           (full-width centre dot)

    Note: we used to wrap gote pieces in [reverse]…[/reverse] for an
    inverted background. Rich's SVG export rendered each reversed cell as
    a separate <text> element while the rest of the row was a single
    <text>, so gote rows came out at a slightly different width than
    sente rows. Switching to a plain colour keeps every cell on the same
    rendering path → identical column rhythm.
    """
    if cell == "." or cell == "":
        # Wrap the empty marker in a markup tag too, so every cell goes
        # through the same SVG rendering path as the coloured pieces below.
        # Without this, sente rows (plain text) get coalesced into a single
        # <text> element while gote rows (markup) become per-cell <text>s,
        # and the renderer ends up painting them at slightly different
        # widths → the board visibly skews from the top down to the bottom.
        return "[default]・[/default]"
    promoted = cell.startswith("+")
    base = cell[1:] if promoted else cell
    is_gote = base.islower()
    if not promoted and base.upper() == "K":
        # 先手玉 / 後手王 — traditional Shogi distinction.
        glyph = _king_kanji(is_gote=is_gote)
    else:
        key = ("+" + base.upper()) if promoted else base.upper()
        glyph = _PIECE_KANJI.get(key, "？")
    colour = "bright_red" if is_gote else "default"
    return f"[{colour}]{glyph}[/{colour}]"


def _format_hand(hand: dict[str, int], side: str) -> str:
    """Format a captured-piece dict (e.g. 'sente の持ち駒: 歩 x2 角')."""
    if not hand:
        body = "なし"
    else:
        # Iterate in a fixed order so the hand always reads the same way.
        order = ["P", "L", "N", "S", "G", "B", "R"]
        parts: list[str] = []
        for k in order:
            n = hand.get(k, 0)
            if not n:
                continue
            kanji = _PIECE_KANJI.get(k, "?")
            parts.append(f"{kanji} x{n}" if n > 1 else kanji)
        body = " ".join(parts) if parts else "なし"
    label = "[bright_red]☖ 後手[/bright_red]" if side == "gote" else "☗ 先手"
    return f"  {label} の持ち駒: {body}"


def _render_board(
    board: list[list[str]],
    *,
    sente_hand: dict[str, int] | None = None,
    gote_hand: dict[str, int] | None = None,
) -> str:
    """Render the board with kanji pieces, plus capture hands above and below.

    Sente pieces appear in plain colour; gote pieces are tagged
    ``[bright_red]…[/bright_red]`` so a real terminal (and the SVG export)
    visibly separates the two sides.
    """
    # Files 9..1 across the top; full-width digits keep the column spacing.
    files = "  ９ ８ ７ ６ ５ ４ ３ ２ １"
    rows: list[str] = []
    # Captured-by-gote hand sits above the board (gote sits at the top edge).
    rows.append(_format_hand(gote_hand or {}, side="gote"))
    rows.append(files)
    rows.append("  ┌" + "──" * 9 + "┐")
    ranks = "一二三四五六七八九"
    for r, row in enumerate(board):
        cells = "".join(_piece_to_kanji(c) for c in row)
        rows.append(f"{ranks[r]}│{cells}│")
    rows.append("  └" + "──" * 9 + "┘")
    rows.append(_format_hand(sente_hand or {}, side="sente"))
    return "\n".join(rows)


class ShogiScenario(DemoScenario):
    """Replay a 14-move scripted game between two LLMs (mocked)."""

    name = "shogi"
    i18n_key = "shogi"
    default_pause = 0.55  # let the eye keep up with the board state

    sensor_pane_title_key = "scenario.shogi.sensor_pane_title"
    spc_pane_title_key = "scenario.shogi.spc_pane_title"
    audit_pane_title_key = "scenario.shogi.audit_pane_title"
    narration_pane_title_key = "scenario.shogi.narration_pane_title"
    # Reshape the narration pane to fit a full 9x9 board + a couple of
    # commentary lines, and only keep the latest position visible so the
    # user always sees the *current* state of the game. The audit pane
    # gets enough room (and scrollback) to show the entire kifu.
    narration_pane_height = "55%"
    narration_max_entries = 1
    audit_pane_height = "32%"
    audit_max_entries = 30

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.shogi.intro",
            title_key="scenario.shogi.intro_title",
            sente=_PLAYERS["sente"],
            gote=_PLAYERS["gote"],
        )

        # Emit a 'shogi.game_start' audit entry so the audit pane (and the
        # JSONL log) record who is playing whom. The display string lands at
        # the top of the kifu pane and reads naturally next to the moves.
        yield Event(
            kind=EventKind.AUDIT,
            source_id="judge",
            payload={
                "event": "shogi.game_start",
                "sente": _PLAYERS["sente"],
                "gote": _PLAYERS["gote"],
                "display": f"☗ 先手: {_PLAYERS['sente']}  ☖ 後手: {_PLAYERS['gote']}",
            },
        )

        board = [row[:] for row in _INITIAL_SFEN_BOARD]
        sente_hand: dict[str, int] = {}
        gote_hand: dict[str, int] = {}

        # Show the starting position once so the SensorStream isn't blank
        # on turn 1 before the first move is applied.
        # Render the board as raw lines (no ``` fence): Rich treats the
        # contents of a code fence as literal text, so [bright_red]…[/]
        # markup on the gote pieces would not get parsed inside one.
        yield narrate(
            f"{_render_board(board, sente_hand=sente_hand, gote_hand=gote_hand)}\n"
            "**Position 0** — initial setup.",
            title="Position",
            allow_rich=True,
        )

        prev_eval = 0
        for ply, move in enumerate(_MOVES, start=1):
            # Capture the moving piece *before* applying the move, so we can
            # build the kifu string and the AuditLogView can show '▲７六歩'.
            r1, c1, _r2, _c2, _ = _usi_to_indices(move["usi"])
            piece_before = board[r1][c1]
            kifu = _usi_to_kifu(
                piece_before,
                move["usi"],
                move["side"],
                thinking_ms=move.get("thinking_ms"),
            )

            captured = _apply(board, move["usi"])
            # Move the captured piece to the moving side's hand.
            if captured and captured != ".":
                base = captured.lstrip("+").upper()
                if move["side"] == "sente":
                    sente_hand[base] = sente_hand.get(base, 0) + 1
                else:
                    gote_hand[base] = gote_hand.get(base, 0) + 1

            # SENSOR: eval score over the game (positive = sente lead).
            yield Event(
                kind=EventKind.SENSOR,
                source_id=move["side"],
                payload={
                    "sensor_id": "eval_score",
                    "value": int(move["eval"]),
                    "ply": ply,
                    "side": move["side"],
                    "usi": move["usi"],
                    # Snapshot state for downstream tools (Qt viewer, replay).
                    "board": ["".join(r) for r in board],
                    "captured": captured,
                },
            )

            # AUDIT: each half-move with full context, plus a pre-formatted
            # `display` string in traditional kifu (▲７六歩 / △３四歩) so the
            # audit pane reads like a real shogi broadcast.
            yield Event(
                kind=EventKind.AUDIT,
                source_id=move["side"],
                payload={
                    "event": "shogi.move",
                    "ply": ply,
                    "side": move["side"],
                    "usi": move["usi"],
                    "kifu": kifu,
                    "display": kifu,
                    "captured": captured or None,
                    "eval": move["eval"],
                    "thinking_ms": move.get("thinking_ms"),
                },
            )

            swing = abs(move["eval"] - prev_eval)
            if swing >= _EVAL_SWING_ALARM:
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id="judge",
                    payload={
                        "sensor_id": "eval_score",
                        "value": move["eval"],
                        "threshold": _EVAL_SWING_ALARM,
                        "cusum": swing,
                        "rule": "eval_swing",
                        "ply": ply,
                        "usi": move["usi"],
                    },
                )

            # Update the board narration after **every half-move**, so the
            # user sees the position after sente's reply *and* after gote's
            # reply — like a real shogi broadcast.
            yield narrate(
                f"{_render_board(board, sente_hand=sente_hand, gote_hand=gote_hand)}\n"
                f"**Ply {ply}** ({move['side']} {move['usi']} = {kifu})  "
                f"eval = **{move['eval']:+d}**\n{move['comment']}",
                title=f"Ply {ply}",
                allow_rich=True,
            )

            prev_eval = move["eval"]

        # Closing audit summary so post-game tools (or a future replay
        # viewer) can re-derive the whole game from a single Event.
        yield Event(
            kind=EventKind.AUDIT,
            source_id="judge",
            payload={
                "event": "shogi.game_end",
                "plies": len(_MOVES),
                "final_eval": _MOVES[-1]["eval"],
                "moves_usi": [m["usi"] for m in _MOVES],
            },
        )

        # Render the take-away *with the final board* so that, when the
        # narration pane is configured to keep only the latest entry
        # (narration_max_entries = 1), the user still sees the position
        # they should remember instead of pure prose.
        final_board = _render_board(board, sente_hand=sente_hand, gote_hand=gote_hand)
        takeaway_text = t(
            "scenario.shogi.takeaway",
            plies=len(_MOVES),
            final_eval=_MOVES[-1]["eval"],
        )
        yield narrate(
            f"{final_board}\n{takeaway_text}",
            title=t("scenario.shogi.takeaway_title"),
            allow_rich=True,
        )
