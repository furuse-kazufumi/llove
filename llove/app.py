"""LoveApp — the Textual application that hosts panes and feeds them events."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TextIO

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Static

from llove.events import Event
from llove.i18n import t
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
    SUB_TITLE = "Made with llove"

    def __init__(
        self,
        source: DataSource,
        *,
        with_narration: bool = False,
        log_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._source = source
        self._views: list[View] = []
        self._paused = False
        self._task: asyncio.Task[None] | None = None
        self._with_narration = with_narration
        # Optional event-log path. When set, every dispatched Event is
        # appended as a JSON line so the run can be replayed with
        # `llove tail` (and serves as a permanent record — e.g. a full
        # shogi kifu).
        self._log_path = log_path
        self._log_file: TextIO | None = None
        # Pull localised app subtitle so it changes with --lang.
        self.sub_title = t("ui.subtitle")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Explicit control row — these are obviously clickable, distinguishing
        # them from the read-only display panes below.
        with Horizontal(id="control-row"):
            self._btn_pause = Button(t("ui.button.pause"), id="btn-pause", variant="primary")
            self._btn_reset = Button(t("ui.button.reset"), id="btn-reset", variant="warning")
            yield self._btn_pause
            yield self._btn_reset
            yield Button(t("ui.button.help"), id="btn-help", variant="default")
            yield Button(t("ui.button.quit"), id="btn-quit", variant="error")
        # Hint bar makes the read/write split unambiguous at a glance.
        yield Static(t("ui.hint_bar"), id="hint-bar")
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
        # Open the event log up-front (append) so every dispatched event is
        # captured. We close it on unmount.
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = self._log_path.open("a", encoding="utf-8")
        # If the source is a DemoScenario, let it rename pane titles and
        # reshape the narration pane so that non-LLMesh-flavoured demos
        # (coin_toss, shogi, …) don't have to fit the LLMesh template.
        from collections import deque

        from llove.demo.scenarios.base import DemoScenario

        if isinstance(self._source, DemoScenario):
            s = self._source
            if s.sensor_pane_title_key:
                self._sensor.border_title = t(s.sensor_pane_title_key)
            if s.spc_pane_title_key:
                self._spc.border_title = t(s.spc_pane_title_key)
            if s.audit_pane_title_key:
                self._audit.border_title = t(s.audit_pane_title_key)
            if s.narration_pane_title_key and self._narration is not None:
                self._narration.border_title = t(s.narration_pane_title_key)
            if self._narration is not None:
                # Resize the narration pane (e.g. shogi needs ~28 rows for
                # a 9x9 board) and shrink its scrollback so the *latest*
                # board is never pushed off-screen by older snapshots.
                if s.narration_pane_height:
                    self._narration.styles.height = s.narration_pane_height
                if s.narration_max_entries:
                    self._narration._entries = deque(
                        self._narration._entries,
                        maxlen=s.narration_max_entries,
                    )
            # Audit pane reshape: shogi keeps the full kifu visible.
            if s.audit_pane_height:
                self._audit.styles.height = s.audit_pane_height
            if s.audit_max_entries:
                self._audit._rows = deque(
                    self._audit._rows,
                    maxlen=s.audit_max_entries,
                )
        self._task = asyncio.create_task(self._consume())

    async def on_unmount(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        if self._log_file is not None:
            try:
                self._log_file.close()
            finally:
                self._log_file = None
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
        if self._log_file is not None:
            try:
                self._log_file.write(event.model_dump_json() + "\n")
                self._log_file.flush()
            except Exception:  # nosec B110 — fail-closed: a broken log must not kill the app.
                pass
        for v in self._views:
            try:
                v.feed(event)
            except Exception:  # nosec B110 — fail-closed: a broken view must not kill the app.
                continue

    def action_reset(self) -> None:
        # Reset = "play the scenario from the beginning". Cancel the current
        # consume task, clear every view, then for DemoScenarios re-instantiate
        # the source and start a fresh consume task so the game / demo plays
        # again from ply 1.
        from llove.demo.scenarios.base import DemoScenario

        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

        for v in self._views:
            if hasattr(v, "_rows"):
                v._rows.clear()
            if hasattr(v, "_alarms"):
                v._alarms.clear()
            if hasattr(v, "_entries"):
                v._entries.clear()
            if hasattr(v, "_values"):
                v._values.clear()
            if hasattr(v, "_count"):
                v._count = 0
            if hasattr(v, "_alarm_count"):
                v._alarm_count = 0
            if hasattr(v, "_beats"):
                v._beats = 0
            if hasattr(v, "_counts") and isinstance(v._counts, dict):
                for k in list(v._counts):
                    v._counts[k] = 0
            # Force a redraw of empty state.
            if hasattr(v, "update"):
                empty = getattr(v, "_initial", None)
                if empty is None:
                    empty = "(reset)"
                try:
                    v.update(empty)
                except Exception:  # nosec B110 — fail-closed: a broken redraw must not kill the app.
                    continue

        # Restart the source from scratch *only* for DemoScenarios — they
        # are stateless apart from their event generator, which is what we
        # want to re-roll. For arbitrary DataSource subclasses (JSONL tail,
        # custom test sources) we leave the existing instance alone and
        # do not start a new consume task: re-reading those is the caller's
        # responsibility, not Reset's.
        self._paused = False
        if hasattr(self, "_btn_pause"):
            self._btn_pause.label = t("ui.button.pause")
        if isinstance(self._source, DemoScenario):
            self._source = self._source.__class__()
            self._task = asyncio.create_task(self._consume())

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        # Keep the visible button label in sync so users see the new state.
        if hasattr(self, "_btn_pause"):
            self._btn_pause.label = t("ui.button.resume") if self._paused else t("ui.button.pause")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_quit_now(self) -> None:
        """Synchronous quit so it can be wired from Button.Pressed."""
        self.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Wire the top-row buttons to the same actions as the keybindings."""
        action_by_id = {
            "btn-pause": self.action_toggle_pause,
            "btn-reset": self.action_reset,
            "btn-help": self.action_show_help,
            "btn-quit": self.action_quit_now,
        }
        handler = action_by_id.get(event.button.id or "")
        if handler is not None:
            handler()


class HelpScreen(ModalScreen):
    """Modal overlay shown when the user clicks Help or presses 'h'."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > #help-box {
        width: 70;
        max-height: 80%;
        background: $boost;
        border: heavy $primary;
        padding: 1 2;
    }
    HelpScreen #help-close {
        margin-top: 1;
    }
    """

    BINDINGS = [  # noqa: RUF012 — Textual reads BINDINGS as a class-level list, not per-instance.
        ("escape", "dismiss", "Close"),
        ("h", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(t("ui.help.title"))
            yield Static(t("ui.help.body"))
            yield Button(t("ui.help.close"), id="help-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss()
