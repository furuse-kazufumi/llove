"""RAG stores scenario — compare Numpy / SQLite / LSH ANN backends.

Synthetic only: we don't actually run a vector search. The numbers below come
from the LLMesh PERFORMANCE.md doc and are presented to teach which store to
pick at which scale.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind

_INTRO = (
    "**llmesh.rag** ships 3 stores. Same `Retriever` ABC, different scaling. "
    "We replay the same query against each one."
)

_STORES = [
    {
        "name": "NumpyVectorStore",
        "scale": "≤ 10⁵ docs",
        "latency_ms": 18,
        "recall_at_10": 1.00,
        "note": "exact cosine, full O(n) scan, .npz atomic save",
    },
    {
        "name": "SqliteVectorStore",
        "scale": "≤ 10⁶ docs",
        "latency_ms": 64,
        "recall_at_10": 1.00,
        "note": "exact cosine, sqlite3 WAL, UPSERT, native backup",
    },
    {
        "name": "LSHVectorStore",
        "scale": "≥ 10⁶ docs",
        "latency_ms": 9,
        "recall_at_10": 0.93,
        "note": "LSH ANN (multi-probe), 0.93 recall@10 vs Numpy ground truth",
    },
]

_QUERY = "Modbus replay attack mitigation in DNP3"


class RAGStoresScenario(DemoScenario):
    name = "rag"
    title = "RAG — three vector stores compared"
    description = (
        "Replay one query across NumpyVectorStore / SqliteVectorStore / LSHVectorStore "
        "and compare latency vs recall."
    )
    default_pause = 0.5

    async def events(self) -> AsyncIterator[Event]:
        yield narrate(_INTRO, title="Scenario: RAG stores")
        yield narrate(f"query: `{_QUERY}`", title="Query")

        for store in _STORES:
            yield narrate(
                f"running **{store['name']}** ({store['scale']}) — {store['note']}",
                title=store["name"],
            )
            for i in range(3):
                yield Event(
                    kind=EventKind.RAG_HIT,
                    source_id=store["name"],
                    payload={
                        "score": round(0.92 - i * 0.04, 2),
                        "text": f"({store['name']}#{i + 1}) replay defenses for industrial protocols ...",
                        "doc_id": f"doc-{store['name'][0].lower()}-{i + 1}",
                    },
                )
            yield Event(
                kind=EventKind.AUDIT,
                source_id=store["name"],
                payload={
                    "event": "rag.search",
                    "store": store["name"],
                    "latency_ms": store["latency_ms"],
                    "recall_at_10": store["recall_at_10"],
                    "scale": store["scale"],
                },
            )

        yield narrate(
            "**Pick by scale, not popularity.** Numpy for prototypes, SQLite for typical "
            "production (≤ 10⁶), LSH ANN when you blow past a million documents.",
            title="Take-away",
        )
