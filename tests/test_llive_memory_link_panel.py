"""F25 (d) — MemoryLinkVizPanel の単体テスト.

BWTDashboard / RouteTraceViewer と同じ哲学 (pure render + widget API)。
特殊な振る舞いとして「同じ concept_id の新しい update が古いものを上書き」
「concept_id 順は最新更新順」をテストでカバー。
"""

from __future__ import annotations

from llove.mcp.client import TimelineEvent
from llove.views.llive.memory_link_panel import (
    ConceptUpdate,
    MemoryLinkVizPanel,
    SurpriseStats,
    make_mock_concept_events,
    render_concept_card,
    render_concept_list,
)

# ---------------------------------------------------------------------------
# ConceptUpdate.from_event — 防御的パース
# ---------------------------------------------------------------------------


def test_from_event_returns_concept_for_valid_payload() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="llive-1",
        event_type="concept_update",
        timestamp_utc="2026-05-14T08:30:00Z",
        metadata={
            "concept_id": "memory-consolidation",
            "title": "Memory Consolidation",
            "page_type": "domain_concept",
            "linked_entry_ids": ["h1", "h2"],
            "linked_concept_ids": ["surprise-gate"],
            "surprise_stats": {"n": 6, "mean": 0.42, "m2": 0.05},
            "summary": "When surprise exceeds threshold.",
        },
    )
    c = ConceptUpdate.from_event(ev)
    assert c is not None
    assert c.concept_id == "memory-consolidation"
    assert c.title == "Memory Consolidation"
    assert c.page_type == "domain_concept"
    assert c.linked_entry_ids == ("h1", "h2")
    assert c.linked_concept_ids == ("surprise-gate",)
    assert c.surprise_stats.n == 6
    assert c.surprise_stats.mean == 0.42
    assert "surprise" in c.summary.lower()


def test_from_event_returns_none_for_wrong_event_type() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="n",
        event_type="bwt_summary",
        timestamp_utc="x",
        metadata={"concept_id": "c"},
    )
    assert ConceptUpdate.from_event(ev) is None


def test_from_event_returns_none_for_missing_concept_id() -> None:
    """concept_id が無い / 空文字なら拒否."""
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="x",
        metadata={"title": "no id"},
    )
    assert ConceptUpdate.from_event(ev) is None


def test_from_event_defaults_title_to_concept_id() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="x",
        metadata={"concept_id": "raw-id"},
    )
    c = ConceptUpdate.from_event(ev)
    assert c is not None
    assert c.title == "raw-id"


def test_from_event_handles_invalid_links_list() -> None:
    """linked_*_ids が list でなければ空タプルに."""
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="x",
        metadata={
            "concept_id": "c",
            "linked_entry_ids": "not a list",
            "linked_concept_ids": 123,
        },
    )
    c = ConceptUpdate.from_event(ev)
    assert c is not None
    assert c.linked_entry_ids == ()
    assert c.linked_concept_ids == ()


def test_from_event_handles_invalid_surprise_stats() -> None:
    ev = TimelineEvent(
        event_id="e1",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="x",
        metadata={
            "concept_id": "c",
            "surprise_stats": {"n": "not int", "mean": 0.5},
        },
    )
    c = ConceptUpdate.from_event(ev)
    assert c is not None
    # n が型変換失敗 → SurpriseStats() デフォルトに倒れる
    assert c.surprise_stats == SurpriseStats()


# ---------------------------------------------------------------------------
# render_concept_card
# ---------------------------------------------------------------------------


def test_concept_card_includes_title_and_page_type() -> None:
    c = ConceptUpdate(
        event_id="e",
        timestamp_utc="x",
        concept_id="c",
        title="My Concept",
        page_type="mechanism",
        linked_entry_ids=(),
        linked_concept_ids=("other",),
        surprise_stats=SurpriseStats(n=3, mean=0.5),
        summary="Brief explanation.",
    )
    out = render_concept_card(c)
    assert "My Concept" in out
    assert "(mechanism)" in out
    assert "other" in out
    assert "μ=0.500" in out
    assert "n=3" in out
    assert "Brief explanation" in out


def test_concept_card_truncates_long_summary() -> None:
    c = ConceptUpdate(
        event_id="e",
        timestamp_utc="x",
        concept_id="c",
        title="t",
        page_type="",
        linked_entry_ids=(),
        linked_concept_ids=(),
        surprise_stats=SurpriseStats(),
        summary="x" * 500,
    )
    out = render_concept_card(c)
    assert "..." in out


def test_concept_card_handles_no_links_and_no_samples() -> None:
    c = ConceptUpdate(
        event_id="e",
        timestamp_utc="x",
        concept_id="c",
        title="lonely",
        page_type="",
        linked_entry_ids=(),
        linked_concept_ids=(),
        surprise_stats=SurpriseStats(n=0),
        summary="",
    )
    out = render_concept_card(c)
    assert "linked → (none)" in out
    assert "(no samples)" in out
    assert "(no summary)" in out


# ---------------------------------------------------------------------------
# render_concept_list
# ---------------------------------------------------------------------------


def test_concept_list_placeholder_for_empty() -> None:
    out = render_concept_list([])
    assert "no concept updates" in out


def test_concept_list_renders_each_concept() -> None:
    concepts = [
        ConceptUpdate.from_event(ev)
        for ev in make_mock_concept_events(n=3)
    ]
    out = render_concept_list([c for c in concepts if c is not None])
    assert "Memory Consolidation" in out
    assert "Surprise Gate" in out
    assert "Free Energy" in out


def test_concept_list_shows_overflow_count() -> None:
    concepts = [
        ConceptUpdate.from_event(ev)
        for ev in make_mock_concept_events(n=5)
    ]
    concepts = [c for c in concepts if c is not None]
    out = render_concept_list(concepts, max_items=2)
    assert "and 3 more concept(s)" in out


# ---------------------------------------------------------------------------
# MemoryLinkVizPanel widget API
# ---------------------------------------------------------------------------


def test_widget_starts_empty() -> None:
    w = MemoryLinkVizPanel()
    assert w.concept_count() == 0
    assert w.latest() is None


def test_widget_feed_events_groups_by_concept_id() -> None:
    w = MemoryLinkVizPanel()
    events = make_mock_concept_events(n=4)
    added = w.feed_events(events)
    assert added == 4
    assert w.concept_count() == 4


def test_widget_latest_update_replaces_older() -> None:
    """同じ concept_id で timestamp が新しい event が来たら上書き."""
    w = MemoryLinkVizPanel()
    old = TimelineEvent(
        event_id="old",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="2026-05-14T08:30:00Z",
        metadata={
            "concept_id": "c",
            "title": "Old Title",
            "summary": "old",
        },
    )
    new = TimelineEvent(
        event_id="new",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="2026-05-14T09:00:00Z",
        metadata={
            "concept_id": "c",
            "title": "New Title",
            "summary": "new",
        },
    )
    w.feed_events([old, new])
    assert w.concept_count() == 1
    latest = w.latest()
    assert latest is not None
    assert latest.title == "New Title"


def test_widget_older_update_does_not_overwrite_newer() -> None:
    """順序逆 (新しい先 → 古い後) でも latest が保たれる."""
    w = MemoryLinkVizPanel()
    new = TimelineEvent(
        event_id="new",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="2026-05-14T09:00:00Z",
        metadata={"concept_id": "c", "title": "New"},
    )
    old = TimelineEvent(
        event_id="old",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="2026-05-14T08:30:00Z",
        metadata={"concept_id": "c", "title": "Old"},
    )
    w.feed_events([new, old])
    latest = w.latest()
    assert latest is not None
    assert latest.title == "New"


def test_widget_order_is_latest_first() -> None:
    """concepts_in_order: 最新更新が先頭."""
    w = MemoryLinkVizPanel()
    w.feed_events(make_mock_concept_events(n=3))
    order = w.concepts_in_order()
    # mock events は timestamp 昇順 (i=0 が一番古い)
    # 後から来た event ほど _order の前に来る (insert(0, ...))
    assert order[0].concept_id == "free-energy"  # i=2 (latest)
    assert order[1].concept_id == "surprise-gate"
    assert order[2].concept_id == "memory-consolidation"


def test_widget_dedups_by_event_id() -> None:
    w = MemoryLinkVizPanel()
    events = make_mock_concept_events(n=3)
    w.feed_events(events)
    added = w.feed_events(events)
    assert added == 0
    assert w.concept_count() == 3


def test_widget_clear_resets_state() -> None:
    w = MemoryLinkVizPanel()
    w.feed_events(make_mock_concept_events(n=3))
    w.clear()
    assert w.concept_count() == 0
    assert w.latest() is None
    # clear 後は同じ event_id でも再受信できる
    added = w.feed_events(make_mock_concept_events(n=3))
    assert added == 3


def test_widget_skips_malformed_events() -> None:
    w = MemoryLinkVizPanel()
    bad = TimelineEvent(
        event_id="bad",
        task_id="t",
        node_id="n",
        event_type="concept_update",
        timestamp_utc="x",
        metadata={"title": "no concept_id"},
    )
    good = make_mock_concept_events(n=1)[0]
    added = w.feed_events([bad, good])
    assert added == 1


# ---------------------------------------------------------------------------
# Mock fixture sanity
# ---------------------------------------------------------------------------


def test_mock_events_have_correct_event_type() -> None:
    events = make_mock_concept_events(n=4)
    assert len(events) == 4
    for ev in events:
        assert ev.event_type == "concept_update"
        assert "concept_id" in ev.metadata


def test_mock_events_have_cross_links() -> None:
    """生成された concept は隣接する concept にリンクしている."""
    events = make_mock_concept_events(n=3)
    # 中央 concept は両隣にリンクする
    middle = events[1]
    linked = middle.metadata["linked_concept_ids"]
    assert len(linked) == 2
