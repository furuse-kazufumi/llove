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


def narrate(text: str, *, title: str | None = None, allow_rich: bool = False) -> Event:
    """Build a NARRATION event in one call.

    ``allow_rich`` lets a scenario opt out of NarrationView's '[' escaping
    so it can use Rich markup like ``[reverse]…[/reverse]`` in the body
    (used by shogi to invert gote pieces). Only set this when the scenario
    *itself* writes the markup string — never propagate user-supplied text
    with this flag on.
    """
    payload: dict = {"text": text}
    if title:
        payload["title"] = title
    if allow_rich:
        payload["allow_rich"] = True
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

    # Optional layout hints for scenarios that want a non-default pane size.
    # Use these sparingly — they reshape the whole window. Example: shogi
    # needs a tall narration pane to fit a 9x9 board *and* a tall audit
    # pane so the whole game scoresheet stays visible.
    narration_pane_height: str | None = None     # CSS length, e.g. "28" or "70%"
    narration_max_entries: int | None = None     # deque maxlen; e.g. 1 = always
                                                  # show only the latest beat
    audit_pane_height: str | None = None         # CSS length, e.g. "20" or "30%"
    audit_max_entries: int | None = None         # deque maxlen; e.g. 30

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
