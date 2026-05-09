"""SPCChartView — show CUSUM-style alarms with a status banner."""
from __future__ import annotations

from datetime import datetime

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View


class SPCChartView(Static, View):
    """Status banner + recent alarm log."""

    name = "spc_chart"
    title = "SPC chart (CUSUM)"

    DEFAULT_CSS = """
    SPCChartView {
        height: 1fr;
        border: round $warning;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 6) -> None:
        super().__init__("● status: waiting for data")
        self._limit = limit
        self._alarms: list[str] = []
        self._last_value: float | None = None

    def feed(self, event: Event) -> None:
        if event.kind == EventKind.SENSOR:
            try:
                self._last_value = float(event.payload.get("value", 0.0))
            except (TypeError, ValueError):
                self._last_value = None
            self._refresh(alarmed=False)
            return
        if event.kind == EventKind.SPC_ALARM:
            sid = event.payload.get("sensor_id", "?")
            cusum = event.payload.get("cusum", "?")
            ts = event.ts.strftime("%H:%M:%S")
            self._alarms.insert(0, f"  {ts}  ALARM {sid}  cusum={cusum}")
            self._alarms = self._alarms[: self._limit]
            self._refresh(alarmed=True)

    def _refresh(self, *, alarmed: bool) -> None:
        if alarmed:
            head = "[bold red]●[/bold red] status: ALARM"
        elif self._last_value is None:
            head = "[dim]●[/dim] status: waiting for data"
        else:
            head = f"[bold green]●[/bold green] status: nominal  (value={self._last_value:.2f})"
        body = "\n".join(self._alarms) if self._alarms else "  (no alarms)"
        body = f"  Recent alarms:\n{body}"
        ts = datetime.now().strftime("%H:%M:%S")
        self.update(f"{head}    [dim]as of {ts}[/dim]\n\n{body}")
