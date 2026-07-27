"""llove engine — Core Multi-UI substrate.

Goal: expose llove's read-only data + observation capabilities through a
narrow, transport-agnostic protocol so any UI (Textual TUI, VS Code
extension, JetBrains plugin, Neovim plugin, Obsidian plugin, web
dashboard, external audit tools) can drive llove without depending on
the TUI rendering stack.

This is Phase 1 (skeleton): we deliberately limit ourselves to the
``sources`` / ``export`` / ``mcp`` / ``events`` layers identified in
``docs/audits/dogfooding-day0-gap.md`` as "TUI coupling 1-2" — i.e.
already engine-shaped. ``views`` / ``widgets`` / ``window`` / ``term``
stay in the TUI layer for Phase 1 and are not exposed here.

Strategy reference:
- ``C:/dev/projects/audit/STRATEGY_EAR_LOCAL_LLM_2026-05-17_PART5_ENGINE.md``
- ``docs/audits/dogfooding-day0-gap.md``

Public API (v0):
- :class:`EngineInfo`     — engine metadata
- :func:`engine_info`     — return current engine info
- :func:`make_http_app`   — build the FastAPI app (Pattern B/C from PART5)

The HTTP layer is optional; ``make_http_app`` is lazy-imported so the
TUI doesn't pull FastAPI into its critical path.
"""
from __future__ import annotations

from .info import EngineInfo, engine_info

__all__ = ["EngineInfo", "engine_info", "make_http_app"]


def make_http_app():  # type: ignore[no-untyped-def]
    """Build a FastAPI app exposing the engine.

    Imported lazily so the TUI path stays FastAPI-free. Returns a
    ``fastapi.FastAPI`` instance; raises ImportError with a friendly
    message if fastapi is not installed.
    """
    try:
        from .http_app import make_app
    except ImportError as exc:  # pragma: no cover - guidance only
        raise ImportError(
            "llove engine HTTP layer requires fastapi. "
            "Install with: pip install 'llmesh-llove[engine]'"
        ) from exc
    return make_app()
