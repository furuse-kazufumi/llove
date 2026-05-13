"""F15 (t2/t3) — Diagram kind registry の単体テスト.

`llove.views.diagram_kinds` が folding.py / markdown_view.py の
4 分散ポイント (info-string 正規化 / summary marker / prose preset /
valid kind set) を 1 ヶ所に集約することを担保する。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# レジストリの形状
# ---------------------------------------------------------------------------


def test_diagram_kinds_registers_all_five_renderers() -> None:
    from llove.views.diagram_kinds import DIAGRAM_KIND_NAMES

    # 現状の 5 種類が揃っていること。ここを変更するときは folding /
    # markdown_view / renderer の存在を同時にチェックすること。
    assert frozenset(
        {"mermaid", "svg", "plantuml", "dot", "svgbob"}
    ) == DIAGRAM_KIND_NAMES


def test_diagram_kinds_is_immutable_tuple() -> None:
    """`DIAGRAM_KINDS` がタプルで、各 entry も frozen dataclass であること."""
    from llove.views.diagram_kinds import DIAGRAM_KINDS, DiagramKind

    assert isinstance(DIAGRAM_KINDS, tuple)
    for kind in DIAGRAM_KINDS:
        assert isinstance(kind, DiagramKind)
        # frozen dataclass なので属性書き換えが失敗すること
        try:
            kind.name = "tampered"  # type: ignore[misc]
        except Exception:
            pass
        else:
            raise AssertionError("DiagramKind should be frozen")


# ---------------------------------------------------------------------------
# normalise_info_string
# ---------------------------------------------------------------------------


def test_normalise_info_string_returns_canonical_name() -> None:
    from llove.views.diagram_kinds import normalise_info_string

    assert normalise_info_string("mermaid") == "mermaid"
    assert normalise_info_string("svg") == "svg"
    assert normalise_info_string("plantuml") == "plantuml"
    assert normalise_info_string("dot") == "dot"
    assert normalise_info_string("svgbob") == "svgbob"


def test_normalise_info_string_normalises_aliases() -> None:
    from llove.views.diagram_kinds import normalise_info_string

    # graphviz → dot, bob → svgbob
    assert normalise_info_string("graphviz") == "dot"
    assert normalise_info_string("bob") == "svgbob"


def test_normalise_info_string_returns_none_for_non_diagram() -> None:
    from llove.views.diagram_kinds import normalise_info_string

    assert normalise_info_string("python") is None
    assert normalise_info_string("rust") is None
    assert normalise_info_string("") is None
    assert normalise_info_string("code") is None


def test_normalise_info_string_is_case_sensitive_on_input() -> None:
    """呼び出し側で lower() してから渡す契約。大文字小文字は normalise しない."""
    from llove.views.diagram_kinds import normalise_info_string

    # contract: info_lower という名前のとおり、呼び出し側で lower 済前提
    assert normalise_info_string("MERMAID") is None
    assert normalise_info_string("Graphviz") is None


# ---------------------------------------------------------------------------
# diagram_summary_marker
# ---------------------------------------------------------------------------


def test_diagram_summary_marker_for_each_kind() -> None:
    from llove.views.diagram_kinds import diagram_summary_marker

    assert diagram_summary_marker("mermaid", "flowchart", 5) == (
        "▶ ◇ mermaid: flowchart (5 lines)"
    )
    assert diagram_summary_marker("svg", "icon", 3) == "▶ ◇ svg: icon (3 lines)"
    assert diagram_summary_marker("plantuml", "seq", 8) == (
        "▶ ◇ plantuml: seq (8 lines)"
    )
    assert diagram_summary_marker("dot", "graph", 4) == (
        "▶ ◇ dot: graph (4 lines)"
    )
    assert diagram_summary_marker("svgbob", "asciiart", 6) == (
        "▶ ◇ svgbob: asciiart (6 lines)"
    )


def test_diagram_summary_marker_returns_none_for_non_diagram() -> None:
    from llove.views.diagram_kinds import diagram_summary_marker

    assert diagram_summary_marker("code", "py", 5) is None
    assert diagram_summary_marker("heading", "Intro", 10) is None
    assert diagram_summary_marker("table", "table (3 cols)", 4) is None


# ---------------------------------------------------------------------------
# 統合: registry の変更が folding.py に波及することを確認
# ---------------------------------------------------------------------------


def test_registry_drives_find_code_block_regions() -> None:
    """folding.find_code_block_regions が registry を使う回帰防止."""
    from llove.views.diagram_kinds import DIAGRAM_KIND_NAMES
    from llove.views.folding import find_code_block_regions

    for kind in DIAGRAM_KIND_NAMES:
        src = f"```{kind}\nbody\n```\n"
        regions = find_code_block_regions(src)
        assert len(regions) == 1, f"{kind}: expected 1 region"
        assert regions[0].kind == kind, f"{kind}: kind mismatch"


def test_registry_drives_summary_for_all_diagram_kinds() -> None:
    """apply_folds が registry で diagram summary を作る回帰防止."""
    from llove.views.diagram_kinds import DIAGRAM_KIND_NAMES
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    for kind in DIAGRAM_KIND_NAMES:
        src = f"```{kind}\nbody\n```\n"
        regions = find_code_block_regions(src)
        state = FoldState()
        state.close_by_kind(regions, kind)
        rendered = apply_folds(src, regions, state)
        assert "▶ ◇" in rendered, f"{kind}: diamond marker missing"
        assert kind in rendered, f"{kind}: name missing in summary"


def test_registry_drives_prose_preset_for_all_diagram_kinds() -> None:
    """`prose` preset が registry に登録された全 diagram を畳むこと."""
    from llove.views.diagram_kinds import DIAGRAM_KIND_NAMES
    from llove.views.folding import (
        FoldState,
        apply_preset,
        find_code_block_regions,
    )

    for kind in DIAGRAM_KIND_NAMES:
        src = f"# H\n```{kind}\nbody\n```\n"
        regions = find_code_block_regions(src)
        state = apply_preset(FoldState(), regions, "prose")
        assert state.is_closed(regions[0].start_line), f"{kind}: not folded by prose"
