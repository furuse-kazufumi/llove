"""LoveApp — the Textual application that hosts panes and feeds them events."""
from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header

from llove.events import Event
from llove.sources.base import DataSource
from llove.views.audit_log import AuditLogView
from llove.views.base import View
from llove.views.narration import NarrationView
from llove.views.sensor_stream import SensorStreamView
from llove.views.spc_chart import SPCChartView


class LoveApp(App):
    """Multi-pane Textual app for llove.

    Default layout: SensorStream | SPCChart on top, AuditLog below.
    With ``with_narration=True``: a fourth NarrationView is added at the bottom
    so demo scenarios can show running commentary.
    """

    CSS = """
    Screen {
        background: $surface;
    }
    .top-row {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reset", "Reset views"),
        ("space", "toggle_pause", "Pause/Resume"),
        ("h", "show_help", "Help"),
    ]

    TITLE = "💗 llove"
    SUB_TITLE = "Made with llove — Watch your LLMesh with llove"

    def __init__(self, source: DataSource, *, with_narration: bool = False) -> None:
        super().__init__()
        self._source = source
        self._views: list[View] = []
        self._paused = False
        self._task: asyncio.Task[None] | None = None
        self._with_narration = with_narration

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            with Horizontal(classes="top-row"):
                self._sensor = SensorStreamView()
                self._spc = SPCChartView()
                yield self._sensor
                yield self._spc
            self._audit = AuditLogView()
            yield self._audit
            self._narration: NarrationView | None = None
            if self._with_narration:
                self._narration = NarrationView()
                yield self._narration
        yield Footer()
        self._views = [self._sensor, self._spc, self._audit]
        if self._narration is not None:
            self._views.append(self._narration)

    async def on_mount(self) -> None:
        self._task = asyncio.create_task(self._consume())

    async def on_unmount(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        await self._source.close()

    async def _consume(self) -> None:
        try:
            async for ev in self._source.stream():
                if self._paused:
                    continue
                self._dispatch(ev)
        except asyncio.CancelledError:
            return

    def _dispatch(self, event: Event) -> None:
        for v in self._views:
            try:
                v.feed(event)
            except Exception:  # nosec B110 — fail-closed: a broken view must not kill the app.
                continue

    def action_reset(self) -> None:
        for v in self._views:
            if hasattr(v, "_rows"):
                v._rows.clear()  # noqa: SLF001 — public reset helper coming in v0.2.

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused

    def action_show_help(self) -> None:
        self.bell()
