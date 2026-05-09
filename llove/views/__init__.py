"""Views — Textual widgets that consume Events and render them."""
from __future__ import annotations

from .base import View
from .audit_log import AuditLogView
from .sensor_stream import SensorStreamView
from .spc_chart import SPCChartView

__all__ = ["View", "AuditLogView", "SensorStreamView", "SPCChartView"]
