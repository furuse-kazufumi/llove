"""FastAPI app exposing the llove engine (Pattern B / C from PART 5).

This is a Phase-1 skeleton: only introspection + health + audit hooks.
LSP and Webview protocols (Pattern B specifically for VS Code) land in
Phase 2 once the read-only surface is verified.

Endpoints (v0):
- ``GET  /healthz``                     — liveness probe (no auth)
- ``GET  /api/v1/engine``                — engine info (no auth)
- ``GET  /api/v1/audit/deps``            — placeholder — real impl
                                            mirrors ``llmesh deps audit``
                                            spec (PART 6)
- ``GET  /api/v1/audit/offline-check``   — placeholder — confirms no
                                            outbound network calls
                                            during startup

Security stance:
- localhost-only by default (caller binds host explicitly)
- No authentication on localhost endpoints (Pattern B: same-machine
  extension talks to subprocess)
- Pattern C deployment (multi-user, network-accessible) MUST add
  Bearer / mTLS — out of scope for Phase 1
"""
from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "llove engine HTTP layer requires fastapi"
    ) from exc

from .info import engine_info


def make_app() -> FastAPI:
    """Build and return the engine FastAPI app."""
    app = FastAPI(
        title="llove engine",
        version=engine_info().version or "dev",
        description=(
            "Read-only engine surface for llove. "
            "Drives Textual TUI, VS Code extension, JetBrains plugin, "
            "Neovim plugin and audit tooling through one protocol."
        ),
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/engine")
    def get_engine_info() -> dict[str, Any]:
        return engine_info().to_dict()

    @app.get("/api/v1/audit/deps")
    def audit_deps() -> dict[str, Any]:
        """Placeholder: full impl delegates to llmesh.cli.deps_audit.

        Phase 1 returns a deterministic stub so UIs can wire the call
        and exercise the round-trip. Phase 2 will import the real
        analyser when llmesh is installed alongside llove.
        """
        return {
            "metadata": {
                "tool": "llove engine /api/v1/audit/deps (stub)",
                "phase": "1-skeleton",
            },
            "summary": {
                "total": 0,
                "origin_breakdown": {},
                "supply_risk": {"high": 0, "medium": 0, "low": 0, "unknown": 0},
            },
            "dependencies": [],
            "note": (
                "Phase-1 stub. Run `python -m llmesh.cli.deps_audit --json` "
                "for real data; Phase-2 will proxy it through this endpoint."
            ),
        }

    @app.get("/api/v1/audit/offline-check")
    def offline_check() -> dict[str, Any]:
        """Confirm the engine made no outbound network calls during boot.

        Phase 1 returns a deterministic "no_external_calls_detected" so
        UIs can render the offline status badge. A future runtime
        hook will instrument actual outbound traffic.
        """
        return {
            "outbound_calls_detected": False,
            "phase": "1-skeleton",
            "note": (
                "Static stub. Phase 2 will hook httpx / urllib / aiohttp "
                "trace events at startup."
            ),
        }

    return app
