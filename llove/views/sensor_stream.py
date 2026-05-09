"""SensorStreamView — rolling list of sensor readings with sparkline."""
from __future__ import annotations

from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

_SPARK = "▁▂▃▄▅▆▇█"


class SensorStreamView(Static, View):
    """Compact rolling display of recent SensorEvents.

    Shows the last ``limit`` rows plus a sparkline of recent values.
    """

    name = "sensor_stream"
    title = "SensorEvent stream"

    DEFAULT_CSS = """
    SensorStreamView {
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }
    """

    def __init__(self, *, limit: int = 12) -> None:
        super().__init__("(no data yet)")
        self._limit = limit
        self._rows: deque[str] = deque(maxlen=limit)
        self._values: deque[float] = deque(maxlen=40)

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.SENSOR:
            return
        try:
            sid = event.payload.get("sensor_id", "?")
            val = float(event.payload.get("value", 0.0))
        except (TypeError, ValueError):
            return
        # Drop NaN / Inf — they cannot be normalised onto a sparkline.
        import math as _math
        if not _math.isfinite(val):
            return
        ts = event.ts.strftime("%H:%M:%S")
        self._rows.append(f"{ts}  {sid:18}  {val:7.2f}")
        self._values.append(val)
        self._refresh()

    def _refresh(self) -> None:
        spark = self._render_spark()
        body = "\n".join(self._rows) if self._rows else "(no data yet)"
        self.update(f"{body}\n\n{spark}")

    def _render_spark(self) -> str:
        if not self._values:
            return ""
        lo = min(self._values)
        hi = max(self._values)
        if hi - lo < 1e-9:
            return _SPARK[0] * len(self._values)
        bins = len(_SPARK) - 1
        return "".join(_SPARK[int((v - lo) / (hi - lo) * bins)] for v in self._values)
