"""TaskGraphView — DAG of research tasks with per-node status (Phase 0c).

Renders a topologically-layered ASCII / Rich-tag view of a research task
DAG (mirroring :class:`llmesh.core.task.TaskGraph`). Each node is drawn
with a status glyph so a watcher can see the run advance in real time.

Status is updated either explicitly via :meth:`update_status` or by
feeding ``TRACE_SPAN`` events whose payload carries ``node_id`` and
``status``.  The view is deliberately stateless w.r.t. the *content* of
each task — only the graph shape and status matter here. Detailed I/O
goes to :class:`TimelineView`.
"""

from __future__ import annotations

from collections import deque

from textual.widgets import Static

from llove.events import Event, EventKind
from llove.views.base import View

# Node status -> (icon, dim/colour tag for the trailing label).
# Plain glyphs (no exotic block chars) so the view degrades gracefully on
# terminals without Nerd Font / wide emoji support.
_STATUS_STYLE: dict[str, tuple[str, str]] = {
    "pending": ("[dim]o[/dim]", "dim"),
    "ready": ("[cyan]o[/cyan]", "cyan"),
    "running": ("[yellow]>[/yellow]", "yellow"),
    "done": ("[green]+[/green]", "green"),
    "failed": ("[red]x[/red]", "red"),
    "skipped": ("[dim]-[/dim]", "dim"),
}
_VALID_STATUSES = frozenset(_STATUS_STYLE)


class TaskGraphView(Static, View):
    """Layered DAG view. Nodes at depth ``d`` are indented by ``2*d`` spaces."""

    name = "task_graph"
    title = "Task graph"

    DEFAULT_CSS = """
    TaskGraphView {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__("(no tasks)")
        # nodes: list of dicts with id / target / depends_on (tuple|list)
        self._task_nodes: list[dict] = []
        self._status: dict[str, str] = {}
        self.border_title = "Task graph"
        self.border_subtitle = ""

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def set_graph(self, nodes: list[dict]) -> None:
        """Replace the rendered graph.

        Each node dict must carry ``id`` and may carry ``target``,
        ``kind`` and ``depends_on``. Unknown keys are ignored so callers
        can pass `dataclasses.asdict(TaskNode)` verbatim.
        """
        seen: set[str] = set()
        for n in nodes:
            nid = n.get("id")
            if not nid:
                raise ValueError("task node missing 'id'")
            if nid in seen:
                raise ValueError(f"duplicate task id: {nid!r}")
            seen.add(nid)
        self._task_nodes = list(nodes)
        self._status = {n["id"]: "pending" for n in self._task_nodes}
        self._redraw()

    def update_status(self, node_id: str, status: str) -> None:
        """Set ``status`` on the named node. Unknown nodes are ignored
        (the trace pipeline may emit spans before :meth:`set_graph`)."""
        if status not in _VALID_STATUSES:
            return
        if node_id not in self._status:
            return
        self._status[node_id] = status
        self._redraw()

    def feed(self, event: Event) -> None:
        if event.kind != EventKind.TRACE_SPAN:
            return
        payload = event.payload if isinstance(event.payload, dict) else {}
        node_id = payload.get("node_id")
        status = payload.get("status")
        if isinstance(node_id, str) and isinstance(status, str):
            self.update_status(node_id, status)

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------

    def _layers(self) -> list[list[str]]:
        """Return node ids grouped by topological depth.

        Cycles or unknown dependencies degrade gracefully: unresolved
        nodes are appended to a final ``"(cycle)"`` layer so the view
        stays informative even on a malformed graph.
        """
        by_id = {n["id"]: n for n in self._task_nodes}
        depth: dict[str, int] = {}
        remaining: deque[str] = deque(by_id)
        # bounded iteration so a cycle can't spin forever
        max_passes = len(by_id) * len(by_id) + 1
        passes = 0
        while remaining and passes < max_passes:
            nid = remaining.popleft()
            node = by_id[nid]
            deps = tuple(node.get("depends_on") or ())
            unresolved = [d for d in deps if d in by_id and d not in depth]
            if unresolved:
                remaining.append(nid)
            else:
                depth[nid] = max((depth[d] for d in deps if d in depth), default=-1) + 1
            passes += 1

        layers: list[list[str]] = []
        for nid in by_id:
            d = depth.get(nid)
            if d is None:
                continue
            while len(layers) <= d:
                layers.append([])
            layers[d].append(nid)
        # nodes left in `remaining` were part of a cycle; surface them.
        cycle = list(remaining)
        if cycle:
            layers.append(cycle)
        return layers

    def _render(self) -> None:
        if not self._task_nodes:
            self.update("(no tasks)")
            self.border_subtitle = ""
            return
        by_id = {n["id"]: n for n in self._task_nodes}
        lines: list[str] = []
        for layer in self._layers():
            for nid in layer:
                node = by_id[nid]
                status = self._status.get(nid, "pending")
                icon, colour = _STATUS_STYLE.get(status, ("?", "dim"))
                indent = "  " * self._depth_of(nid)
                target = str(node.get("target", "") or "")
                deps_seq = tuple(node.get("depends_on") or ())
                deps = ",".join(deps_seq) if deps_seq else "-"
                label = f"{nid} ({target})" if target else nid
                lines.append(
                    f"{indent}{icon} [{colour}]{label}[/{colour}] "
                    f"[dim]\\[{status}] deps={deps}[/dim]"
                )
        counts: dict[str, int] = {}
        for s in self._status.values():
            counts[s] = counts.get(s, 0) + 1
        self.border_subtitle = " · ".join(f"{k}:{v}" for k, v in counts.items() if v)
        self.update("\n".join(lines))

    def _depth_of(self, node_id: str) -> int:
        # Recompute on demand — graphs in the minimum-view phase are tiny.
        for d, layer in enumerate(self._layers()):
            if node_id in layer:
                return d
        return 0


__all__ = ["TaskGraphView"]
