"""View ABC — the common interface every llove pane implements."""
from __future__ import annotations

from abc import ABC, abstractmethod

from llove.events import Event


class View(ABC):
    """Renderable pane that ingests Events and updates its display."""

    name: str = "view"
    title: str = "view"

    @abstractmethod
    def feed(self, event: Event) -> None:
        """Consume one Event. Must not block. Must not raise on malformed data."""
        raise NotImplementedError
