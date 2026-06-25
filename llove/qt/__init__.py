"""llove Qt front (Stage 1) — PySide6 + pyqtgraph live panels.

A second, GUI front beside the Textual TUI (which stays the default, lightweight
front). Everything here is gated behind the ``gui`` extra so the core wheel is
unaffected::

    pip install 'llmesh-llove[gui]'

Stage 1 ships a single live panel — ``FitnessTrajectoryPanel`` — that tails an
evolution run's ``metrics.jsonl`` and plots best/mean/median score per
generation. Later stages add the QtAds OS-like shell and the rest of the panel
catalogue (design: llove_qt_gui_architecture_2026_05_25 §6).

Importing this subpackage never imports PySide6/pyqtgraph; the submodules do.
Call :func:`ensure_gui` for a friendly error when the extra is missing.
"""

from __future__ import annotations


def ensure_gui() -> None:
    """Raise a helpful ImportError if the ``gui`` extra is not installed."""
    missing: list[str] = []
    for mod in ("PySide6", "pyqtgraph"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        raise ImportError(
            "llove Qt front needs the 'gui' extra "
            f"(missing: {', '.join(missing)}). Install with: "
            "pip install 'llmesh-llove[gui]'"
        )


__all__ = ["ensure_gui"]
