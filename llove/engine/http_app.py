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

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any, AsyncIterator

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "llove engine HTTP layer requires fastapi"
    ) from exc

from .brief_event_bus import BriefEvent, BriefEventBus, get_default_bus
from .info import engine_info


# F25 Phase h.1 — request schema mirrors llive.mcp.tools.tool_submit_brief.
# Kept here (not in a separate module) so the Phase-1 skeleton stays in one file.
# Defaults match docs/design/f25-phase-h-e2e.md 4.6.1 (draft v0.2, 2026-05-18).
class BriefSubmitRequest(BaseModel):
    goal: str = Field(..., min_length=1, description="Brief 目標. 空文字は 400")
    brief_id: str | None = None
    constraints: list[str] = Field(default_factory=list)
    source: str = "engine"
    priority: float = 0.5
    backend: str = ""
    tools: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    approval_required: bool = True


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
        """Phase 2 (2026-05-23): proxy ``llmesh.cli.deps_audit`` when present.

        Falls back to the Phase-1 deterministic stub when llmesh is not
        installed (feedback_independence_principle: llove engine ships
        standalone, llmesh is an optional peer via the ``[llmesh]`` extra).
        Wiring lets UIs render real supply-chain audit results without
        each frontend re-implementing the analyser.
        """
        try:
            from llmesh.cli.deps_audit import _to_json as _llmesh_to_json
            from llmesh.supply_chain import Origins, audit_installed
        except ModuleNotFoundError as exc:
            return {
                "metadata": {
                    "tool": "llove engine /api/v1/audit/deps (stub)",
                    "phase": "1-skeleton",
                    "reason": "llmesh not installed in this environment",
                    "missing_module": exc.name,
                },
                "summary": {
                    "total": 0,
                    "origin_breakdown": {},
                    "supply_risk": {"high": 0, "medium": 0, "low": 0, "unknown": 0},
                },
                "dependencies": [],
                "note": (
                    "Phase-1 stub. Install llmesh to enable real-data proxy "
                    "(pip install 'llmesh-llove[llmesh]')."
                ),
            }

        entries = audit_installed(origins=Origins())
        payload = json.loads(_llmesh_to_json(entries))
        payload["metadata"]["tool"] = (
            "llove engine /api/v1/audit/deps (proxy -> llmesh.cli.deps_audit)"
        )
        payload["metadata"]["phase"] = "2-proxy"
        return payload

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

    @app.post("/api/v1/brief/submit")
    def submit_brief(req: BriefSubmitRequest) -> dict[str, Any]:
        """F25 Phase h.1 — submit a Brief through llive.

        Behaviour (docs/design/f25-phase-h-e2e.md 4.6.1, draft v0.2):

        - 200 + BriefResult shape on success
        - 400 if ``goal`` is missing / empty (also handled by Pydantic validation)
        - 503 if llive is not installed (independence principle:
          feedback_independence_principle — llove engine ships standalone,
          llive is an optional runtime peer)
        - LLM-level / backend errors are surfaced inside ``result.status`` /
          ``result.error`` (200 with status="error"), not as HTTP errors.

        On completion, emits a ``brief_done`` event on the engine bus so
        any active ``/api/v1/annotations/stream`` subscriber sees the
        terminal state. Phase h.2.b will add ``annotation`` /
        ``stage_complete`` emits once llive exposes a hook into BriefRunner.
        """
        # Lazy-import to preserve llove independence (feedback_independence_principle).
        try:
            from llive.mcp.tools import tool_submit_brief
        except ModuleNotFoundError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "backend_unavailable",
                    "reason": "llive is not installed in this environment",
                    "hint": "pip install 'llmesh-llive[llm]' alongside llove",
                    "missing_module": exc.name,
                },
            ) from None

        payload = tool_submit_brief(
            goal=req.goal,
            brief_id=req.brief_id,
            constraints=list(req.constraints),
            source=req.source,
            priority=float(req.priority),
            backend=req.backend,
            tools=list(req.tools),
            success_criteria=list(req.success_criteria),
            approval_required=bool(req.approval_required),
        )

        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        get_default_bus().emit(
            "brief_done",
            data={"status": result.get("status"), "rationale": result.get("rationale")},
            brief_id=result.get("brief_id"),
        )
        return payload

    @app.get("/api/v1/annotations/stream")
    async def annotations_stream(
        request: Request,
        brief_id: str | None = None,
        target_layer: str | None = None,
        namespaces: str | None = None,
    ) -> StreamingResponse:
        """F25 Phase h.2 — SSE stream of brief events.

        Query params (docs/design/f25-phase-h-e2e.md 4.6.2):

        * ``brief_id`` — filter to a single brief; omit = all
        * ``target_layer`` — filter by ``target_layer`` (e.g. ``llove``).
          ``None`` (unset) target layer is treated as "any" and always passes.
        * ``namespaces`` — CSV of namespaces (applies to ``annotation`` events
          only; other event types always pass)

        Resume: ``Last-Event-ID`` header replays buffered events with
        ``seq > last_event_id`` (best-effort, bounded by the engine buffer).
        """
        last_event_id_raw = request.headers.get("last-event-id", "0")
        try:
            since_seq = int(last_event_id_raw)
        except ValueError:
            since_seq = 0

        ns_set: set[str] | None = (
            {n.strip() for n in namespaces.split(",") if n.strip()}
            if namespaces
            else None
        )

        def matches(ev: BriefEvent) -> bool:
            if brief_id is not None and ev.brief_id != brief_id:
                return False
            if (
                target_layer is not None
                and ev.target_layer is not None
                and ev.target_layer != target_layer
            ):
                return False
            if ev.event_type == "annotation" and ns_set is not None:
                if ev.namespace not in ns_set:
                    return False
            return True

        heartbeat_interval = float(os.environ.get("LLOVE_BRIEF_HEARTBEAT_S", "15"))
        # 0 / unset = no auto-close; positive = max wall-clock seconds before the
        # stream auto-terminates. Tests set a small value to avoid hangs; production
        # may set e.g. 600 to enforce a 10-minute idle timeout via the client.
        max_duration_raw = os.environ.get("LLOVE_BRIEF_SSE_MAX_DURATION_S", "0")
        try:
            max_duration = float(max_duration_raw)
        except ValueError:
            max_duration = 0.0

        return StreamingResponse(
            _sse_stream(
                get_default_bus(),
                matches,
                since_seq,
                heartbeat_interval,
                max_duration,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
            },
        )

    return app


def _format_sse(ev: BriefEvent) -> bytes:
    """Encode one BriefEvent as a single SSE message."""
    payload: dict[str, Any] = {"ts": ev.ts}
    if ev.brief_id is not None:
        payload["brief_id"] = ev.brief_id
    if ev.event_type == "annotation":
        payload["namespace"] = ev.namespace
        payload["target_layer"] = ev.target_layer
    payload.update(ev.data)
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return (
        f"event: {ev.event_type}\n"
        f"id: {ev.seq}\n"
        f"data: {body}\n\n"
    ).encode("utf-8")


async def _sse_stream(
    bus: BriefEventBus,
    matches,  # type: ignore[no-untyped-def]
    since_seq: int,
    heartbeat_interval: float,
    max_duration: float = 0.0,
) -> AsyncIterator[bytes]:
    """Yield SSE-formatted bytes — replay buffer, then live tail with heartbeat.

    ``max_duration > 0`` → terminate the stream after that many wall-clock
    seconds (client must reconnect with ``Last-Event-ID``). ``0`` = no limit.
    """
    loop = asyncio.get_event_loop()
    deadline = loop.time() + max_duration if max_duration > 0 else None

    # 1. Replay buffered events newer than since_seq (Last-Event-ID resume)
    for ev in bus.replay_since(since_seq):
        if matches(ev):
            yield _format_sse(ev)

    # 2. Subscribe for live events
    q: asyncio.Queue[BriefEvent] = asyncio.Queue(maxsize=1024)
    bus._register(q)  # noqa: SLF001 — engine-internal coupling
    try:
        while True:
            if deadline is not None and loop.time() >= deadline:
                return
            # Cap the await on the smaller of heartbeat_interval / remaining-deadline
            wait_for = heartbeat_interval
            if deadline is not None:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return
                wait_for = min(wait_for, remaining)
            try:
                ev = await asyncio.wait_for(q.get(), timeout=wait_for)
            except asyncio.TimeoutError:
                # Distinguish heartbeat (timeout == heartbeat_interval) from
                # deadline-cap (timeout was shorter than heartbeat_interval).
                if deadline is not None and loop.time() >= deadline:
                    return
                heartbeat = BriefEvent(
                    seq=0,
                    event_type="heartbeat",
                    data={},
                )
                yield _format_sse(heartbeat)
                continue
            if matches(ev):
                yield _format_sse(ev)
    finally:
        bus._unregister(q)  # noqa: SLF001
