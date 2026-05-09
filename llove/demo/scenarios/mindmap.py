"""Mindmap scenario — LLM expands a query into a knowledge tree, step by step.

Each node is emitted as a TRACE_SPAN. When the tree breadth crosses a watch
threshold, an SPC_ALARM fires (proxy for "this query is too broad — narrow
or split it"). The final tree is rendered as an ASCII outline so the
narration pane shows the whole map; the same payload also carries the raw
adjacency dict so an external viewer can render it differently.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind

# Adjacency list — order is the order we expand. Keys not appearing as values
# are roots; leaves have no entry.
_NODES: dict[str, list[str]] = {
    "LLMesh": [
        "PromptFirewall",
        "SPC",
        "RAG",
        "Backends",
        "AuditTrail",
    ],
    "PromptFirewall": [
        "L0 injection",
        "L1 secret",
        "L1.5 PII",
        "L2 logic",
    ],
    "SPC": [
        "CUSUMChart",
        "Hotelling T²",
        "XbarRChart",
    ],
    "RAG": [
        "NumpyVectorStore",
        "SqliteVectorStore",
        "LSHVectorStore",
    ],
    "Backends": [
        "OllamaBackend",
        "OpenAIBackend",
        "AnthropicBackend",
    ],
    # AuditTrail is a leaf for this scenario.
}


_BREADTH_ALARM_THRESHOLD = 12  # nodes — proxy for "query is too broad"


def _render_outline(adj: dict[str, list[str]], root: str) -> str:
    """Render the adjacency dict as a Unicode-tree outline rooted at ``root``."""
    lines: list[str] = [root]

    def walk(node: str, prefix: str) -> None:
        children = adj.get(node, [])
        for i, ch in enumerate(children):
            last = i == len(children) - 1
            branch = "└── " if last else "├── "
            lines.append(prefix + branch + ch)
            walk(ch, prefix + ("    " if last else "│   "))

    walk(root, "")
    return "\n".join(lines)


class MindmapScenario(DemoScenario):
    """Live mindmap construction in response to an open-ended LLM query."""

    name = "mindmap"
    i18n_key = "mindmap"
    default_pause = 0.5

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.mindmap.intro", title_key="scenario.mindmap.intro_title")

        # Open with the seed query and the root node — like an LLM "thinking".
        yield narrate_key("scenario.mindmap.query", title_key="scenario.mindmap.query_title")
        yield Event(
            kind=EventKind.TRACE_SPAN,
            source_id="mindmap",
            payload={
                "span": "mindmap.expand",
                "node": "LLMesh",
                "depth": 0,
                "parent": None,
                "kind": "root",
            },
        )

        # BFS expansion — each pop is a TRACE_SPAN, the breadth count drives SPC.
        breadth = 1  # the root itself
        alarm_fired = False
        queue: list[tuple[str, int, str | None]] = [("LLMesh", 0, None)]
        while queue:
            node, depth, _parent = queue.pop(0)
            for child in _NODES.get(node, []):
                breadth += 1
                yield Event(
                    kind=EventKind.TRACE_SPAN,
                    source_id="mindmap",
                    payload={
                        "span": "mindmap.expand",
                        "node": child,
                        "depth": depth + 1,
                        "parent": node,
                        "kind": "branch" if child in _NODES else "leaf",
                    },
                )
                queue.append((child, depth + 1, node))

                if not alarm_fired and breadth >= _BREADTH_ALARM_THRESHOLD:
                    alarm_fired = True
                    yield Event(
                        kind=EventKind.SPC_ALARM,
                        source_id="mindmap",
                        payload={
                            "sensor_id": "tree_breadth",
                            "value": breadth,
                            "threshold": _BREADTH_ALARM_THRESHOLD,
                            "cusum": breadth - _BREADTH_ALARM_THRESHOLD,
                            "rule": "breadth_explosion",
                        },
                    )
                    yield narrate_key(
                        "scenario.mindmap.alarm",
                        title_key="scenario.mindmap.alarm_title",
                        breadth=breadth,
                        threshold=_BREADTH_ALARM_THRESHOLD,
                    )

        # Final summary — full tree as ASCII outline.
        outline = _render_outline(_NODES, "LLMesh")
        yield narrate(
            f"```\n{outline}\n```\n**{breadth} nodes total** across "
            f"{len([n for n in _NODES if n != 'LLMesh']) + 1} branches.",
            title="Mindmap (final)",
        )

        yield Event(
            kind=EventKind.AUDIT,
            source_id="mindmap",
            payload={
                "event": "mindmap.completed",
                "root": "LLMesh",
                "node_count": breadth,
                "adjacency": _NODES,
                "outline_ascii": outline,
            },
        )

        yield narrate_key(
            "scenario.mindmap.takeaway",
            title_key="scenario.mindmap.takeaway_title",
            breadth=breadth,
        )
