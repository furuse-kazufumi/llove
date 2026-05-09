"""RAG stores scenario — compare Numpy / SQLite / LSH ANN backends."""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind
from llove.i18n import t

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
    i18n_key = "rag"
    default_pause = 0.5

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.rag.intro", title_key="scenario.rag.intro_title")
        yield narrate(t("scenario.rag.query", q=_QUERY), title=t("scenario.rag.query_title"))

        for store in _STORES:
            yield narrate(
                t("scenario.rag.running", name=store["name"], scale=store["scale"], note=store["note"]),
                title=str(store["name"]),
            )
            for i in range(3):
                yield Event(
                    kind=EventKind.RAG_HIT,
                    source_id=str(store["name"]),
                    payload={
                        "score": round(0.92 - i * 0.04, 2),
                        "text": f"({store['name']}#{i + 1}) replay defenses for industrial protocols ...",
                        "doc_id": f"doc-{str(store['name'])[0].lower()}-{i + 1}",
                    },
                )
            yield Event(
                kind=EventKind.AUDIT,
                source_id=str(store["name"]),
                payload={
                    "event": "rag.search",
                    "store": store["name"],
                    "latency_ms": store["latency_ms"],
                    "recall_at_10": store["recall_at_10"],
                    "scale": store["scale"],
                },
            )

        yield narrate_key("scenario.rag.takeaway", title_key="scenario.rag.takeaway_title")
