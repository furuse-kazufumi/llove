"""F15 (u) — MarkdownView code/table fold integration.

After the folding tier learned about code blocks and tables, MarkdownView's
`fold_regions()` must surface all three kinds together so the UI can offer
a single key/command for "toggle the fold on this line" regardless of what
kind of construct it is.
"""

from __future__ import annotations


def _make_event(text: str):
    from llove.events import Event, EventKind

    return Event(kind=EventKind.NARRATION, payload={"text": text})


def test_fold_regions_includes_code_block() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("# Title\n```python\nprint(1)\n```\nbody\n"))
    kinds = {r.kind for r in v.fold_regions()}
    assert "heading" in kinds
    assert "code" in kinds


def test_fold_regions_includes_table() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(
        _make_event(
            "intro\n"
            "| col1 | col2 |\n"
            "|------|------|\n"
            "| a    | b    |\n"
        )
    )
    kinds = {r.kind for r in v.fold_regions()}
    assert "table" in kinds


def test_toggle_fold_on_code_block_hides_body() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(_make_event("intro\n```py\nsecret = 42\n```\nouter\n"))
    code_region = next(r for r in v.fold_regions() if r.kind == "code")
    v.toggle_fold(code_region.start_line)
    rendered = v.last_render
    assert "secret = 42" not in rendered
    # Surrounding text remains.
    assert "intro" in rendered
    assert "outer" in rendered


def test_toggle_fold_on_table_hides_rows() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(
        _make_event(
            "preface\n"
            "| a | b |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
            "| 3 | 4 |\n"
            "epilogue\n"
        )
    )
    table_region = next(r for r in v.fold_regions() if r.kind == "table")
    v.toggle_fold(table_region.start_line)
    rendered = v.last_render
    assert "| 1 | 2 |" not in rendered
    assert "| 3 | 4 |" not in rendered
    assert "preface" in rendered
    assert "epilogue" in rendered


def test_close_all_folds_collapses_every_kind() -> None:
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(
        _make_event(
            "# Section\n"
            "intro\n"
            "```py\n"
            "x = 1\n"
            "```\n"
            "| a | b |\n"
            "|---|---|\n"
            "| 1 | 2 |\n"
        )
    )
    v.close_all_folds()
    rendered = v.last_render
    # No body content should leak through.
    assert "intro" not in rendered  # under # Section
    assert "x = 1" not in rendered
    assert "| 1 | 2 |" not in rendered
