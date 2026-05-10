"""F15 (u8) — `:fold preset <name>` rule sets.

Preset semantics (from REQUIREMENTS / project_llove_md_svg_mermaid_fold.md):

    outline    — only h1/h2 visible. Everything else (h3+, code, table)
                 collapses into summary lines. The user wants the document
                 skeleton.
    code       — only fenced code blocks visible. Headings + tables
                 collapse so the reader can focus on snippets.
    data-only  — only tables visible. Headings + code collapse.
    prose      — code blocks and tables collapse; headings stay open.

Preset application is idempotent: applying the same preset twice yields
the same FoldState (no toggling).
"""

from __future__ import annotations


def _all_regions(src: str):
    from llove.views.folding import (
        find_code_block_regions,
        find_heading_regions,
        find_table_regions,
    )

    return (
        find_heading_regions(src)
        + find_code_block_regions(src)
        + find_table_regions(src)
    )


_DOC = (
    "# H1\n"
    "intro\n"
    "## H2\n"
    "h2 body\n"
    "### H3\n"
    "h3 body\n"
    "```py\n"
    "x = 1\n"
    "```\n"
    "| a | b |\n"
    "|---|---|\n"
    "| 1 | 2 |\n"
)


def _kinds_closed(regions, state) -> dict:
    """Return a mapping of (kind, level) -> closed? for each region."""
    return {
        (r.kind, r.level, r.label): state.is_closed(r.start_line)
        for r in regions
    }


def test_apply_preset_outline_keeps_only_h1_h2_open() -> None:
    from llove.views.folding import FoldState, apply_preset

    regions = _all_regions(_DOC)
    state = apply_preset(FoldState(), regions, "outline")
    closed = _kinds_closed(regions, state)
    # h1 / h2 must be OPEN, h3+ closed.
    h1 = [v for (k, lvl, _), v in closed.items() if k == "heading" and lvl == 1]
    h2 = [v for (k, lvl, _), v in closed.items() if k == "heading" and lvl == 2]
    h3 = [v for (k, lvl, _), v in closed.items() if k == "heading" and lvl == 3]
    assert all(v is False for v in h1)
    assert all(v is False for v in h2)
    assert all(v is True for v in h3)
    # Code and table closed.
    assert all(v is True for (k, _, _), v in closed.items() if k == "code")
    assert all(v is True for (k, _, _), v in closed.items() if k == "table")


def test_apply_preset_code_keeps_only_code_open() -> None:
    from llove.views.folding import FoldState, apply_preset

    regions = _all_regions(_DOC)
    state = apply_preset(FoldState(), regions, "code")
    closed = _kinds_closed(regions, state)
    assert all(v is True for (k, _, _), v in closed.items() if k == "heading")
    assert all(v is False for (k, _, _), v in closed.items() if k == "code")
    assert all(v is True for (k, _, _), v in closed.items() if k == "table")


def test_apply_preset_data_only_keeps_only_tables_open() -> None:
    from llove.views.folding import FoldState, apply_preset

    regions = _all_regions(_DOC)
    state = apply_preset(FoldState(), regions, "data-only")
    closed = _kinds_closed(regions, state)
    assert all(v is True for (k, _, _), v in closed.items() if k == "heading")
    assert all(v is True for (k, _, _), v in closed.items() if k == "code")
    assert all(v is False for (k, _, _), v in closed.items() if k == "table")


def test_apply_preset_prose_collapses_code_and_table() -> None:
    from llove.views.folding import FoldState, apply_preset

    regions = _all_regions(_DOC)
    state = apply_preset(FoldState(), regions, "prose")
    closed = _kinds_closed(regions, state)
    # Headings stay open.
    assert all(v is False for (k, _, _), v in closed.items() if k == "heading")
    assert all(v is True for (k, _, _), v in closed.items() if k == "code")
    assert all(v is True for (k, _, _), v in closed.items() if k == "table")


def test_apply_preset_unknown_returns_unchanged_state() -> None:
    from llove.views.folding import FoldState, apply_preset

    regions = _all_regions(_DOC)
    seed = FoldState(closed_starts={0})
    out = apply_preset(seed, regions, "no-such-preset")
    # Unknown preset must NOT touch the input state. We accept either the
    # same instance or an equal copy — both satisfy "leave the user alone".
    assert out.closed_starts == {0}


def test_apply_preset_is_idempotent() -> None:
    from llove.views.folding import FoldState, apply_preset

    regions = _all_regions(_DOC)
    once = apply_preset(FoldState(), regions, "outline")
    twice = apply_preset(once, regions, "outline")
    assert once.closed_starts == twice.closed_starts


def test_fold_command_preset_routes_to_hook() -> None:
    from llove.term import (
        CommandRegistry,
        builtin_commands,
        dispatch,
        make_default_context,
        register_builtins,
    )

    assert "fold" in {c.name for c in builtin_commands()}
    reg = CommandRegistry()
    register_builtins(reg)
    ctx = make_default_context(reg)

    captured: list[tuple[str, list[str]]] = []
    ctx.hooks["fold"] = lambda v, a: captured.append((v, list(a))) or ("ok",)

    result = dispatch(":fold preset outline", ctx, reg)
    assert result.ok is True
    assert captured == [("preset", ["outline"])]


def test_fold_command_preset_requires_name() -> None:
    from llove.term import (
        CommandRegistry,
        dispatch,
        make_default_context,
        register_builtins,
    )

    reg = CommandRegistry()
    register_builtins(reg)
    ctx = make_default_context(reg)

    result = dispatch(":fold preset", ctx, reg)
    assert result.ok is False


def test_make_markdown_fold_hook_handles_preset() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(__import__(
        "llove.events", fromlist=["Event"]
    ).Event(
        kind=__import__("llove.events", fromlist=["EventKind"]).EventKind.NARRATION,
        payload={"text": _DOC},
    ))
    hook = make_markdown_fold_hook(v)
    out = hook("preset", ["outline"])
    assert out is not None
    # Code and tables are now hidden; h1 / h2 still visible.
    rendered = v.last_render
    assert "x = 1" not in rendered
    assert "| 1 | 2 |" not in rendered
    assert "H1" in rendered
    assert "H2" in rendered


def test_make_markdown_fold_hook_unknown_preset_returns_none() -> None:
    from llove.views.markdown_view import MarkdownView, make_markdown_fold_hook

    v = MarkdownView()
    v.feed(__import__(
        "llove.events", fromlist=["Event"]
    ).Event(
        kind=__import__("llove.events", fromlist=["EventKind"]).EventKind.NARRATION,
        payload={"text": "# A\nbody\n"},
    ))
    hook = make_markdown_fold_hook(v)
    assert hook("preset", ["no-such-preset"]) is None
