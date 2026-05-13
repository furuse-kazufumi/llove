"""F25 (c) — RouteTraceViewer.

llive `route_trace` event を TUI viewer として可視化する。
`docs/llove_llive_bridge.md` 仕様 v1 に従う。

各 ``route_trace`` event は 1 リクエストの内部 subblock 実行 trace。
表示:

    Route Trace                                                container: adaptive_v1
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Request: 550e8400-...  latency: 2.12 ms  subblocks: 4
    Subblocks:
      [pre_norm]      ▓░░░░░░░░░░░░░░░  0.12 ms  ( 5.7%)
      [memory_read]   ▓▓▓▓▓▓▓▓▓░░░░░░░  1.40 ms  (66.0%)
      [ffn_swiglu]    ▓░░░░░░░░░░░░░░░  0.18 ms  ( 8.5%)
      [memory_write]  ▓▓▓░░░░░░░░░░░░░  0.42 ms  (19.8%)
    Memory access:
      read  semantic  hits=2  best=0.83
      write semantic  surprise=0.71

複数 trace を渡されたら最新 (一番新しい timestamp) を表示。`feed_events`
で event_id dedup 累積するのは BWTDashboard と同じ哲学。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from textual.widgets import Static

from llove.mcp.client import TimelineEvent
from llove.views.base import View

# ---------------------------------------------------------------------------
# Defensive parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubBlock:
    name: str
    type: str
    duration_ms: float
    note: str = ""


@dataclass(frozen=True)
class MemoryAccess:
    op: str  # "read" or "write"
    layer: str
    hits: tuple[tuple[str, float], ...] = ()  # ((entry_id, score), ...)
    entry_id: str = ""
    surprise: float = 0.0


@dataclass(frozen=True)
class RouteTrace:
    event_id: str
    request_id: str
    timestamp_utc: str
    container: str
    subblocks: tuple[SubBlock, ...] = ()
    memory_accesses: tuple[MemoryAccess, ...] = ()
    latency_ms: float = 0.0
    subblock_count: int = 0

    @classmethod
    def from_event(cls, ev: TimelineEvent) -> RouteTrace | None:
        if ev.event_type != "route_trace":
            return None
        md = ev.metadata or {}
        if not isinstance(md, dict):
            return None
        # subblocks / memory_accesses は list 前提、それ以外は無視
        raw_subs = md.get("subblocks")
        if not isinstance(raw_subs, list):
            raw_subs = []
        subs: list[SubBlock] = []
        for s in raw_subs:
            if not isinstance(s, dict):
                continue
            try:
                subs.append(
                    SubBlock(
                        name=str(s.get("name", "")),
                        type=str(s.get("type", "")),
                        duration_ms=float(s.get("duration_ms", 0.0)),
                        note=str(s.get("note", "")),
                    )
                )
            except (TypeError, ValueError):
                continue
        raw_mem = md.get("memory_accesses")
        if not isinstance(raw_mem, list):
            raw_mem = []
        mems: list[MemoryAccess] = []
        for m in raw_mem:
            if not isinstance(m, dict):
                continue
            hits_raw = m.get("hits") or []
            hits: list[tuple[str, float]] = []
            if isinstance(hits_raw, list):
                for h in hits_raw:
                    if not isinstance(h, dict):
                        continue
                    try:
                        hits.append(
                            (str(h.get("id", "")), float(h.get("score", 0.0)))
                        )
                    except (TypeError, ValueError):
                        continue
            try:
                surprise = float(m.get("surprise", 0.0))
            except (TypeError, ValueError):
                surprise = 0.0
            mems.append(
                MemoryAccess(
                    op=str(m.get("op", "")),
                    layer=str(m.get("layer", "")),
                    hits=tuple(hits),
                    entry_id=str(m.get("entry_id", "")),
                    surprise=surprise,
                )
            )
        metrics = md.get("metrics") or {}
        if not isinstance(metrics, dict):
            metrics = {}
        try:
            latency = float(metrics.get("latency_ms", 0.0))
        except (TypeError, ValueError):
            latency = 0.0
        try:
            subblock_count = int(metrics.get("subblock_count", len(subs)))
        except (TypeError, ValueError):
            subblock_count = len(subs)
        return cls(
            event_id=ev.event_id,
            request_id=str(ev.task_id),
            timestamp_utc=ev.timestamp_utc,
            container=str(md.get("container", "")),
            subblocks=tuple(subs),
            memory_accesses=tuple(mems),
            latency_ms=latency,
            subblock_count=subblock_count,
        )


# ---------------------------------------------------------------------------
# Pure rendering
# ---------------------------------------------------------------------------


def render_subblock_bars(
    subs: tuple[SubBlock, ...], *, bar_width: int = 16
) -> str:
    if not subs:
        return "  (no subblocks)"
    total = sum(s.duration_ms for s in subs)
    if total <= 0:
        total = 1.0
    name_width = max(8, min(20, max(len(s.name) for s in subs) + 2))
    lines: list[str] = []
    for s in subs:
        frac = s.duration_ms / total
        cells = max(0, min(bar_width, round(frac * bar_width)))
        bar = "▓" * cells + "░" * (bar_width - cells)
        lines.append(
            f"  [{s.name:<{name_width}}] {bar}  {s.duration_ms:>6.2f} ms  ({frac * 100:5.1f}%)"
        )
    return "\n".join(lines)


def render_memory_access(mems: tuple[MemoryAccess, ...]) -> str:
    if not mems:
        return "  (no memory accesses)"
    lines: list[str] = []
    for m in mems:
        if m.op == "read":
            if m.hits:
                best = max(m.hits, key=lambda h: h[1])
                lines.append(
                    f"  read  {m.layer:<10} hits={len(m.hits)}  best={best[1]:.3f}"
                )
            else:
                lines.append(f"  read  {m.layer:<10} hits=0")
        elif m.op == "write":
            lines.append(
                f"  write {m.layer:<10} surprise={m.surprise:.3f}"
            )
        else:
            lines.append(f"  {m.op}    {m.layer}")
    return "\n".join(lines)


def render_trace(trace: RouteTrace | None) -> str:
    if trace is None:
        return "(no route traces yet)"
    header = (
        f"Request: {trace.request_id}  latency: {trace.latency_ms:.2f} ms  "
        f"subblocks: {trace.subblock_count}"
    )
    container_line = (
        f"Container: {trace.container}" if trace.container else "Container: (unknown)"
    )
    parts = [
        container_line,
        header,
        "Subblocks:",
        render_subblock_bars(trace.subblocks),
        "Memory access:",
        render_memory_access(trace.memory_accesses),
    ]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class RouteTraceViewer(Static, View):
    """Latest-trace viewer with dedup history."""

    name = "route_trace_viewer"
    title = "Route Trace"

    DEFAULT_CSS = """
    RouteTraceViewer {
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, *, history: int = 100) -> None:
        super().__init__("(no route traces yet)")
        self._history: deque[RouteTrace] = deque(maxlen=max(2, int(history)))
        self._seen_ids: set[str] = set()
        self.border_title = "Route Trace"
        self.border_subtitle = ""

    def feed_events(self, events: list[TimelineEvent]) -> int:
        added = 0
        for ev in events:
            if ev.event_id and ev.event_id in self._seen_ids:
                continue
            trace = RouteTrace.from_event(ev)
            if trace is None:
                continue
            if trace.event_id:
                self._seen_ids.add(trace.event_id)
            self._history.append(trace)
            added += 1
        if added > 0:
            self._render()
        return added

    def clear(self) -> None:
        self._history.clear()
        self._seen_ids.clear()
        self._render()

    def trace_count(self) -> int:
        return len(self._history)

    def latest(self) -> RouteTrace | None:
        return self._history[-1] if self._history else None

    def _render(self) -> None:
        text = render_trace(self.latest())
        self.update(text)
        self.border_subtitle = f"traces: {len(self._history)}"


# ---------------------------------------------------------------------------
# Mock fixture
# ---------------------------------------------------------------------------


def make_mock_route_trace_events(n: int = 3) -> list[TimelineEvent]:
    """Synthetic ``route_trace`` events for offline demos.

    Generates ``n`` traces with realistic subblock breakdown (pre_norm /
    memory_read / ffn / memory_write) so the viewer can be exercised in CI.
    """
    events: list[TimelineEvent] = []
    for i in range(n):
        events.append(
            TimelineEvent(
                event_id=f"mock-trace-{i}",
                task_id=f"550e8400-e29b-41d4-a716-44665544{i:04d}",
                node_id="llive-mock",
                event_type="route_trace",
                timestamp_utc=f"2026-05-14T08:{30 + i:02d}:01Z",
                metadata={
                    "version": 1,
                    "container": "adaptive_reasoning_v1",
                    "subblocks": [
                        {"name": "pre_norm", "type": "pre_norm",
                         "duration_ms": 0.10 + 0.02 * i, "note": ""},
                        {"name": "memory_read", "type": "memory_read",
                         "duration_ms": 1.40 - 0.10 * i, "note": ""},
                        {"name": "ffn_swiglu", "type": "ffn_swiglu",
                         "duration_ms": 0.18 + 0.01 * i, "note": ""},
                        {"name": "memory_write", "type": "memory_write",
                         "duration_ms": 0.42, "note": ""},
                    ],
                    "memory_accesses": [
                        {
                            "op": "read",
                            "layer": "semantic",
                            "hits": [
                                {"id": f"hex-{i}-1", "score": 0.83 - 0.01 * i},
                                {"id": f"hex-{i}-2", "score": 0.71 - 0.01 * i},
                            ],
                        },
                        {
                            "op": "write",
                            "layer": "semantic",
                            "entry_id": f"hex-{i}-3",
                            "surprise": 0.71 + 0.02 * i,
                        },
                    ],
                    "metrics": {
                        "latency_ms": 2.10 - 0.05 * i,
                        "subblock_count": 4,
                    },
                },
            )
        )
    return events


__all__ = [
    "MemoryAccess",
    "RouteTrace",
    "RouteTraceViewer",
    "SubBlock",
    "make_mock_route_trace_events",
    "render_memory_access",
    "render_subblock_bars",
    "render_trace",
]


# Mypy compatibility: keep `field` referenced even if not used directly above
# (some patterns may want it later; importing without use triggers F401).
_ = field
