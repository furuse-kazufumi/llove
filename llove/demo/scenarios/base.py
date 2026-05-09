"""Base interface for demo scenarios."""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from llove.events import Event, EventKind
from llove.sources.base import DataSource


def narrate(text: str, *, title: str | None = None) -> Event:
    """Build a NARRATION event in one call."""
    payload: dict = {"text": text}
    if title:
        payload["title"] = title
    return Event(kind=EventKind.NARRATION, source_id="scenario", payload=payload)


class DemoScenario(ABC, DataSource):
    """A scripted sequence of llove Events with attached narration.

    Each scenario covers one or more LLMesh capabilities and is fully
    self-contained (no network, no LLMesh node required). Subclasses override
    ``events`` with their script; ``stream`` wraps that with realistic spacing.
    """

    name: str = "scenario"
    title: str = "Scenario"
    description: str = ""
    default_pause: float = 0.4  # seconds between events

    @abstractmethod
    async def events(self) -> AsyncIterator[Event]:
        """Yield the script of events. Implementations are async generators."""
        if False:  # pragma: no cover — typing hint
            yield Event(kind=EventKind.INFO)

    async def stream(self) -> AsyncIterator[Event]:
        async for ev in self.events():
            yield ev
            if self.default_pause > 0:
                await asyncio.sleep(self.default_pause)
