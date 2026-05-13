"""F15 (t2/t3) — recognise PlantUML blocks as a distinct kind.

`mermaid` / `svg` を別 kind として扱ったのと同じ理由で、
` ```plantuml ... ``` ` フェンスは通常 code とは別 kind として扱いたい:

- `:fold by-tag plantuml` で diagram だけ畳む
- `prose` preset で「コード / テーブル / 図 (mermaid + svg + plantuml)」を畳む
- 後段で plantuml_render.py が hook できる識別レイヤを提供
"""

from __future__ import annotations


def test_plantuml_fence_is_classified_as_plantuml() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```plantuml\n@startuml\nAlice -> Bob\n@enduml\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].kind == "plantuml"
    assert regions[0].label == "plantuml"


def test_plantuml_uppercase_fence_also_classified() -> None:
    """info-string は case-insensitive (mermaid / svg と同じ)."""
    from llove.views.folding import find_code_block_regions

    src = "```PlantUML\n@startuml\n@enduml\n```\n"
    regions = find_code_block_regions(src)
    assert regions[0].kind == "plantuml"


def test_plantuml_mermaid_svg_code_coexist() -> None:
    from llove.views.folding import find_code_block_regions

    src = (
        "```python\nx = 1\n```\n"
        "between\n"
        "```mermaid\nflowchart LR\n```\n"
        "between\n"
        "```svg\n<svg/>\n```\n"
        "between\n"
        "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
    )
    regions = find_code_block_regions(src)
    kinds = [r.kind for r in regions]
    assert kinds == ["code", "mermaid", "svg", "plantuml"]


def test_close_by_kind_plantuml_only() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = (
        "```python\ncode body\n```\n"
        "```plantuml\n@startuml\nAlice -> Bob\n@enduml\n```\n"
    )
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "plantuml")
    rendered = apply_folds(src, regions, state)
    assert "code body" in rendered
    assert "Alice -> Bob" not in rendered


def test_summary_line_for_plantuml_uses_marker() -> None:
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    src = "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
    regions = find_code_block_regions(src)
    state = FoldState()
    state.close_by_kind(regions, "plantuml")
    rendered = apply_folds(src, regions, state)
    assert "▶" in rendered
    assert "plantuml" in rendered.lower()


def test_apply_preset_prose_folds_plantuml() -> None:
    """`prose` preset は mermaid / svg と同じく plantuml も畳む (図全般)."""
    from llove.views.folding import (
        FoldState,
        apply_preset,
        find_code_block_regions,
        find_heading_regions,
    )

    src = (
        "# H\n"
        "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
        "```py\nx = 1\n```\n"
    )
    regions = find_heading_regions(src) + find_code_block_regions(src)
    state = apply_preset(FoldState(), regions, "prose")
    closed = {(r.kind, state.is_closed(r.start_line)) for r in regions}
    assert ("heading", False) in closed
    assert ("code", True) in closed
    assert ("plantuml", True) in closed


def test_fold_command_by_tag_plantuml_routes_to_hook() -> None:
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

    result = dispatch(":fold by-tag plantuml", ctx, reg)
    assert result.ok is True
    assert captured == [("by-tag", ["plantuml"])]
