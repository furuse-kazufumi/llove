"""F15 (t2/t3) — recognise Graphviz dot blocks as a distinct kind.

`mermaid` / `svg` / `plantuml` を別 kind として扱ったのと同じ理由で、
` ```dot ... ``` ` フェンスは通常 code とは別 kind として扱いたい:

- `:fold by-tag dot` で diagram だけ畳む
- `prose` preset で「コード / テーブル / 図 (mermaid+svg+plantuml+dot)」を畳む
- 後段で dot_render.py が hook できる識別レイヤを提供
- info-string は ``dot`` (canonical) と ``graphviz`` (alias) の両方を受理し、
  ``kind="dot"`` に正規化する
"""

from __future__ import annotations


def test_dot_fence_is_classified_as_dot() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```dot\ndigraph G { A -> B }\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].kind == "dot"
    assert regions[0].label == "dot"


def test_dot_uppercase_fence_also_classified() -> None:
    """info-string は case-insensitive (mermaid / svg / plantuml と同じ)."""
    from llove.views.folding import find_code_block_regions

    src = "```DOT\ndigraph G { A -> B }\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "dot"


def test_graphviz_alias_normalises_to_dot() -> None:
    """``graphviz`` info-string は ``dot`` と同じ kind に正規化."""
    from llove.views.folding import find_code_block_regions

    src = "```graphviz\ndigraph G { A -> B }\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "dot"
    # label は元の info を保持 (downstream の renderer 選択は kind で行うため
    # label の正規化は不要)。
    assert regions[0].label == "graphviz"


def test_dot_coexists_with_other_diagram_kinds() -> None:
    from llove.views.folding import find_code_block_regions

    src = (
        "```python\nx = 1\n```\n"
        "```mermaid\nflowchart LR\n```\n"
        "```svg\n<svg/>\n```\n"
        "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
        "```dot\ndigraph G { A -> B }\n```\n"
    )
    regions = find_code_block_regions(src)
    kinds = [r.kind for r in regions]
    assert kinds == ["code", "mermaid", "svg", "plantuml", "dot"]


def test_close_by_kind_dot_only() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = (
        "```python\ncode body\n```\n"
        "```dot\ndigraph G { A -> B }\n```\n"
    )
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "dot")
    rendered = apply_folds(src, regions, state)
    assert "code body" in rendered
    assert "A -> B" not in rendered


def test_summary_line_for_dot_uses_marker() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = "```dot\ndigraph G { A -> B }\n```\n"
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "dot")
    rendered = apply_folds(src, regions, state)
    assert "▶" in rendered
    assert "dot" in rendered.lower()


def test_apply_preset_prose_folds_dot() -> None:
    """`prose` preset は mermaid / svg / plantuml と同じく dot も畳む (図全般)."""
    from llove.views.folding import (
        FoldState,
        apply_preset,
        find_code_block_regions,
        find_heading_regions,
    )

    src = (
        "# H\n"
        "```dot\ndigraph G { A -> B }\n```\n"
        "```py\nx = 1\n```\n"
    )
    regions = find_heading_regions(src) + find_code_block_regions(src)
    state = apply_preset(FoldState(), regions, "prose")
    closed = {(r.kind, state.is_closed(r.start_line)) for r in regions}
    assert ("heading", False) in closed
    assert ("code", True) in closed
    assert ("dot", True) in closed


def test_fold_command_by_tag_dot_routes_to_hook() -> None:
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

    result = dispatch(":fold by-tag dot", ctx, reg)
    assert result.ok is True
    assert captured == [("by-tag", ["dot"])]
