"""Views — Textual widgets that consume Events and render them."""
from __future__ import annotations

from .audit_log import AuditLogView
from .base import View
from .narration import NarrationView
from .sensor_stream import SensorStreamView
from .spc_chart import SPCChartView

__all__ = [
    "AuditLogView",
    "NarrationView",
    "SPCChartView",
    "SensorStreamView",
    "View",
]
