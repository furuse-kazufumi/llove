"""F25 / M8.1 — Cognitive Mesh Panel stand-alone Textual demo.

llive cognitive_mesh の 3 種 event (proactive utterance / risk alert /
quarantine pending) を表示する skeleton viewer を **stand-alone Textual
App** として立ち上げる。LoveApp (本体) は touch せず、demo subprocess
として安全に動かせる経路。

実行:

    py -3.11 -m llove.demo.cog_mesh_demo

env で挙動制御:
- ``LLOVE_DEMO_AUTO_TICK=1`` — 起動時に mock event を 5 件流す
- ``LLOVE_DEMO_TICK_INTERVAL=1.0`` — 自動 tick 間隔秒

asciinema 録画候補。実 Timeline server (llmesh) との配線は Phase 6 で
``TimelinePollDriver(client=...)`` を本 demo に注入する形になる予定.
"""

from __future__ import annotations

import os

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Footer, Header

from llove.views.llive.cognitive_mesh_panel import (
    CognitiveMeshPanel,
    make_mock_cog_events,
)


class CogMeshDemoApp(App):
    """Stand-alone Textual app hosting just the CognitiveMeshPanel."""

    CSS = """
    Screen {
        background: $surface;
    }
    #cog-mesh-pane {
        padding: 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh (mock)"),
        ("c", "clear_panel", "Clear panel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.panel = CognitiveMeshPanel()
        self._auto_tick = os.environ.get("LLOVE_DEMO_AUTO_TICK", "") == "1"
        self._tick_interval = float(
            os.environ.get("LLOVE_DEMO_TICK_INTERVAL", "1.0")
        )
        self._tick_counter = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="cog-mesh-pane"):
            yield self.panel
        yield Footer()

    def on_mount(self) -> None:
        # 起動直後に 1 batch の mock events を流す (静止画にしない).
        self.panel.feed_events(make_mock_cog_events(3))
        if self._auto_tick:
            self.set_interval(self._tick_interval, self._tick_more)

    def _tick_more(self) -> None:
        """1 秒ごとに mock events を 1 件追加する (event_id を変えて
        idempotent dedup を超える)."""
        from llove.mcp.client import TimelineEvent

        self._tick_counter += 1
        ev = TimelineEvent(
            event_id=f"cog-tick-{self._tick_counter:04d}",
            task_id="",
            node_id="",
            event_type="cog_proactive_utterance",
            timestamp_utc=f"2026-05-19T10:00:{self._tick_counter % 60:02d}+09:00",
            metadata={
                "content": f"自動 tick #{self._tick_counter}",
                "mode": "timer",
                "gift_value": 0.7 + (self._tick_counter % 10) * 0.01,
            },
        )
        self.panel.feed_events([ev])

    def action_refresh(self) -> None:
        """手動で 3 件 mock events を追加 (押すたびに event_id が変わる)."""
        self._tick_counter += 1
        offset = self._tick_counter * 3

        # make_mock_cog_events をベースに event_id だけ書き換える
        # (TimelineEvent は frozen dataclass なので新規構築)
        from llove.mcp.client import TimelineEvent

        evs = []
        for i in range(3):
            base = make_mock_cog_events(1)[0]
            evs.append(
                TimelineEvent(
                    event_id=f"cog-manual-{offset + i:04d}",
                    task_id=base.task_id,
                    node_id=base.node_id,
                    event_type=base.event_type,
                    timestamp_utc=base.timestamp_utc,
                    metadata=dict(base.metadata),
                )
            )
        self.panel.feed_events(evs)

    def action_clear_panel(self) -> None:
        self.panel.clear()


def main() -> int:
    CogMeshDemoApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
