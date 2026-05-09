"""LoveApp — the Textual application that hosts panes and feeds them events."""
from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Static

from llove.events import Event
from llove.sources.base import DataSource
from llove.views.audit_log import AuditLogView
from llove.views.base import View
from llove.views.narration import NarrationView
from llove.views.sensor_stream import SensorStreamView
from llove.views.spc_chart import SPCChartView


class LoveApp(App):
    """Multi-pane Textual app for llove.

    Default layout (top → bottom):
        Header  (auto title + clock)
        Control row  (clickable Pause / Reset / Help / Quit buttons)
        Top row      SensorStream | SPCChart  (read-only displays)
        Audit log row                          (read-only display)
        Narration row (optional, when running a scenario)
        Footer  (keybinding hints; clicking a hint invokes the action)
    """

    CSS = """
    Screen {
        background: $surface;
    }
    #control-row {
        height: 3;
        padding: 0 1;
        background: $boost;
    }
    #control-row Button {
        margin: 0 1;
        min-width: 12;
    }
    #hint-bar {
        height: 1;
        padding: 0 2;
        background: $panel;
        color: $text-muted;
    }
    .top-row {
        height: 1fr;
    }
    """

    BINDINGS = [  # noqa: RUF012 — Textual reads BINDINGS as a class-level list, not per-instance.
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
        # Explicit control row — these are obviously clickable, distinguishing
        # them from the read-only display panes below.
        with Horizontal(id="control-row"):
            self._btn_pause = Button("⏸ Pause", id="btn-pause", variant="primary")
            self._btn_reset = Button("⟲ Reset", id="btn-reset", variant="warning")
            yield self._btn_pause
            yield self._btn_reset
            yield Button("? Help", id="btn-help", variant="default")
            yield Button("✕ Quit", id="btn-quit", variant="error")
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
                v._rows.clear()

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        # Keep the visible button label in sync so users see the new state.
        if hasattr(self, "_btn_pause"):
            self._btn_pause.label = "▶ Resume" if self._paused else "⏸ Pause"

    def action_show_help(self) -> None:
        self.bell()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Wire the top-row buttons to the same actions as the keybindings."""
        action_by_id = {
            "btn-pause": self.action_toggle_pause,
            "btn-reset": self.action_reset,
            "btn-help": self.action_show_help,
            "btn-quit": self.action_quit,
        }
        handler = action_by_id.get(event.button.id or "")
        if handler is not None:
            handler()
