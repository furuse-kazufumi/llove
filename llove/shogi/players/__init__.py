"""llove.shogi.players — pluggable LLM (and mock) players for shogi.

Currently shipping:

* ``mock`` — scripted player, mirrors the MVP1 demo so tests don't need a network
  (``mock:script`` plays the canonical opening; ``mock:illegal`` always proposes
  invalid moves so we can exercise the loop's resignation path)
* ``anthropic`` — Claude-family LLMs via the ``anthropic`` SDK *(MVP2b)*
* ``ollama`` — local LLMs via the Ollama HTTP API *(MVP2b)*

The concrete provider classes are imported lazily by ``parse_provider_spec``
so that, on a default install, ``import llove.shogi`` does **not** require
the optional SDKs.
"""

from __future__ import annotations

from llove.shogi.players.base import Move, Player, parse_provider_spec

__all__ = ["Move", "Player", "parse_provider_spec"]
