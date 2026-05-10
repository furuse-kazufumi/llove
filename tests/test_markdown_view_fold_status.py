"""F15 (u6) — MarkdownView fold metrics + status string.

The view must surface a simple, render-friendly metric so a status bar can
display ``[fold: 3 closed / 12 total]`` without the caller having to know
the internals. Coverage:

    - `fold_metrics()` returns ``(closed, total)`` integers
    - `fold_status()` returns the canonical localised status string
    - mutation operations refresh the metric (and the widget border subtitle)
    - empty docs and unfeed views report (0, 0) without raising
"""

from __future__ import annotations


def _make_event(text: str):
    from llove.events import Event, EventKind

    return Event(kind=EventKind.NARRATION, payload={"text": text})


def test_fold_metrics_zero_zero_for_unfeed_view() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    assert v.fold_metrics() == (0, 0)


def test_fold_metrics_counts_total_regions() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n## B\nb body\n```py\nx\n```\n"))
    closed, total = v.fold_metrics()
    assert closed == 0
    assert total == 3  # # A, ## B, code fence


def test_fold_metrics_after_close_all() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n## B\nb body\n"))
    v.close_all_folds()
    closed, total = v.fold_metrics()
    assert closed == total == 2


def test_fold_status_string_format() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n```py\nx\n```\n"))
    v.toggle_fold(0)  # close the heading
    status = v.fold_status()
    # We don't pin the exact wording, only that both numbers and the word
    # "fold" appear so a status bar can render it sensibly.
    assert "fold" in status.lower()
    assert "1" in status
    assert "2" in status


def test_fold_status_empty_view() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    status = v.fold_status()
    assert "0" in status


def test_border_subtitle_updates_on_close_all() -> None:
    """The Textual widget border_subtitle should reflect fold metrics."""
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n"))
    v.close_all_folds()
    sub = str(v.border_subtitle or "")
    assert "fold" in sub.lower()
    assert "1" in sub  # 1 closed = 1 total


def test_open_all_resets_closed_count_to_zero() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n"))
    v.close_all_folds()
    assert v.fold_metrics()[0] == 1
    v.open_all_folds()
    assert v.fold_metrics()[0] == 0
