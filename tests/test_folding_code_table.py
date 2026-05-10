"""F15 (u) — code-block and table fold detection.

Heading folding already works (test_folding.py). This file extends the pure
folding tier with two more kinds:

    kind="code"   — fenced ``` / ~~~ blocks. label = info-string (language).
    kind="table"  — GFM pipe tables (header row + alignment row + body).

Summary lines per (u4):
    code  → ``▶ ```python (N lines)``
    table → ``▶ | table (N rows)``
"""

from __future__ import annotations


# ----------------------------------------------------------------------
# find_code_block_regions
# ----------------------------------------------------------------------


def test_code_block_single_python_fence() -> None:
    from llove.views.folding import find_code_block_regions

    src = "intro\n```python\nprint(1)\nprint(2)\n```\nouter\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    r = regions[0]
    assert r.kind == "code"
    assert r.label == "python"
    assert r.start_line == 1  # the ```python line
    assert r.end_line == 4    # the closing ``` line


def test_code_block_no_lang_label_defaults_to_code() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```\nplain\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].label == "code"


def test_code_block_tilde_fence_supported() -> None:
    from llove.views.folding import find_code_block_regions

    src = "~~~rust\nfn main() {}\n~~~\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 1
    assert regions[0].label == "rust"


def test_code_block_unclosed_fence_returns_empty() -> None:
    """Fail-closed: a dangling fence must not produce a phantom region."""
    from llove.views.folding import find_code_block_regions

    src = "```python\nprint(1)\n"  # no closing fence
    assert find_code_block_regions(src) == []


def test_code_block_multiple_fences() -> None:
    from llove.views.folding import find_code_block_regions

    src = "```py\na\n```\ntext\n```js\nb\n```\n"
    regions = find_code_block_regions(src)
    assert len(regions) == 2
    labels = [r.label for r in regions]
    assert labels == ["py", "js"]


# ----------------------------------------------------------------------
# find_table_regions
# ----------------------------------------------------------------------


def test_table_basic() -> None:
    from llove.views.folding import find_table_regions

    src = (
        "intro\n"
        "| col1 | col2 |\n"
        "|------|------|\n"
        "| a    | b    |\n"
        "| c    | d    |\n"
        "after\n"
    )
    regions = find_table_regions(src)
    assert len(regions) == 1
    r = regions[0]
    assert r.kind == "table"
    assert r.start_line == 1
    assert r.end_line == 4


def test_table_label_carries_column_count() -> None:
    from llove.views.folding import find_table_regions

    src = "| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n"
    regions = find_table_regions(src)
    assert len(regions) == 1
    # We don't pin the exact wording, just that the column count survives.
    assert "3" in regions[0].label


def test_table_requires_alignment_row() -> None:
    """A pipe row without the dashed separator is not a table."""
    from llove.views.folding import find_table_regions

    src = "| a | b |\n| 1 | 2 |\n"  # missing |---|---|
    assert find_table_regions(src) == []


def test_table_inside_code_fence_ignored() -> None:
    from llove.views.folding import find_table_regions

    src = (
        "```\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
        "```\n"
    )
    assert find_table_regions(src) == []


# ----------------------------------------------------------------------
# apply_folds — kind-aware summary lines
# ----------------------------------------------------------------------


def test_apply_folds_code_summary_format() -> None:
    from llove.views.folding import FoldState, apply_folds, find_code_block_regions

    src = "```python\nline a\nline b\nline c\n```\n"
    regions = find_code_block_regions(src)
    s = FoldState()
    s.toggle(regions[0].start_line)
    rendered = apply_folds(src, regions, s)
    # Spec u4: closed code fold = ``` plus language plus line count.
    assert "▶" in rendered
    assert "python" in rendered
    assert "```" in rendered
    # The body must vanish.
    assert "line a" not in rendered
    assert "line b" not in rendered


def test_apply_folds_table_summary_format() -> None:
    from llove.views.folding import FoldState, apply_folds, find_table_regions

    src = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n"
    regions = find_table_regions(src)
    s = FoldState()
    s.toggle(regions[0].start_line)
    rendered = apply_folds(src, regions, s)
    assert "▶" in rendered
    assert "table" in rendered.lower()
    # Body rows hidden.
    assert "| 1 |" not in rendered
    assert "| 3 |" not in rendered


def test_apply_folds_mixed_kinds_independent() -> None:
    """Closing a code fold must not affect a sibling table fold."""
    from llove.views.folding import FoldState, apply_folds, find_code_block_regions, find_table_regions

    src = (
        "```py\nx = 1\n```\n"
        "intro\n"
        "| a | b |\n"
        "|---|---|\n"
        "| 1 | 2 |\n"
    )
    code = find_code_block_regions(src)
    table = find_table_regions(src)
    regions = code + table
    s = FoldState()
    s.toggle(code[0].start_line)  # close only the code block
    rendered = apply_folds(src, regions, s)
    assert "x = 1" not in rendered  # code hidden
    assert "| 1 | 2 |" in rendered  # table still visible


def test_apply_folds_close_by_kind_code_only() -> None:
    from llove.views.folding import FoldState, apply_folds, find_code_block_regions, find_heading_regions

    src = "# A\nbody A\n```py\nx = 1\n```\n# B\n"
    regions = find_heading_regions(src) + find_code_block_regions(src)
    s = FoldState()
    s.close_by_kind(regions, "code")
    rendered = apply_folds(src, regions, s)
    assert "x = 1" not in rendered
    assert "body A" in rendered  # heading is open
    assert "# B" in rendered
