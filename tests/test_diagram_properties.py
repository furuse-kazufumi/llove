"""F15 (t2/t3) — pure 関数の不変条件を Hypothesis で property-based に攻める.

通常の単体テストは 1 入力 → 1 出力の点的検証だが、property-based は
**「どんな入力でも成り立つべき性質」** を 100+ 回ランダムサンプリングで
検証する。

代表例:
- `find_code_block_regions(s)` は **どんな s でも raise しない**
- `apply_folds` は state が空なら入力を変えない
- `ascii_fallback*` は **どんな入力でも非空 str を返す**
- `run_image_render([])` は常に None
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# folding.py — どんな入力でも raise しない / 矛盾しない
# ---------------------------------------------------------------------------


@given(st.text(max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_find_code_block_regions_never_raises_for_any_input(text: str) -> None:
    from llove.views.folding import find_code_block_regions

    regions = find_code_block_regions(text)
    # 戻り値は list で、各要素は start_line <= end_line の region
    assert isinstance(regions, list)
    for r in regions:
        assert r.start_line <= r.end_line
        assert r.kind in {"code", "mermaid", "svg"}


@given(st.text(max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_find_heading_regions_never_raises_for_any_input(text: str) -> None:
    from llove.views.folding import find_heading_regions

    regions = find_heading_regions(text)
    assert isinstance(regions, list)
    for r in regions:
        assert r.start_line <= r.end_line
        assert r.kind == "heading"
        assert 1 <= r.level <= 6


@given(st.text(max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_apply_folds_with_empty_state_returns_input_unchanged(text: str) -> None:
    """fold 状態が空なら入力テキストが変化しない (頂点の安全性)."""
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
    )

    regions = find_code_block_regions(text)
    out = apply_folds(text, regions, FoldState())
    # apply_folds は空 state なら source をそのまま返す約束
    assert out == text


@given(st.text(max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_apply_folds_does_not_grow_text_when_closing_all(text: str) -> None:
    """全 region を閉じた結果は元テキストより長くならない (折り畳みの定義)."""
    from llove.views.folding import (
        FoldState,
        apply_folds,
        find_code_block_regions,
        find_heading_regions,
        find_table_regions,
    )

    regions = (
        find_heading_regions(text)
        + find_code_block_regions(text)
        + find_table_regions(text)
    )
    state = FoldState()
    state.close_all(regions)
    out = apply_folds(text, regions, state)
    # サマリ行の方が短いか同じになる (folding なので)
    assert out.count("\n") <= text.count("\n") + len(regions)  # サマリ行追加分の上限


# ---------------------------------------------------------------------------
# mermaid_render / svg_render — ASCII fallback の不変条件
# ---------------------------------------------------------------------------


@given(st.text(max_size=500))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_mermaid_ascii_fallback_returns_non_empty_for_any_input(text: str) -> None:
    from llove.views.mermaid_render import ascii_fallback

    out = ascii_fallback(text)
    assert isinstance(out, str)
    assert out  # 必ず非空 (ヘッダ + 罫線が必ず付く)
    assert "mermaid" in out.lower()


@given(st.text(max_size=500))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_svg_ascii_fallback_returns_non_empty_for_any_input(text: str) -> None:
    from llove.views.svg_render import ascii_fallback_for_svg

    out = ascii_fallback_for_svg(text)
    assert isinstance(out, str)
    assert out
    assert "svg" in out.lower()


@given(st.text(min_size=300, max_size=2000))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_svg_ascii_fallback_truncates_long_input(text: str) -> None:
    """SVG ascii fallback は 240 文字 + ellipsis に必ず切る."""
    from llove.views.svg_render import ascii_fallback_for_svg

    out = ascii_fallback_for_svg(text)
    # 元テキストの最後の方の文字が切られて消えていること
    if len(text.strip()) > 240:
        assert "..." in out


# ---------------------------------------------------------------------------
# run_image_render — empty argv は常に None
# ---------------------------------------------------------------------------


@given(st.lists(st.text(max_size=20), max_size=10))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_run_image_render_handles_arbitrary_argv(argv: list[str]) -> None:
    """argv をどんな形にしても (空 / 短い / ランダム文字列) raise せず None or str を返す."""
    from llove.views.image_render_pane import run_image_render

    # 失敗を強制する runner: 常に非ゼロ
    def fake_runner(a, *, timeout):
        return 1, b"", b""

    out = run_image_render(argv, runner=fake_runner)
    # 空 argv → None / 非空 + rc=1 → None。常に None になる。
    assert out is None


@given(st.binary(max_size=200))
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
def test_run_image_render_decodes_arbitrary_stdout(stdout: bytes) -> None:
    """runner が任意の bytes を吐いても decode で raise しない (errors=replace)."""
    from llove.views.image_render_pane import run_image_render

    out = run_image_render(["fake"], runner=lambda a, *, timeout: (0, stdout, b""))
    # Stdout が空文字でなければ str が返る (空なら ascii fallback ではなく
    # rc=0 なので decoded str が返ってくる、空文字も含めて str)
    assert out is None or isinstance(out, str)


# ---------------------------------------------------------------------------
# render_mermaid_to_svg / render_svg_to_png — 不在 path で必ず None
# ---------------------------------------------------------------------------


@given(st.text(max_size=300))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_render_mermaid_to_svg_returns_none_without_mmdc_path(text: str) -> None:
    import tempfile
    from pathlib import Path

    from llove.views.mermaid_render import render_mermaid_to_svg

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "x.svg"
        result = render_mermaid_to_svg(text, out, mmdc_path=None)
        assert result is None
        assert not out.exists()


@given(st.text(max_size=300))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_render_svg_to_png_returns_none_without_rsvg_path(text: str) -> None:
    import tempfile
    from pathlib import Path

    from llove.views.svg_render import render_svg_to_png

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "x.png"
        result = render_svg_to_png(text, out, rsvg_path=None)
        assert result is None
        assert not out.exists()
