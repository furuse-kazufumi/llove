"""F15 (u8) — `make_markdown_fold_hook` factory tests.

The hook is the glue between the `:fold` builtin command and a concrete
MarkdownView instance. It keeps the command dispatcher view-agnostic while
providing a single-line wiring path for callers:

    ctx.hooks["fold"] = make_markdown_fold_hook(my_markdown_view)
"""

from __future__ import annotations


def _make_event(text: str):
    from llove.events import Event, EventKind

    return Event(kind=EventKind.NARRATION, payload={"text": text})


def test_fold_hook_close_all_calls_view() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n# B\nb body\n"))
    hook = make_markdown_fold_hook(v)

    out = hook("close-all", [])
    assert out is not None
    assert v.fold_state.closed_starts  # something got closed
    assert "body" not in v.last_render


def test_fold_hook_open_all_clears_state() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n"))
    v.close_all_folds()
    hook = make_markdown_fold_hook(v)

    out = hook("open-all", [])
    assert out is not None
    assert v.fold_state.closed_starts == set()
    assert "body" in v.last_render


def test_fold_hook_by_tag_only_closes_that_kind() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(_make_event("# A\na body\n```py\nx = 1\n```\n# B\nb body\n"))
    hook = make_markdown_fold_hook(v)

    hook("by-tag", ["code"])
    rendered = v.last_render
    # Headings stay open, code is closed.
    assert "a body" in rendered
    assert "b body" in rendered
    assert "x = 1" not in rendered


def test_fold_hook_toggle_specific_line() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(_make_event("# Section\nbody\n"))
    hook = make_markdown_fold_hook(v)

    region = v.fold_regions()[0]
    out = hook("toggle", [str(region.start_line)])
    assert out is not None
    assert v.fold_state.is_closed(region.start_line) is True
    # Toggling again opens it.
    hook("toggle", [str(region.start_line)])
    assert v.fold_state.is_closed(region.start_line) is False


def test_fold_hook_toggle_non_integer_returns_none() -> None:
    """Hook returns None for verbs it cannot honour — surfaced as an error."""
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(_make_event("# Section\nbody\n"))
    hook = make_markdown_fold_hook(v)

    assert hook("toggle", ["not-a-number"]) is None


def test_fold_hook_unknown_verb_returns_none() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(_make_event("# A\nbody\n"))
    hook = make_markdown_fold_hook(v)

    assert hook("unsupported-verb", []) is None


def test_fold_hook_integrates_with_dispatch() -> None:
    """End-to-end: `:fold close-all` through dispatch reaches the view."""
    from llove.term import (
        CommandRegistry,
        builtin_commands,
        dispatch,
        make_default_context,
        register_builtins,
    )
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    # Sanity: builtin registration includes the new command.
    assert "fold" in {c.name for c in builtin_commands()}

    reg = CommandRegistry()
    register_builtins(reg)
    ctx = make_default_context(reg)

    v = MarkdownView()
    v.feed(_make_event("# X\nhidden body line\n"))
    ctx.hooks["fold"] = make_markdown_fold_hook(v)

    result = dispatch(":fold close-all", ctx, reg)
    assert result.ok is True
    assert "hidden body line" not in v.last_render
