"""F25 (d) — MemoryLinkVizPanel.

llive `concept_update` event を TUI panel として可視化する。
`docs/llove_llive_bridge.md` 仕様 v1 に従う。

各 ``concept_update`` event は ConceptPage の upsert (新規 or 更新)。
同じ concept_id の event は ``timestamp_utc`` が新しい方が常に最新。
panel は concept_id 単位で **latest を保持** し、最新更新順に list 表示。

表示例:

    Memory Link                                  concepts: 3
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    ◆ Memory Consolidation                       (domain_concept)
        linked → surprise-gate, free-energy
        surprise: μ=0.42  n=6
        > Consolidation happens when surprise exceeds the gate threshold...

    ◆ Surprise Gate                              (mechanism)
        linked → memory-consolidation
        surprise: μ=0.71  n=3
        > ...
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.widgets import Static

from llove.mcp.client import TimelineEvent
from llove.views.base import View

# ---------------------------------------------------------------------------
# Defensive parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SurpriseStats:
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0  # second moment (variance accumulator)


@dataclass(frozen=True)
class ConceptUpdate:
    event_id: str
    timestamp_utc: str
    concept_id: str
    title: str
    page_type: str
    linked_entry_ids: tuple[str, ...]
    linked_concept_ids: tuple[str, ...]
    surprise_stats: SurpriseStats
    summary: str

    @classmethod
    def from_event(cls, ev: TimelineEvent) -> ConceptUpdate | None:
        if ev.event_type != "concept_update":
            return None
        md = ev.metadata or {}
        if not isinstance(md, dict):
            return None
        concept_id = str(md.get("concept_id", "")).strip()
        if not concept_id:
            return None
        linked_entry_ids = md.get("linked_entry_ids") or []
        if not isinstance(linked_entry_ids, list):
            linked_entry_ids = []
        linked_concept_ids = md.get("linked_concept_ids") or []
        if not isinstance(linked_concept_ids, list):
            linked_concept_ids = []
        raw_stats = md.get("surprise_stats") or {}
        if not isinstance(raw_stats, dict):
            raw_stats = {}
        try:
            stats = SurpriseStats(
                n=int(raw_stats.get("n", 0)),
                mean=float(raw_stats.get("mean", 0.0)),
                m2=float(raw_stats.get("m2", 0.0)),
            )
        except (TypeError, ValueError):
            stats = SurpriseStats()
        return cls(
            event_id=ev.event_id,
            timestamp_utc=ev.timestamp_utc,
            concept_id=concept_id,
            title=str(md.get("title", concept_id)),
            page_type=str(md.get("page_type", "")),
            linked_entry_ids=tuple(str(x) for x in linked_entry_ids),
            linked_concept_ids=tuple(str(x) for x in linked_concept_ids),
            surprise_stats=stats,
            summary=str(md.get("summary", "")),
        )


# ---------------------------------------------------------------------------
# Pure rendering
# ---------------------------------------------------------------------------


_SUMMARY_MAX = 120  # 1 行短縮上限。spec の 1500 chars を card 用に圧縮


def render_concept_card(concept: ConceptUpdate) -> str:
    """1 つの concept を card 形式に整形.

    最新更新順 list 表示で 1 ブロックにまとまるように 4〜5 行で書く。
    """
    page_type = f"({concept.page_type})" if concept.page_type else ""
    header = f"◆ {concept.title}".ljust(40) + page_type
    linked = (
        "    linked → " + ", ".join(concept.linked_concept_ids)
        if concept.linked_concept_ids
        else "    linked → (none)"
    )
    stats = concept.surprise_stats
    surprise = (
        f"    surprise: μ={stats.mean:.3f}  n={stats.n}"
        if stats.n > 0
        else "    surprise: (no samples)"
    )
    summary = concept.summary.strip().replace("\n", " ")
    if len(summary) > _SUMMARY_MAX:
        summary = summary[:_SUMMARY_MAX].rstrip() + "..."
    summary_line = f"    > {summary}" if summary else "    > (no summary)"
    return "\n".join([header, linked, surprise, summary_line])


def render_concept_list(
    concepts: list[ConceptUpdate], *, max_items: int = 10
) -> str:
    """Render a list of concepts (latest first) up to ``max_items``."""
    if not concepts:
        return "(no concept updates yet)"
    visible = concepts[:max_items]
    blocks = [render_concept_card(c) for c in visible]
    extras = ""
    if len(concepts) > max_items:
        extras = f"\n\n... and {len(concepts) - max_items} more concept(s)"
    return ("\n\n".join(blocks)) + extras


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------


class MemoryLinkVizPanel(Static, View):
    """Concept page panel. concept_id 単位で最新を保持し、最近の更新順に表示."""

    name = "memory_link_panel"
    title = "Memory Link"

    DEFAULT_CSS = """
    MemoryLinkVizPanel {
        height: 1fr;
        border: round $warning;
        padding: 0 1;
    }
    """

    def __init__(self, *, max_items: int = 10) -> None:
        super().__init__("(no concept updates yet)")
        self._max_items = max(1, int(max_items))
        self._by_concept: dict[str, ConceptUpdate] = {}
        self._order: list[str] = []  # concept_id, 最新更新順 (先頭=最新)
        self._seen_ids: set[str] = set()
        self.border_title = "Memory Link"
        self.border_subtitle = ""

    # ------------------------------------------------------------------

    def feed_events(self, events: list[TimelineEvent]) -> int:
        """Ingest concept_update events. Returns count of *concept_id*
        changes (新規 + 既存の更新)。event_id で dedup."""
        changed = 0
        for ev in events:
            if ev.event_id and ev.event_id in self._seen_ids:
                continue
            concept = ConceptUpdate.from_event(ev)
            if concept is None:
                continue
            if concept.event_id:
                self._seen_ids.add(concept.event_id)
            existing = self._by_concept.get(concept.concept_id)
            # 既存より古い update なら無視 (タイムスタンプ昇順保証)
            if existing is not None and concept.timestamp_utc < existing.timestamp_utc:
                continue
            self._by_concept[concept.concept_id] = concept
            # _order: 最新更新を先頭に置き直す
            if concept.concept_id in self._order:
                self._order.remove(concept.concept_id)
            self._order.insert(0, concept.concept_id)
            changed += 1
        if changed > 0:
            self._render()
        return changed

    def clear(self) -> None:
        self._by_concept.clear()
        self._order.clear()
        self._seen_ids.clear()
        self._render()

    def concept_count(self) -> int:
        return len(self._by_concept)

    def latest(self) -> ConceptUpdate | None:
        if not self._order:
            return None
        return self._by_concept[self._order[0]]

    def concepts_in_order(self) -> list[ConceptUpdate]:
        return [self._by_concept[cid] for cid in self._order]

    # ------------------------------------------------------------------

    def _render(self) -> None:
        text = render_concept_list(
            self.concepts_in_order(), max_items=self._max_items
        )
        self.update(text)
        self.border_subtitle = f"concepts: {len(self._by_concept)}"


# ---------------------------------------------------------------------------
# Mock fixture
# ---------------------------------------------------------------------------


def make_mock_concept_events(n: int = 4) -> list[TimelineEvent]:
    """Synthetic ``concept_update`` events for offline demos.

    Generates ``n`` distinct concepts with cross-links so the panel shows
    realistic graph topology in `llove demo` / CI.
    """
    concept_titles = [
        ("memory-consolidation", "Memory Consolidation", "domain_concept"),
        ("surprise-gate", "Surprise Gate", "mechanism"),
        ("free-energy", "Free Energy Principle", "theory"),
        ("predictive-coding", "Predictive Coding", "theory"),
        ("hippocampal-replay", "Hippocampal Replay", "mechanism"),
        ("schema-update", "Schema Update", "mechanism"),
    ]
    events: list[TimelineEvent] = []
    for i in range(min(n, len(concept_titles))):
        cid, title, ptype = concept_titles[i]
        # 各 concept は前後の concept にリンク (循環でない)
        linked = []
        if i > 0:
            linked.append(concept_titles[i - 1][0])
        if i + 1 < min(n, len(concept_titles)):
            linked.append(concept_titles[i + 1][0])
        events.append(
            TimelineEvent(
                event_id=f"mock-concept-{i}",
                task_id=f"concept-task-{i:04d}",
                node_id="llive-mock",
                event_type="concept_update",
                timestamp_utc=f"2026-05-14T08:{30 + i:02d}:02Z",
                metadata={
                    "version": 1,
                    "concept_id": cid,
                    "title": title,
                    "page_type": ptype,
                    "linked_entry_ids": [f"hex-{i}-a", f"hex-{i}-b"],
                    "linked_concept_ids": linked,
                    "surprise_stats": {
                        "n": 6 + i,
                        "mean": 0.42 + 0.05 * i,
                        "m2": 0.05 + 0.01 * i,
                    },
                    "summary": (
                        f"{title} の役割: フェーズ {i} における学習段階での"
                        " 概念連結を担う、長期記憶への昇格判定の主要素。"
                    ),
                },
            )
        )
    return events


__all__ = [
    "ConceptUpdate",
    "MemoryLinkVizPanel",
    "SurpriseStats",
    "make_mock_concept_events",
    "render_concept_card",
    "render_concept_list",
]
