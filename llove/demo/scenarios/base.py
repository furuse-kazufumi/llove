"""Base interface for demo scenarios.

Scenarios pull their human-facing strings from the i18n catalog under
``llove/i18n/locales/<lang>.toml``. Each scenario class declares an i18n
``key`` (e.g. ``"firewall"``); title/description are then resolved lazily
so locale switches at runtime work without re-instantiating.
"""

from __future__ import annotations

import asyncio
from abc import abstractmethod
from collections.abc import AsyncIterator

from llove.events import Event, EventKind
from llove.i18n import t
from llove.sources.base import DataSource


def narrate(text: str, *, title: str | None = None) -> Event:
    """Build a NARRATION event in one call."""
    payload: dict = {"text": text}
    if title:
        payload["title"] = title
    return Event(kind=EventKind.NARRATION, source_id="scenario", payload=payload)


def narrate_key(text_key: str, *, title_key: str | None = None, **subs: object) -> Event:
    """Build a NARRATION event by resolving i18n keys.

    Convenience wrapper used by every shipping scenario so that all narration
    lives in TOML and switching locale at runtime takes effect immediately.
    """
    text = t(text_key, **subs)
    title = t(title_key) if title_key else None
    return narrate(text, title=title)


class DemoScenario(DataSource):
    """A scripted sequence of llove Events with attached narration.

    Each scenario covers one or more LLMesh capabilities and is fully
    self-contained (no network, no LLMesh node required). Subclasses override
    ``events`` with their script; ``stream`` wraps that with realistic spacing.

    Subclasses set ``i18n_key`` to the leaf under ``[scenario.*]`` in the TOML
    catalog. The default ``title`` / ``description`` properties resolve via i18n.
    """

    name: str = "scenario"
    i18n_key: str = "scenario"
    default_pause: float = 0.4  # seconds between events

    # Optional per-scenario pane label overrides. Each is an i18n key the app
    # resolves at mount time. None = use the default ui.pane.<name>.title.
    # Use these to keep terminology natural in non-LLMesh-flavoured demos
    # (e.g. coin_toss should say "Toss outcomes" not "SensorEvent stream").
    sensor_pane_title_key: str | None = None
    spc_pane_title_key: str | None = None
    audit_pane_title_key: str | None = None
    narration_pane_title_key: str | None = None

    @property
    def title(self) -> str:
        return t(f"scenario.{self.i18n_key}.title")

    @property
    def description(self) -> str:
        return t(f"scenario.{self.i18n_key}.description")

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
