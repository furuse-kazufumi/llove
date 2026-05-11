"""Tests for Phase 6 explainability views.

Covers HypothesisBoardView / DiffViewerView / MetricDashboardView /
QualitativeMemoView via the same feed() / public-API paths the
production app uses, without spinning a Textual app.
"""

from __future__ import annotations

from llove.events import Event, EventKind
from llove.views.diff_viewer import DiffViewerView, compute_diff_lines
from llove.views.hypothesis_board import HypothesisBoardView
from llove.views.memo import QualitativeMemoView
from llove.views.metric_dashboard import MetricDashboardView, _sparkline

# ---------------------------------------------------------------------------
# HypothesisBoardView
# ---------------------------------------------------------------------------


class TestHypothesisBoard:
    def test_empty_by_default(self) -> None:
        v = HypothesisBoardView()
        assert v._cards == {}

    def test_add_hypothesis(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis(
            {
                "id": "h1",
                "statement": "X has no effect on Y.",
                "independent_variable": "X",
                "dependent_variable": "Y",
                "expected_effect": "negligible",
                "falsifier": "|effect| > eps",
                "status": "proposed",
            }
        )
        assert "h1" in v._cards
        assert v._cards["h1"]["statement"].startswith("X has no")

    def test_status_update_via_set_status(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis({"id": "h1", "statement": "S"})
        v.set_status("h1", "approved")
        assert v._cards["h1"]["status"] == "approved"

    def test_set_status_ignores_unknown_id(self) -> None:
        v = HypothesisBoardView()
        v.set_status("ghost", "approved")  # no-op
        assert v._cards == {}

    def test_set_status_ignores_unknown_status(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis({"id": "h1", "statement": "S"})
        v.set_status("h1", "exploded")
        assert v._cards["h1"]["status"] == "proposed"  # unchanged

    def test_unknown_status_defaults_to_proposed(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis({"id": "h1", "statement": "S", "status": "exploded"})
        assert v._cards["h1"]["status"] == "proposed"

    def test_default_id_when_missing(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis({"statement": "first"})
        v.add_hypothesis({"statement": "second"})
        assert list(v._cards.keys()) == ["h1", "h2"]

    def test_empty_statement_dropped(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis({"id": "h1", "statement": ""})
        assert v._cards == {}

    def test_limit_evicts_oldest(self) -> None:
        v = HypothesisBoardView(limit=2)
        v.add_hypothesis({"id": "h1", "statement": "first"})
        v.add_hypothesis({"id": "h2", "statement": "second"})
        v.add_hypothesis({"id": "h3", "statement": "third"})
        assert list(v._cards.keys()) == ["h2", "h3"]

    def test_feed_with_single_hypothesis_payload(self) -> None:
        v = HypothesisBoardView()
        v.feed(
            Event(
                kind=EventKind.NARRATION,
                payload={"hypothesis": {"id": "h1", "statement": "S"}},
            )
        )
        assert "h1" in v._cards

    def test_feed_with_list_payload(self) -> None:
        v = HypothesisBoardView()
        v.feed(
            Event(
                kind=EventKind.NARRATION,
                payload={
                    "hypotheses": [
                        {"id": "h1", "statement": "one"},
                        {"id": "h2", "statement": "two"},
                    ]
                },
            )
        )
        assert {"h1", "h2"} <= set(v._cards.keys())

    def test_feed_status_change(self) -> None:
        v = HypothesisBoardView()
        v.add_hypothesis({"id": "h1", "statement": "S"})
        v.feed(
            Event(
                kind=EventKind.NARRATION,
                payload={"hypothesis_status": {"id": "h1", "status": "approved"}},
            )
        )
        assert v._cards["h1"]["status"] == "approved"

    def test_feed_ignores_non_narration(self) -> None:
        v = HypothesisBoardView()
        v.feed(Event(kind=EventKind.SENSOR, payload={"value": 1, "sensor_id": "x"}))
        assert v._cards == {}


# ---------------------------------------------------------------------------
# DiffViewerView
# ---------------------------------------------------------------------------


class TestDiffViewer:
    def test_compute_diff_basic(self) -> None:
        diff = compute_diff_lines("a\nb\nc", "a\nB\nc")
        markers = [m for m, _ in diff]
        # Expect at least one '-' and one '+' for the modified line
        assert "-" in markers
        assert "+" in markers

    def test_compute_diff_identical_yields_only_context(self) -> None:
        diff = compute_diff_lines("same\nlines", "same\nlines")
        assert all(m == " " for m, _ in diff)

    def test_set_diff_records_pair(self) -> None:
        v = DiffViewerView()
        v.set_diff(ai_proposal="hello", human_edited="hi", label="round1")
        assert len(v._pairs) == 1
        label, lines = v._pairs[0]
        assert label == "round1"
        assert lines  # non-empty

    def test_history_evicts_oldest(self) -> None:
        v = DiffViewerView(history=2)
        v.set_diff(ai_proposal="a", human_edited="b", label="r1")
        v.set_diff(ai_proposal="c", human_edited="d", label="r2")
        v.set_diff(ai_proposal="e", human_edited="f", label="r3")
        labels = [p[0] for p in v._pairs]
        assert labels == ["r2", "r3"]

    def test_feed_diff_payload(self) -> None:
        v = DiffViewerView()
        v.feed(
            Event(
                kind=EventKind.NARRATION,
                payload={
                    "diff": {
                        "ai_proposal": "old",
                        "human_edited": "new",
                        "label": "step1",
                    }
                },
            )
        )
        assert len(v._pairs) == 1
        assert v._pairs[0][0] == "step1"

    def test_feed_garbage_payload_no_crash(self) -> None:
        v = DiffViewerView()
        # missing strings should silently drop the event
        v.feed(
            Event(
                kind=EventKind.NARRATION,
                payload={"diff": {"ai_proposal": 1, "human_edited": None}},
            )
        )
        v.feed(Event(kind=EventKind.NARRATION, payload={"diff": "not-a-dict"}))
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "x", "value": 1}))
        assert len(v._pairs) == 0


# ---------------------------------------------------------------------------
# MetricDashboardView
# ---------------------------------------------------------------------------


class TestMetricDashboard:
    def test_record_adds_metric(self) -> None:
        v = MetricDashboardView()
        v.record("accuracy", 0.91)
        assert "accuracy" in v._samples
        assert list(v._samples["accuracy"]) == [0.91]
        assert v._counts["accuracy"] == 1

    def test_record_history_capped(self) -> None:
        v = MetricDashboardView(per_metric_history=3)
        for i in range(5):
            v.record("m", float(i))
        # only the last 3 stay in the buffer
        assert list(v._samples["m"]) == [2.0, 3.0, 4.0]
        # but the total counter is the full feed
        assert v._counts["m"] == 5

    def test_record_ignores_empty_name(self) -> None:
        v = MetricDashboardView()
        v.record("", 1.0)
        assert v._samples == {}

    def test_record_ignores_non_numeric(self) -> None:
        v = MetricDashboardView()
        v.record("m", "not-a-number")  # type: ignore[arg-type]
        assert "m" not in v._samples

    def test_feed_sensor_event(self) -> None:
        v = MetricDashboardView()
        v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "lat_ms", "value": 42}))
        assert list(v._samples["lat_ms"]) == [42.0]

    def test_feed_info_event_with_metric_key(self) -> None:
        v = MetricDashboardView()
        v.feed(
            Event(
                kind=EventKind.INFO,
                payload={"metric": "score", "value": 0.7, "unit": "frac"},
            )
        )
        assert "score" in v._samples
        assert v._units["score"] == "frac"

    def test_sparkline_short_input_returns_empty(self) -> None:
        assert _sparkline([]) == ""
        assert _sparkline([1.0]) == ""

    def test_sparkline_constant_input_renders_flat(self) -> None:
        spark = _sparkline([1.0, 1.0, 1.0])
        assert len(spark) == 3
        assert len(set(spark)) == 1  # all the same glyph

    def test_sparkline_varying_input(self) -> None:
        spark = _sparkline([0.0, 1.0])
        assert spark[0] != spark[1]

    def test_feed_ignores_unrelated_kinds(self) -> None:
        v = MetricDashboardView()
        v.feed(Event(kind=EventKind.NARRATION, payload={"text": "hi"}))
        assert v._samples == {}


# ---------------------------------------------------------------------------
# QualitativeMemoView
# ---------------------------------------------------------------------------


class TestQualitativeMemo:
    def test_add_memo(self) -> None:
        v = QualitativeMemoView()
        v.add_memo("a thought")
        assert len(v._entries) == 1
        assert v._count == 1

    def test_blank_memo_ignored(self) -> None:
        v = QualitativeMemoView()
        v.add_memo("   ")
        assert v._entries == []

    def test_limit_evicts_oldest(self) -> None:
        v = QualitativeMemoView(limit=2)
        for i in range(4):
            v.add_memo(f"memo {i}")
        joined = "\n\n".join(v._entries)
        assert "memo 3" in joined
        assert "memo 0" not in joined

    def test_memo_records_author_and_tag(self) -> None:
        v = QualitativeMemoView()
        v.add_memo("note", author="Alice", tag="design")
        block = v._entries[0]
        assert "Alice" in block
        assert "#design" in block

    def test_lite_markdown_bold_substitution(self) -> None:
        v = QualitativeMemoView()
        v.add_memo("**emphasised** word")
        block = v._entries[0]
        assert "[bold]emphasised[/bold]" in block

    def test_user_brackets_escaped(self) -> None:
        v = QualitativeMemoView()
        v.add_memo("see [TODO: fix]")
        block = v._entries[0]
        # brackets escaped to prevent Rich markup hijack
        assert "\\[TODO" in block

    def test_feed_memo_payload(self) -> None:
        v = QualitativeMemoView()
        v.feed(
            Event(
                kind=EventKind.NARRATION,
                payload={"memo": {"text": "hello", "author": "Bob", "tag": "qa"}},
            )
        )
        assert len(v._entries) == 1

    def test_feed_ignores_non_memo_narration(self) -> None:
        v = QualitativeMemoView()
        v.feed(Event(kind=EventKind.NARRATION, payload={"text": "plain narration"}))
        assert v._entries == []

    def test_feed_garbage_memo_no_crash(self) -> None:
        v = QualitativeMemoView()
        v.feed(Event(kind=EventKind.NARRATION, payload={"memo": "not-a-dict"}))
        v.feed(Event(kind=EventKind.NARRATION, payload={"memo": {"text": 123}}))
        assert v._entries == []
