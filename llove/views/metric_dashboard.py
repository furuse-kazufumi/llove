"""MetricDashboardView — numeric metric dashboard (Phase 6).

A compact at-a-glance dashboard of named metrics: each metric carries
its latest value, an aggregate (count / min / max / mean), and a tiny
sparkline of the most recent samples. Designed for the explainability
flow where a reviewer wants to see *roughly* what changed, not a full
chart (that's the role of :class:`llove.views.spc_chart.SPCChartView`).

Reads ``Event(kind=SENSOR)`` with payload
``{"sensor_id": <metric_name>, "value": <number>}``, and additionally
accepts ``Event(kind=INFO)`` with payload
``{"metric": <name>, "value": <number>, "unit": <optional>}`` so a
demo can record domain-specific evaluation scores without abusing the
SENSOR kind.
"""

from __future__ import annotations

from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

# Sparkline blocks — low → high. Keep the set short so terminals
# without nerd-font / wide unicode still render readable bars.
_SPARK = "▁▂▃▄▅▆▇█"


def _sparkline(samples: list[float]) -> str:
    """Build a unicode sparkline of ``samples``.

    Returns an empty string for ``len(samples) < 2`` because a single
    point is not a trend worth visualising.
    """
    if len(samples) < 2:
        return ""
    lo = min(samples)
    hi = max(samples)
    span = hi - lo
    if span <= 0:
        # All samples equal — render as a flat mid-band line so the
        # dashboard still shows "metric is alive".
        return _SPARK[len(_SPARK) // 2] * len(samples)
    out: list[str] = []
    for s in samples:
        frac = (s - lo) / span
        idx = min(len(_SPARK) - 1, max(0, round(frac * (len(_SPARK) - 1))))
        out.append(_SPARK[idx])
    return "".join(out)


class MetricDashboardView(Static, View):
    """Multi-metric dashboard. Newest sample is the headline."""

    name = "metric_dashboard"
    title = "Metric dashboard"

    DEFAULT_CSS = """
    MetricDashboardView {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    def __init__(self, *, per_metric_history: int = 24) -> None:
        super().__init__("(no metrics)")
        self._history = max(2, int(per_metric_history))
        # metric_name -> samples deque (oldest..newest)
        self._samples: dict[str, deque[float]] = {}
        # metric_name -> unit string (or "")
        self._units: dict[str, str] = {}
        # number of total samples seen (incl evicted ones), per metric
        self._counts: dict[str, int] = {}
        self.border_title = "Metric dashboard"
        self.border_subtitle = ""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def record(self, name: str, value: float, *, unit: str = "") -> None:
        if not name:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        if v != v:  # NaN guard
            return
        buf = self._samples.setdefault(name, deque(maxlen=self._history))
        buf.append(v)
        self._counts[name] = self._counts.get(name, 0) + 1
        if unit:
            self._units[name] = unit
        self._redraw()

    def feed(self, event: Event) -> None:
        if event.kind == EventKind.SENSOR:
            payload = event.payload if isinstance(event.payload, dict) else {}
            sid = payload.get("sensor_id")
            val = payload.get("value")
            if isinstance(sid, str) and isinstance(val, (int, float)):
                self.record(sid, float(val))
            return
        if event.kind == EventKind.INFO:
            payload = event.payload if isinstance(event.payload, dict) else {}
            name = payload.get("metric")
            val = payload.get("value")
            unit = payload.get("unit", "")
            if isinstance(name, str) and isinstance(val, (int, float)):
                self.record(name, float(val), unit=unit if isinstance(unit, str) else "")

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        if not self._samples:
            self.update("(no metrics)")
            self.border_subtitle = ""
            return
        lines: list[str] = []
        # Sort metrics by name so the dashboard order is stable
        for name in sorted(self._samples):
            samples = list(self._samples[name])
            latest = samples[-1]
            mn = min(samples)
            mx = max(samples)
            mean = sum(samples) / len(samples)
            count = self._counts.get(name, len(samples))
            unit = self._units.get(name, "")
            unit_label = f" {unit}" if unit else ""
            spark = _sparkline(samples)
            lines.append(
                f"[bold]{name}[/bold]  "
                f"latest=[green]{latest:.3f}[/green]{unit_label}  "
                f"min={mn:.3f} max={mx:.3f} mean={mean:.3f}  "
                f"n={count}  {spark}"
            )
        self.border_subtitle = f"metrics:{len(self._samples)}"
        self.update("\n".join(lines))


__all__ = ["MetricDashboardView"]
