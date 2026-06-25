"""Time-axis-agnostic drivers: the caller controls cadence, the driver polls."""

from __future__ import annotations

from llove.core.drivers.metrics_tail import MetricsTailReader

__all__ = ["MetricsTailReader"]
