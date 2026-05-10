"""F15 (t2 prep) — recognise SVG blocks as a distinct kind.

`mermaid` を別 kind として扱ったのと同じ理由で、` ```svg ... ``` ` フェンスは
通常 code とは別の kind として扱いたい:
- `:fold by-tag svg` で diagram だけ畳む
- `prose` preset で「コード / テーブル / 図 (mermaid + svg)」を畳む
- 後段で svg_render.py が hook できる識別レイヤを提供
"""

from __future__ import annotations


def test_svg_fence_is_classified_as_svg() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```svg\n<svg/>\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].kind == "svg"
    assert regions[0].label == "svg"


def test_svg_uppercase_fence_also_classified() -> None:
    """info-string の case-insensitive を mermaid と同じく svg にも適用."""
    from llove.views.folding import find_code_block_regions

    src = "```SVG\n<svg/>\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "svg"


def test_svg_mermaid_code_coexist() -> None:
    from llove.views.folding import find_code_block_regions

    src = (
        "```python\nx = 1\n```\n"
        "between\n"
        "```mermaid\nflowchart LR\n```\n"
        "between\n"
        "```svg\n<svg/>\n```\n"
    )
    regions = find_code_block_regions(src)
    kinds = [r.kind for r in regions]
    assert kinds == ["code", "mermaid", "svg"]


def test_close_by_kind_svg_only() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = (
        "```python\ncode body\n```\n"
        "```svg\n<svg width='10'/>\n```\n"
    )
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "svg")
    rendered = apply_folds(src, regions, state)
    assert "code body" in rendered
    assert "<svg width='10'/>" not in rendered


def test_summary_line_for_svg_uses_marker() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = "```svg\n<svg/>\n```\n"
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "svg")
    rendered = apply_folds(src, regions, state)
    assert "▶" in rendered
    assert "svg" in rendered.lower()


def test_apply_preset_prose_folds_svg() -> None:
    """`prose` preset は mermaid だけでなく svg も畳む (図全般)."""
    from llove.views.folding import (
        FoldState,
        apply_preset,
        find_code_block_regions,
        find_heading_regions,
    )

    src = "# H\n```svg\n<svg/>\n```\n```py\nx = 1\n```\n"
    regions = find_heading_regions(src) + find_code_block_regions(src)
    state = apply_preset(FoldState(), regions, "prose")
    closed = {(r.kind, state.is_closed(r.start_line)) for r in regions}
    assert ("heading", False) in closed
    assert ("code", True) in closed
    assert ("svg", True) in closed


def test_fold_command_by_tag_svg_routes_to_hook() -> None:
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

    result = dispatch(":fold by-tag svg", ctx, reg)
    assert result.ok is True
    assert captured == [("by-tag", ["svg"])]
