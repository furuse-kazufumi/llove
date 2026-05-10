"""Views — Textual widgets that consume Events and render them."""

from __future__ import annotations

from .audit_log import AuditLogView
from .base import View
from .markdown_view import MarkdownView
from .narration import NarrationView
from .sensor_stream import SensorStreamView
from .spc_chart import SPCChartView

__all__ = [
    "AuditLogView",
    "MarkdownView",
    "NarrationView",
    "SPCChartView",
    "SensorStreamView",
    "View",
]
