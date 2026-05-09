"""Data sources for llove."""
from __future__ import annotations

from .base import DataSource
from .jsonl import JSONLSource
from .mock import MockSource

__all__ = ["DataSource", "JSONLSource", "MockSource"]
