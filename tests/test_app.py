"""Headless tests for the Textual app via run_test().

Textual ships an in-process pilot that drives the App without a real terminal.
We use it to:
    1. Verify the App boots without exception
    2. Verify keyboard bindings respond
    3. Verify the narration variant adds the extra pane
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from llove.app import LoveApp
from llove.events import Event, EventKind
from llove.sources.base import DataSource


class _StaticSource(DataSource):
    """Deterministic, finite source for tests — yields a few events then ends."""

    name = "static"

    def __init__(self, events: list[Event]) -> None:
        self._events = events

    async def stream(self) -> AsyncIterator[Event]:
        for ev in self._events:
            yield ev
            await asyncio.sleep(0)  # let the event loop schedule the receiver


@pytest.mark.asyncio
async def test_app_boots_without_exception() -> None:
    src = _StaticSource(
        [
            Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": 1.0}),
            Event(kind=EventKind.AUDIT, payload={"event": "ok"}),
        ]
    )
    app = LoveApp(src)
    async with app.run_test(size=(120, 40)) as pilot:
        # Give the consumer a brief moment to drain.
        await pilot.pause(0.05)
        # The default 3-pane layout means narration view is absent.
        assert not app._with_narration


@pytest.mark.asyncio
async def test_app_with_narration_pane_exposes_extra_view() -> None:
    src = _StaticSource(
        [
            Event(kind=EventKind.NARRATION, payload={"text": "**hello** world", "title": "T"}),
        ]
    )
    app = LoveApp(src, with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        names = [type(v).__name__ for v in app._views]
        assert "NarrationView" in names


@pytest.mark.asyncio
async def test_app_responds_to_pause_toggle() -> None:
    src = _StaticSource([Event(kind=EventKind.AUDIT, payload={"event": "ok"})])
    app = LoveApp(src)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        assert app._paused is False
        await pilot.press("space")
        await pilot.pause(0.05)
        assert app._paused is True
        await pilot.press("space")
        await pilot.pause(0.05)
        assert app._paused is False


@pytest.mark.asyncio
async def test_app_reset_clears_view_rows() -> None:
    src = _StaticSource(
        [
            Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": 1.0}),
            Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": 2.0}),
        ]
    )
    app = LoveApp(src)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        rows_before = len(app._sensor._rows)
        assert rows_before > 0
        await pilot.press("r")
        await pilot.pause(0.05)
        assert len(app._sensor._rows) == 0


@pytest.mark.asyncio
async def test_app_quit_binding_terminates_cleanly() -> None:
    src = _StaticSource([Event(kind=EventKind.AUDIT, payload={"event": "ok"})])
    app = LoveApp(src)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        await pilot.press("q")
        # If the app didn't quit, the context manager would hang on exit.


@pytest.mark.asyncio
async def test_app_continues_when_a_view_raises() -> None:
    """A misbehaving view must not bring down the app."""

    class _BadView:
        name = "bad"
        title = "bad"

        def feed(self, event: Event) -> None:
            raise RuntimeError("boom")

    src = _StaticSource(
        [Event(kind=EventKind.SENSOR, payload={"sensor_id": "s1", "value": 1.0})]
    )
    app = LoveApp(src)
    async with app.run_test(size=(120, 40)) as pilot:
        # Inject the bad view into the dispatch list after compose ran.
        app._views.append(_BadView())
        await pilot.pause(0.1)
        # If the app survived this far without raising, the assertion passes.
        assert True
