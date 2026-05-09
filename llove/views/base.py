"""View interface — the common shape every llove pane implements.

We use a plain base class instead of ``abc.ABC`` because Textual widgets bring
their own metaclass; mixing the two produces a metaclass conflict at import.
Subclasses are expected to override ``feed``; the default raises so missing
implementations fail loudly during development.
"""

from __future__ import annotations

from llove.events import Event


class View:
    """Renderable pane that ingests Events and updates its display."""

    name: str = "view"
    title: str = "view"

    def feed(self, event: Event) -> None:
        """Consume one Event. Must not block. Must not raise on malformed data."""
        raise NotImplementedError
