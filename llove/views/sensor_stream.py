"""SensorStreamView — rolling list of sensor readings with sparkline."""
from __future__ import annotations

import math
from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.i18n import t
from llove.views.base import View

_SPARK = "▁▂▃▄▅▆▇█"


class SensorStreamView(Static, View):
    """Compact rolling display of recent SensorEvents.

    Shows the last ``limit`` rows plus a sparkline of recent values.
    All user-facing strings come from the i18n catalog
    (``llove/i18n/locales/<lang>.toml``).
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
        super().__init__(t("ui.pane.sensor_stream.empty"))
        self._limit = limit
        self._rows: deque[str] = deque(maxlen=limit)
        self._values: deque[float] = deque(maxlen=40)
        self._count = 0
        self.border_title = t("ui.pane.sensor_stream.title")
        self.border_subtitle = t("ui.pane.sensor_stream.subtitle_init")

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.SENSOR:
            return
        try:
            sid = event.payload.get("sensor_id", "?")
            val = float(event.payload.get("value", 0.0))
        except (TypeError, ValueError):
            return
        # Drop NaN / Inf — they cannot be normalised onto a sparkline.
        if not math.isfinite(val):
            return
        ts = event.ts.strftime("%H:%M:%S")
        self._rows.append(f"{ts}  {sid:18}  {val:7.2f}")
        self._values.append(val)
        self._count += 1
        self.border_subtitle = t(
            "ui.pane.sensor_stream.subtitle_active",
            count=self._count,
            latest=f"{val:.2f}",
        )
        self._refresh()

    def _refresh(self) -> None:
        spark = self._render_spark()
        header = "[dim]" + t("ui.pane.sensor_stream.header") + "[/dim]"
        body = "\n".join(self._rows) if self._rows else t("ui.pane.sensor_stream.empty")
        spark_label = (
            "[dim]" + t("ui.pane.sensor_stream.sparkline_label") + "[/dim] " + spark
            if spark
            else ""
        )
        self.update(f"{header}\n{body}\n\n{spark_label}")

    def _render_spark(self) -> str:
        if not self._values:
            return ""
        lo = min(self._values)
        hi = max(self._values)
        if hi - lo < 1e-9:
            return _SPARK[0] * len(self._values)
        bins = len(_SPARK) - 1
        return "".join(_SPARK[int((v - lo) / (hi - lo) * bins)] for v in self._values)
