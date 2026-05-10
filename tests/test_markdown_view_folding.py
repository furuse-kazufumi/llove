"""F15 (u) — MarkdownView fold integration.

Folding lives in `llove.views.folding` (pure module, no UI deps). This file
verifies that MarkdownView wires that into its render path correctly: a
section closed via `toggle_fold` collapses to a `▶` summary line and the
hidden body never reaches the rendered surface.
"""

from __future__ import annotations


def _make_event(text: str):
    from llove.events import Event, EventKind

    return Event(kind=EventKind.NARRATION, payload={"text": text})


def test_markdown_view_exposes_fold_state_and_regions() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n## B\nb body\n"))
    regions = v.fold_regions()
    labels = {r.label for r in regions}
    assert {"A", "B"} <= labels
    # Default state: nothing closed.
    assert v.fold_state.closed_starts == set()


def test_markdown_view_toggle_fold_hides_section_body() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# Section\nbody-of-section\nmore\n"))
    region = v.fold_regions()[0]
    v.toggle_fold(region.start_line)
    rendered = v.last_render
    assert "▶ # Section" in rendered or "▶ Section" in rendered
    assert "body-of-section" not in rendered


def test_markdown_view_close_all_then_open_all() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# A\na body\n# B\nb body\n"))
    v.close_all_folds()
    rendered = v.last_render
    assert "a body" not in rendered
    assert "b body" not in rendered
    v.open_all_folds()
    rendered = v.last_render
    assert "a body" in rendered
    assert "b body" in rendered


def test_markdown_view_fold_persists_across_feeds_when_lines_unchanged() -> None:
    """Toggling a fold then feeding the *same* document again preserves state.

    This matters because a re-render (e.g. theme switch, width change) must
    not silently re-open everything the user closed.
    """
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(limit=1)  # only keep the latest entry
    src = "# Top\nbody\n"
    v.feed(_make_event(src))
    v.toggle_fold(v.fold_regions()[0].start_line)
    assert "body" not in v.last_render
    # Feed identical content again — fold must remain closed.
    v.feed(_make_event(src))
    assert "body" not in v.last_render


def test_markdown_view_no_fold_on_plain_paragraph() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("just a plain paragraph with no headings"))
    assert v.fold_regions() == []
