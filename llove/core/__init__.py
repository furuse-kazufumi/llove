"""llove core — UI-framework-independent layer.

Holds the pieces that neither Textual nor Qt should own: the event/metrics
data shapes, view-models (pure state that ``feed``s rows and exposes series),
and time-axis-agnostic drivers. Both the Textual front (``llove/views``) and the
Qt front (``llove/qt``) subscribe to the same view-models.

This package MUST NOT import any UI framework (no ``textual``, no ``PySide6``)
so the core wheel stays light and either front can be installed independently.
See ``docs`` design: llove_qt_gui_architecture_2026_05_25 §5.2.
"""

from __future__ import annotations
