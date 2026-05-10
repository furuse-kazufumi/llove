"""F15 (t3 prep / u) — recognise Mermaid blocks as a distinct kind.

A fenced block like ` ```mermaid ... ``` ` is technically a code block, but
the user typically wants it folded *separately* from regular code: e.g.
`:fold by-tag mermaid` to collapse all diagrams without touching code, or
the `prose` preset hiding only diagrams + tables but keeping code visible
when the document is technical.

Implementation strategy: `find_code_block_regions` re-labels Mermaid
fences with `kind="mermaid"` (label = original info-string), so the rest
of the pipeline (FoldState.close_by_kind / apply_folds / presets) needs no
changes.
"""

from __future__ import annotations


def test_mermaid_fence_is_classified_as_mermaid() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```mermaid\nflowchart LR\nA --> B\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].kind == "mermaid"
    assert regions[0].label == "mermaid"


def test_non_mermaid_fence_keeps_kind_code() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```python\nprint(1)\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "code"


def test_mermaid_and_code_fences_coexist() -> None:
    from llove.views.folding import find_code_block_regions

    src = (
        "```python\nx = 1\n```\n"
        "intro\n"
        "```mermaid\nflowchart LR\n```\n"
    )
    regions = find_code_block_regions(src)
    kinds = [r.kind for r in regions]
    assert kinds == ["code", "mermaid"]


def test_close_by_kind_mermaid_only() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = (
        "```python\ncode body\n```\n"
        "between\n"
        "```mermaid\ndiagram body\n```\n"
    )
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "mermaid")
    rendered = apply_folds(src, regions, state)
    assert "code body" in rendered  # python code untouched
    assert "diagram body" not in rendered  # mermaid hidden


def test_summary_line_for_mermaid_uses_marker_prefix() -> None:
    """A folded mermaid block should be visually distinguishable from code."""
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = "```mermaid\nflowchart LR\nA --> B\n```\n"
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "mermaid")
    rendered = apply_folds(src, regions, state)
    assert "▶" in rendered
    assert "mermaid" in rendered.lower()


def test_apply_preset_prose_folds_mermaid() -> None:
    """The `prose` preset hides distractions; mermaid counts as one."""
    from llove.views.folding import FoldState, apply_preset

    from llove.views.folding import find_code_block_regions, find_heading_regions

    src = "# H\n```mermaid\nflowchart LR\n```\n```py\nx = 1\n```\n"
    regions = find_heading_regions(src) + find_code_block_regions(src)
    state = apply_preset(FoldState(), regions, "prose")
    # heading open, code closed, mermaid closed.
    closed = {(r.kind, state.is_closed(r.start_line)) for r in regions}
    assert ("heading", False) in closed
    assert ("code", True) in closed
    assert ("mermaid", True) in closed


def test_apply_preset_data_only_folds_mermaid() -> None:
    """`data-only` shows only tables; mermaid is not a table → hidden."""
    from llove.views.folding import (
        FoldState,
        apply_preset,
        find_code_block_regions,
        find_table_regions,
    )

    src = "```mermaid\nflowchart LR\n```\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    regions = find_code_block_regions(src) + find_table_regions(src)
    state = apply_preset(FoldState(), regions, "data-only")
    closed = {(r.kind, state.is_closed(r.start_line)) for r in regions}
    assert ("mermaid", True) in closed
    assert ("table", False) in closed


def test_markdown_view_fold_regions_includes_mermaid_kind() -> None:
    from llove.events import Event, EventKind
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    v.feed(
        Event(
            kind=EventKind.NARRATION,
            payload={"text": "intro\n```mermaid\nflowchart LR\nA --> B\n```\n"},
        )
    )
    kinds = {r.kind for r in v.fold_regions()}
    assert "mermaid" in kinds


def test_fold_command_by_tag_mermaid_routes_to_hook() -> None:
    from llove.term import (
        CommandRegistry,
        dispatch,
        make_default_context,
        register_builtins,
    )

    reg = CommandRegistry()
    register_builtins(reg)
    ctx = make_default_context(reg)
    captured: list[tuple[str, list[str]]] = []
    ctx.hooks["fold"] = lambda v, a: captured.append((v, list(a))) or ("ok",)

    result = dispatch(":fold by-tag mermaid", ctx, reg)
    assert result.ok is True
    assert captured == [("by-tag", ["mermaid"])]
