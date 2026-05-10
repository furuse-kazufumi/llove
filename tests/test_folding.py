"""F15 (u) Foldable Blocks — pure data/algorithm tier.

This module is UI-agnostic by design. The MarkdownView, NotebookView,
JSONTreeView etc. will all delegate fold calculation here. We test:

    1. Heading region detection (Markdown ATX `#`/`##`/...).
    2. Nesting: a section spans until the next heading at same-or-shallower
       level, never further (so `## A` ends when the next `##` or `#` starts).
    3. `FoldState` open/close primitives (toggle, close-all, open-all,
       close-by-tag).
    4. `apply_folds` rendering — closed sections collapse to a one-line
       summary `▶ ## Heading (N lines)` matching (u4); open sections pass
       through verbatim.
    5. Fail-closed: malformed input never raises, returns input unchanged.
"""

from __future__ import annotations


def test_find_heading_regions_single_section() -> None:
    from llove.views.folding import find_heading_regions

    src = "# Title\nbody line\nmore body\n"
    regions = find_heading_regions(src)
    assert len(regions) == 1
    r = regions[0]
    assert r.kind == "heading"
    assert r.level == 1
    assert r.label == "Title"
    assert r.start_line == 0
    # End is inclusive of the last body line (index 2). We treat end_line as
    # the last line that belongs to the section.
    assert r.end_line == 2


def test_find_heading_regions_two_sibling_sections() -> None:
    from llove.views.folding import find_heading_regions

    src = "# A\nbody A\n# B\nbody B\n"
    regions = find_heading_regions(src)
    assert len(regions) == 2
    assert regions[0].label == "A"
    assert regions[0].start_line == 0
    assert regions[0].end_line == 1
    assert regions[1].label == "B"
    assert regions[1].start_line == 2
    assert regions[1].end_line == 3


def test_find_heading_regions_nested() -> None:
    from llove.views.folding import find_heading_regions

    src = "# Top\nintro\n## Sub\nsub body\n## Sub2\ns2 body\n# Other\no body\n"
    regions = find_heading_regions(src)
    levels_labels = [(r.level, r.label, r.start_line, r.end_line) for r in regions]
    # Outer Top section spans from line 0 through line 5 (right before # Other).
    # Inner Sub from line 2..3, Sub2 from line 4..5.
    assert (1, "Top", 0, 5) in levels_labels
    assert (2, "Sub", 2, 3) in levels_labels
    assert (2, "Sub2", 4, 5) in levels_labels
    assert (1, "Other", 6, 7) in levels_labels


def test_find_heading_regions_empty_and_no_headings() -> None:
    from llove.views.folding import find_heading_regions

    assert find_heading_regions("") == []
    assert find_heading_regions("just text\nno headings\n") == []


def test_find_heading_regions_skips_atx_inside_code_fence() -> None:
    from llove.views.folding import find_heading_regions

    src = "# Real\n```\n# not a heading\n```\nbody\n"
    regions = find_heading_regions(src)
    assert len(regions) == 1
    assert regions[0].label == "Real"


def test_fold_state_toggle_and_query() -> None:
    from llove.views.folding import FoldState

    s = FoldState()
    assert not s.is_closed(5)
    s.toggle(5)
    assert s.is_closed(5)
    s.toggle(5)
    assert not s.is_closed(5)


def test_fold_state_close_all_and_open_all() -> None:
    from llove.views.folding import FoldState, find_heading_regions

    src = "# A\nbody\n## B\nb body\n# C\nc body\n"
    regions = find_heading_regions(src)
    s = FoldState()
    s.close_all(regions)
    assert all(s.is_closed(r.start_line) for r in regions)
    s.open_all()
    assert not any(s.is_closed(r.start_line) for r in regions)


def test_fold_state_close_by_kind() -> None:
    from llove.views.folding import FoldRegion, FoldState

    regions = [
        FoldRegion(kind="heading", level=1, label="A", start_line=0, end_line=2),
        FoldRegion(kind="code", level=0, label="python", start_line=4, end_line=8),
    ]
    s = FoldState()
    s.close_by_kind(regions, "heading")
    assert s.is_closed(0)
    assert not s.is_closed(4)


def test_apply_folds_replaces_closed_section_with_summary() -> None:
    from llove.views.folding import FoldState, apply_folds, find_heading_regions

    src = "# Section\nline 1\nline 2\nline 3\n"
    regions = find_heading_regions(src)
    s = FoldState()
    s.toggle(regions[0].start_line)  # close it
    rendered = apply_folds(src, regions, s)
    assert rendered.startswith("▶ # Section")
    # u4 spec: include line count (closed body length).
    assert "(3 lines)" in rendered
    # The body content must NOT appear in the rendered output when folded.
    assert "line 1" not in rendered
    assert "line 2" not in rendered


def test_apply_folds_open_section_passes_through() -> None:
    from llove.views.folding import FoldState, apply_folds, find_heading_regions

    src = "# Section\nline 1\nline 2\n"
    regions = find_heading_regions(src)
    s = FoldState()  # nothing closed
    rendered = apply_folds(src, regions, s)
    assert rendered.rstrip("\n") == src.rstrip("\n")


def test_apply_folds_nested_outer_closed_hides_inner() -> None:
    from llove.views.folding import FoldState, apply_folds, find_heading_regions

    src = "# Top\nintro\n## Sub\nsub body\n# Other\no body\n"
    regions = find_heading_regions(src)
    s = FoldState()
    top = next(r for r in regions if r.label == "Top")
    s.toggle(top.start_line)  # close Top
    rendered = apply_folds(src, regions, s)
    # Closed Top must collapse the inner heading too (single fold line).
    assert "▶ # Top" in rendered
    assert "## Sub" not in rendered
    assert "sub body" not in rendered
    # Sibling # Other must remain.
    assert "# Other" in rendered
    assert "o body" in rendered


def test_apply_folds_nested_inner_closed_keeps_outer_visible() -> None:
    from llove.views.folding import FoldState, apply_folds, find_heading_regions

    src = "# Top\nintro\n## Sub\nsub body\n# Other\no body\n"
    regions = find_heading_regions(src)
    s = FoldState()
    sub = next(r for r in regions if r.label == "Sub")
    s.toggle(sub.start_line)
    rendered = apply_folds(src, regions, s)
    assert "# Top" in rendered
    assert "intro" in rendered
    assert "▶ ## Sub" in rendered
    assert "sub body" not in rendered


def test_apply_folds_fail_closed_on_malformed_inputs() -> None:
    from llove.views.folding import FoldState, apply_folds

    # No regions, no folds — must return source unchanged.
    src = "# A\nbody\n"
    assert apply_folds(src, [], FoldState()).rstrip("\n") == src.rstrip("\n")
    # Non-string source must not raise.
    assert apply_folds(None, [], FoldState()) == ""  # type: ignore[arg-type]


def test_summary_format_matches_spec_u4() -> None:
    """u4: `▶ ## 設計詳細 (16 行)` style — include marker + heading + count."""
    from llove.views.folding import FoldState, apply_folds, find_heading_regions

    src = "## 設計詳細\n" + "".join(f"line {i}\n" for i in range(16))
    regions = find_heading_regions(src)
    s = FoldState()
    s.toggle(regions[0].start_line)
    rendered = apply_folds(src, regions, s)
    assert "▶ ## 設計詳細" in rendered
    assert "16" in rendered  # tolerate "lines"/"行"; we just check the count survives.
