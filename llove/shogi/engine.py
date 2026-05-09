"""Thin legality engine wrapping ``python-shogi``.

We delegate the actual rule logic (piece moves, two-pawn / nifu, drop-pawn
mate / uchifuzume, going-nowhere pieces / yukidokoronai-koma, leaving the
king in check / oute-houchi, fourfold repetition / sennichite) to the
``python-shogi`` library. The engine here just exposes the slice of API the
rest of llove actually needs, in stable types we control.

``python-shogi`` is GPL-3.0 and ships behind the ``[shogi]`` extras. If the
user runs ``llove play shogi`` without installing the extras we raise
:class:`EngineUnavailable` with a copy that tells them exactly which
``pip install`` to run, instead of an opaque ``ModuleNotFoundError``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — type-only
    pass


class EngineUnavailable(RuntimeError):
    """Raised when ``python-shogi`` is not installed.

    We surface a concrete install hint rather than letting the bare
    :class:`ModuleNotFoundError` bubble up, because the typical user of
    ``llove play shogi`` will not have read the README's extras section.
    """


@dataclass(frozen=True)
class LegalityResult:
    """Outcome of validating a USI move against the current position.

    ``ok`` is the only field a caller usually needs. ``reason`` is a short
    English string suitable for an audit log entry; we keep it stable across
    versions of ``python-shogi`` by mapping their internals into our own
    vocabulary.
    """

    ok: bool
    reason: str = ""


# Stable termination reason vocabulary. Loops persist these into the JSONL
# log, so changing a string is a breaking change for downstream replay
# tools — add new values rather than renaming existing ones.
TERM_CHECKMATE = "checkmate"
TERM_RESIGN_ILLEGAL = "resign_illegal"
TERM_RESIGN_PLAYER = "resign_player"
TERM_SENNICHITE = "sennichite"
TERM_MAX_PLY = "max_ply"
TERM_STALEMATE = "stalemate"  # impossible in real shogi, kept for safety


def _import_shogi() -> Any:
    """Import ``python-shogi`` lazily and translate ImportError to a
    user-friendly :class:`EngineUnavailable`.
    """
    try:
        import shogi  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover — guarded by extras tests
        msg = (
            "python-shogi is not installed. The `llove play shogi` command "
            "needs it for legality checking. Install with:\n"
            "    pip install 'llmesh-llove[shogi]'"
        )
        raise EngineUnavailable(msg) from exc
    return shogi


class Engine:
    """Stateful shogi position with legality checking.

    The engine owns one ``shogi.Board`` instance and exposes a stable,
    minimal API to the rest of llove. All rule edge cases (uchifuzume,
    nifu, oute-houchi, yukidokoronai-koma) are validated transparently by
    ``shogi.Board.is_legal``; we do not duplicate them here.
    """

    def __init__(self, sfen: str | None = None) -> None:
        self._shogi = _import_shogi()
        self._board = self._shogi.Board() if sfen is None else self._shogi.Board(sfen)

    # ------------------------------------------------------------------
    # state queries
    # ------------------------------------------------------------------
    @property
    def sfen(self) -> str:
        """Current position as an SFEN string (e.g. for replay / Qt viewer)."""
        return self._board.sfen()

    @property
    def turn(self) -> str:
        """``"sente"`` (BLACK / first player) or ``"gote"`` (WHITE / second)."""
        return "sente" if self._board.turn == self._shogi.BLACK else "gote"

    @property
    def ply(self) -> int:
        """Number of half-moves played so far."""
        return len(self._board.move_stack)

    @property
    def move_history_usi(self) -> list[str]:
        """Move history in USI notation, oldest first."""
        return [m.usi() for m in self._board.move_stack]

    def legal_moves_usi(self) -> list[str]:
        """All legal half-moves in the current position, USI-encoded."""
        return [m.usi() for m in self._board.legal_moves]

    def is_check(self) -> bool:
        return bool(self._board.is_check())

    def is_checkmate(self) -> bool:
        return bool(self._board.is_checkmate())

    def is_fourfold_repetition(self) -> bool:
        """Sennichite — same position 4 times = draw (or loss for the side
        repeating perpetual check; we don't distinguish in the engine and let
        the loop call it a sennichite draw)."""
        return bool(self._board.is_fourfold_repetition())

    def is_stalemate(self) -> bool:
        """Pure stalemate is impossible in real shogi (drops give you a move),
        but ``python-shogi`` exposes the helper, so we forward it for tests."""
        return bool(self._board.is_stalemate())

    # ------------------------------------------------------------------
    # move validation / application
    # ------------------------------------------------------------------
    def validate(self, usi: str) -> LegalityResult:
        """Check whether ``usi`` is a legal half-move *without* applying it.

        Translates the various failure modes into a stable ``reason`` string
        so the audit log can read ``"illegal: nifu"`` instead of a raw
        Python exception.
        """
        # 1. Parse — bad syntax is its own failure mode.
        try:
            move = self._shogi.Move.from_usi(usi)
        except (ValueError, KeyError, IndexError) as exc:
            return LegalityResult(ok=False, reason=f"parse_error: {exc}")

        # 2. Legal in this position?  python-shogi rolls every shogi-specific
        #    rule (oute-houchi, nifu, uchifuzume, yukidokoronai-koma, drop-on-
        #    occupied, wrong-side-to-move) into ``is_legal``.
        if self._board.is_legal(move):
            return LegalityResult(ok=True)

        # 3. Try to give a more specific reason. ``python-shogi`` keeps the
        #    pseudo_legal flag and a few helpers, so we can at least split
        #    "wrong move shape" from "leaves king in check / forbidden drop".
        if not self._board.is_pseudo_legal(move):
            return LegalityResult(ok=False, reason="illegal: not pseudo-legal")

        # Pseudo-legal but not legal → it's a king-safety / shogi-specific rule
        # (oute-houchi, nifu, uchifuzume, drop on a square that creates one of
        # those). We don't try to disambiguate further; the caller will count
        # the strike and move on.
        return LegalityResult(ok=False, reason="illegal: rule violation")

    def push_usi(self, usi: str) -> LegalityResult:
        """Validate and apply ``usi``. Returns the same result as :meth:`validate`.

        Only mutates state when the result is ``ok``.
        """
        result = self.validate(usi)
        if not result.ok:
            return result
        self._board.push(self._shogi.Move.from_usi(usi))
        return result
