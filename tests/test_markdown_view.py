"""F15 (t1) MarkdownView — full GFM rendering pane.

NarrationView only supports lite markdown (bold + inline code). MarkdownView
is its full-GFM successor: headings, lists, fenced code, tables, blockquotes,
task lists, and the rest of the GFM surface, rendered through Rich's Markdown
backend (markdown-it-py under the hood).

Tests pin the contract every renderer must satisfy:
    1. Frontmatter / lifecycle parity with NarrationView (feed, last_render,
       NARRATION-only filtering).
    2. GFM constructs round-trip into the rendered surface (we don't assert
       on Rich-internal markup, only that the source content survives in some
       form so a human or export can recognise it).
"""

from __future__ import annotations


def _make_event(text: str, *, title: str | None = None):
    from llove.events import Event, EventKind

    payload: dict = {"text": text}
    if title is not None:
        payload["title"] = title
    return Event(kind=EventKind.NARRATION, payload=payload)


def test_markdown_view_initialises_with_empty_state() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    assert v.name == "markdown"
    assert v.last_source == ""
    assert v.last_render  # empty-state placeholder is non-empty


def test_markdown_view_renders_heading_and_paragraph() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# Title\n\nbody text."))
    assert "Title" in v.last_render
    assert "body text" in v.last_render
    assert v.last_source.startswith("# Title")


def test_markdown_view_renders_fenced_code_block() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("```python\nprint('hi')\n```"))
    assert "print" in v.last_render


def test_markdown_view_renders_unordered_list() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("- alpha\n- beta\n- gamma"))
    rendered = v.last_render
    assert "alpha" in rendered
    assert "beta" in rendered
    assert "gamma" in rendered


def test_markdown_view_renders_blockquote() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("> quoted line"))
    assert "quoted line" in v.last_render


def test_markdown_view_renders_inline_code_and_bold() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("call **foo** with `bar`"))
    rendered = v.last_render
    assert "foo" in rendered
    assert "bar" in rendered


def test_markdown_view_ignores_non_narration_events() -> None:
    from llove.events import Event, EventKind
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    initial = v.last_render
    v.feed(Event(kind=EventKind.SENSOR, payload={"sensor_id": "x", "value": 1.0}))
    assert v.last_render == initial
    assert v.last_source == ""


def test_markdown_view_drops_empty_text() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    initial = v.last_render
    v.feed(_make_event("   "))
    assert v.last_render == initial
    assert v.last_source == ""


def test_markdown_view_keeps_history_with_latest_first() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(limit=3)
    v.feed(_make_event("# first"))
    v.feed(_make_event("# second"))
    v.feed(_make_event("# third"))
    rendered = v.last_render
    assert "first" in rendered
    assert "second" in rendered
    assert "third" in rendered
    # Latest entry must be at the top of the rendered surface.
    assert rendered.index("third") < rendered.index("second")
    assert rendered.index("second") < rendered.index("first")


def test_markdown_view_history_respects_limit() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(limit=2)
    v.feed(_make_event("# one"))
    v.feed(_make_event("# two"))
    v.feed(_make_event("# three"))
    rendered = v.last_render
    assert "one" not in rendered
    assert "two" in rendered
    assert "three" in rendered


def test_markdown_view_title_prefixed_when_present() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("body", title="Section A"))
    assert "Section A" in v.last_render


def test_markdown_view_does_not_raise_on_malformed_payload() -> None:
    from llove.events import Event, EventKind
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    # text missing entirely — fail-closed, no exception.
    v.feed(Event(kind=EventKind.NARRATION, payload={}))
    # text is non-string
    v.feed(Event(kind=EventKind.NARRATION, payload={"text": 12345}))
    # Both must leave the view in a valid state with empty render unchanged.
    assert v.last_source == ""
