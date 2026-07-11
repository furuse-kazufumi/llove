"""Generic game registry — maps a game name to a :class:`GameEngine` factory.

Scope: this registry covers games built on :mod:`llove.games.base` (the
generic ``run_game`` + ``GameEngine`` / ``GamePlayer`` stack). **shogi is
deliberately not here** — it lives in :mod:`llove.shogi` with its own
``Engine`` / ``Player`` / loop (a separate stack kept from the MVP2a
one-file-at-a-time build).

Only ``LoveApp._start_game`` dispatches *by name* through this registry: it
special-cases shogi and falls through to ``make_engine(game)`` for every other
name, so a game registered here is immediately reachable from ``:play <game>``.
The CLI (``llove play``) does **not** fall through — it is a fixed set of Click
subcommands (``shogi``, ``chess``), so adding a game here makes it playable from
the palette but a matching ``llove play <game>`` subcommand must be added by
hand (see the sync note on ``_ENGINE_FACTORIES``).

Engine construction is lazy: importing this module does **not** import
``python-chess``. ``make_engine("chess")`` constructs a ``ChessEngine``, and
*that* is what raises :class:`~llove.games.chess.engine.EngineUnavailable`
when the ``[chess]`` extra is missing — so the missing-dependency hint reaches
the user with the right install command.
"""

from __future__ import annotations

from collections.abc import Callable

from llove.games.base.engine import GameEngine


def _make_chess() -> GameEngine:
    # Lazy import so a default install (no ``[chess]`` extra) can still import
    # this module. ChessEngine() raises EngineUnavailable when python-chess is
    # absent — the caller surfaces its install hint.
    from llove.games.chess.engine import ChessEngine

    return ChessEngine()


#: game name → zero-arg engine factory. Keep names in sync with the CLI
#: (``llove play <game>``) and the palette (``:play <game>``).
_ENGINE_FACTORIES: dict[str, Callable[[], GameEngine]] = {
    "chess": _make_chess,
}


def available_games() -> list[str]:
    """Sorted list of games this registry can build (``["chess"]`` today).

    Does **not** include shogi — see the module docstring.
    """
    return sorted(_ENGINE_FACTORIES)


def is_registered(game: str) -> bool:
    """Whether ``game`` has a generic engine factory here."""
    return game in _ENGINE_FACTORIES


def make_engine(game: str) -> GameEngine:
    """Construct the :class:`GameEngine` for ``game``.

    Raises
    ------
    ValueError
        When ``game`` is not a registered generic game.
    llove.games.chess.engine.EngineUnavailable
        When the engine's optional dependency (e.g. ``[chess]``) is missing —
        propagated from the concrete engine constructor with an install hint.
    """
    factory = _ENGINE_FACTORIES.get(game)
    if factory is None:
        known = ", ".join(available_games()) or "(none)"
        raise ValueError(f"unknown game {game!r}; available: {known}")
    return factory()


__all__ = ["available_games", "is_registered", "make_engine"]
