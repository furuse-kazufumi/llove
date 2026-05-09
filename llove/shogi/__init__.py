"""llove.shogi — real shogi play loop with pluggable LLM players.

This package is the MVP2 evolution of the scripted ``llove demo --scenario shogi``.
The demo scenario is kept verbatim under ``llove.demo.scenarios.shogi`` and
remains the offline-friendly entry point. ``llove.shogi`` adds:

* a thin legality engine wrapping ``python-shogi`` (extras ``[shogi]``)
* a Player abstraction (mock today; anthropic / ollama / llmesh in MVP2b)
* a game loop that yields ``llove.events.Event``s into the existing TUI
  pipeline so the same panes light up as in the scripted demo

Public surface deliberately stays small. Sub-modules are imported lazily so
that, on a default install, ``import llove.shogi`` does **not** require the
``[shogi]`` extras until you actually instantiate ``Engine`` or call
``run_game``.
"""

from __future__ import annotations

from llove.shogi.engine import Engine, EngineUnavailable
from llove.shogi.loop import GameOutcome, run_game
from llove.shogi.players.base import Move, Player, ThinkResult, parse_provider_spec, make_player

__all__ = [
    "Engine",
    "EngineUnavailable",
    "GameOutcome",
    "Move",
    "Player",
    "ThinkResult",
    "make_player",
    "parse_provider_spec",
    "run_game",
]
