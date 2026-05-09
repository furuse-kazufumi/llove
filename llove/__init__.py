"""llove — a cute, terminal-first Artifact for inspecting LLMesh data with llove.

Public API surface:

    from llove import Event, EventKind, DataSource, View

The package follows the LLMesh philosophy: fail-closed, optional dependencies as
extras, and keyboard-friendly by default.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .events import Event, EventKind
from .sources.base import DataSource
from .views.base import View

__all__ = [
    "Event",
    "EventKind",
    "DataSource",
    "View",
    "__version__",
]
