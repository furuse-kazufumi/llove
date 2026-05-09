"""Scripted shogi player — MVP1-compatible, no LLM.

``MockPlayer`` exists for three reasons:

1. **Tests.** The loop, the audit log, the JSONL log and the engine all
   need a deterministic player to assert against.
2. **Offline demos.** ``llove play shogi --sente mock --gote mock`` plays
   the canonical opening end-to-end with no network, no API keys.
3. **Failure-mode testing.** ``MockPlayer(model="illegal")`` always
   proposes obviously illegal moves, so the loop's "3 strikes → resign"
   path can be tested without crafting a custom backend.

Modes are selected by ``model`` (the part after ``mock:``):

* ``mock:script`` (default) — replay the demo scenario's `_MOVES` list.
  When the script runs out, the player resigns.
* ``mock:illegal`` — always propose ``"9z9z"`` (a malformed USI). The
  loop should hit 3 strikes within 3 plies and end the game.
* ``mock:resign`` — resign on the very first ply.
"""

from __future__ import annotations

import asyncio

from llove.shogi.players.base import Move, Player, ThinkResult


def _load_demo_script() -> list[tuple[str, int, str]]:
    """Pull the (USI, thinking_ms, comment) script out of the MVP1 demo
    scenario. Imported lazily so the regular Player path doesn't reach
    into demo-only code unless asked."""
    from llove.demo.scenarios.shogi import _MOVES  # type: ignore[attr-defined]

    return [
        (m["usi"], int(m.get("thinking_ms", 0)), str(m.get("comment", "")))
        for m in _MOVES
    ]


class MockPlayer(Player):
    """Deterministic player. ``model`` selects the variant."""

    def __init__(
        self,
        *,
        model: str = "script",
        side: str = "sente",
        thinking_ms_override: int | None = None,
    ) -> None:
        # Subset of legal model strings — guards against typos like ``mock:scrpt``.
        if model not in ("script", "illegal", "resign"):
            raise ValueError(
                f"mock player model must be one of 'script' / 'illegal' / 'resign', "
                f"got {model!r}"
            )
        self.provider = "mock"
        self.model = model
        self.name = f"mock:{model} ({side})"
        self._side = side
        # When set, every move's ``thinking_ms`` is overridden to this value.
        # Tests pass ``thinking_ms_override=0`` so the demo replay finishes in
        # milliseconds instead of multiple minutes of real-time sleep.
        self._thinking_ms_override = thinking_ms_override
        # Index into the demo script for the ``script`` variant.
        self._cursor = 0
        self._script: list[tuple[str, int, str]] | None = None

    async def think(self, engine):  # type: ignore[override]
        if self.model == "resign":
            return ThinkResult(
                move=None,
                resign=True,
                resign_reason="mock:resign always concedes on the first ply",
            )

        if self.model == "illegal":
            # Simulate a fixed 50ms "thinking" so the audit pane shows a
            # plausible timing field. The "9z9z" USI fails parse, which
            # the engine maps to ``parse_error`` — counted as one strike.
            await asyncio.sleep(0.05)
            return ThinkResult(
                move=Move(
                    usi="9z9z",
                    thinking_ms=50,
                    commentary="(mock:illegal — deliberately malformed)",
                )
            )

        # ``script`` mode: replay the demo opening, half-move by half-move,
        # ignoring whose turn it is (the engine will reject if the script
        # ever falls out of sync).
        if self._script is None:
            self._script = _load_demo_script()
        if self._cursor >= len(self._script):
            return ThinkResult(
                move=None,
                resign=True,
                resign_reason="mock:script exhausted — no further moves in the demo",
            )
        usi, thinking_ms, commentary = self._script[self._cursor]
        self._cursor += 1
        # Sleep in real time only when the LoveApp is driving us; tests pass
        # ``default_pause = 0.0`` by setting ``thinking_ms`` themselves.
        if thinking_ms > 0:
            await asyncio.sleep(thinking_ms / 1000.0)
        return ThinkResult(
            move=Move(usi=usi, thinking_ms=thinking_ms, commentary=commentary)
        )
