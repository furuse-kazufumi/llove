"""F15 (t2/t3) — recognise svgbob blocks as a distinct kind.

`mermaid` / `svg` / `plantuml` / `dot` を別 kind として扱ったのと
同じ理由で、` ```svgbob ... ``` ` フェンスは通常 code とは別 kind:

- `:fold by-tag svgbob` で diagram だけ畳む
- `prose` preset で「コード / テーブル / 図 (mermaid+svg+plantuml+dot+svgbob)」を畳む
- 後段で svgbob_render.py が hook できる識別レイヤを提供
- info-string は ``svgbob`` (canonical) と ``bob`` (短縮 alias) の両方を受理し、
  ``kind="svgbob"`` に正規化する
"""

from __future__ import annotations


def test_svgbob_fence_is_classified_as_svgbob() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```svgbob\n+--+\n|  |\n+--+\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].kind == "svgbob"
    assert regions[0].label == "svgbob"


def test_svgbob_uppercase_fence_also_classified() -> None:
    """info-string は case-insensitive (mermaid / svg / plantuml / dot と同じ)."""
    from llove.views.folding import find_code_block_regions

    src = "```SVGBOB\n+--+\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "svgbob"


def test_bob_alias_normalises_to_svgbob() -> None:
    """``bob`` info-string は ``svgbob`` と同じ kind に正規化."""
    from llove.views.folding import find_code_block_regions

    src = "```bob\n+--+\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "svgbob"
    # label は元の info を保持
    assert regions[0].label == "bob"


def test_svgbob_coexists_with_other_diagram_kinds() -> None:
    from llove.views.folding import find_code_block_regions

    src = (
        "```python\nx = 1\n```\n"
        "```mermaid\nflowchart LR\n```\n"
        "```svg\n<svg/>\n```\n"
        "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
        "```dot\ndigraph G { A -> B }\n```\n"
        "```svgbob\n+--+\n```\n"
    )
    regions = find_code_block_regions(src)
    kinds = [r.kind for r in regions]
    assert kinds == ["code", "mermaid", "svg", "plantuml", "dot", "svgbob"]


def test_close_by_kind_svgbob_only() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = (
        "```python\ncode body\n```\n"
        "```svgbob\n+ AAA +\n+-----+\n```\n"
    )
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "svgbob")
    rendered = apply_folds(src, regions, state)
    assert "code body" in rendered
    assert "AAA" not in rendered


def test_summary_line_for_svgbob_uses_marker() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = "```svgbob\n+--+\n```\n"
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "svgbob")
    rendered = apply_folds(src, regions, state)
    assert "▶" in rendered
    assert "svgbob" in rendered.lower()


def test_apply_preset_prose_folds_svgbob() -> None:
    """`prose` preset は mermaid/svg/plantuml/dot と同じく svgbob も畳む (図全般)."""
    from llove.views.folding import (
        FoldState,
        apply_preset,
        find_code_block_regions,
        find_heading_regions,
    )

    src = (
        "# H\n"
        "```svgbob\n+--+\n```\n"
        "```py\nx = 1\n```\n"
    )
    regions = find_heading_regions(src) + find_code_block_regions(src)
    state = apply_preset(FoldState(), regions, "prose")
    closed = {(r.kind, state.is_closed(r.start_line)) for r in regions}
    assert ("heading", False) in closed
    assert ("code", True) in closed
    assert ("svgbob", True) in closed


def test_fold_command_by_tag_svgbob_routes_to_hook() -> None:
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

    result = dispatch(":fold by-tag svgbob", ctx, reg)
    assert result.ok is True
    assert captured == [("by-tag", ["svgbob"])]
