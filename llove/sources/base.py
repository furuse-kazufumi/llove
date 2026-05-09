"""DataSource ABC.

A DataSource yields ``Event``s asynchronously. Implementations live in this
package (``mock``, ``jsonl``, …) plus optional sub-packages enabled via
extras (``llmesh``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from llove.events import Event, EventKind


class DataSource(ABC):
    """Source that yields Events.

    Implementations should be **fail-closed**: when the underlying medium
    becomes unavailable, ``stream`` should stop producing rather than crash.
    """

    name: str = "datasource"

    @abstractmethod
    async def stream(self) -> AsyncIterator[Event]:
        """Yield events. Loop forever for live sources, finish for finite ones."""
        if False:  # pragma: no cover — purely a generator-typing hint
            yield Event(kind=EventKind.SENSOR)

    async def close(self) -> None:
        """Optional cleanup hook called by the App on teardown."""
        return None
