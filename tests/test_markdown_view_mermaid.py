"""F15 (t3) — MarkdownView と mermaid_render の統合.

`folding.find_code_block_regions` が `kind="mermaid"` で識別したフェンスを
MarkdownView 描画時に **自動展開** する仕組みを足す。

統合の柱:
- **opt-in**: 既存呼び出し側を壊さないため、`mermaid_render=False` がデフォルト。
  True にしたときだけ展開ロジックが走る。
- **ASCII 経路**: mmdc / 画像ツール未検出時は ``ascii_fallback`` 文字列を
  `last_render` に差し込む (Textual ペイン内に納まる)。
- **image 経路**: 画像化が成功 (kind="image") した場合は本文に「画像で
  別レンダリング中」マーカーを残し、`mermaid_image_callback` に
  `MermaidRender` を渡して subprocess 起動はホスト側責務とする。
- **fail-closed**: render_mermaid が予期せず raise しても view は落ちない。
"""

from __future__ import annotations

from pathlib import Path

from llove.events import Event, EventKind


def _narration(text: str) -> Event:
    return Event(kind=EventKind.NARRATION, payload={"text": text})


# ---------------------------------------------------------------------------
# opt-in / 既存挙動の非破壊
# ---------------------------------------------------------------------------


def test_mermaid_render_disabled_by_default(tmp_path: Path) -> None:
    """デフォルトでは展開ロジックが走らず、source はそのまま見える."""
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView()
    src = "intro\n```mermaid\nflowchart LR\nA --> B\n```\n"
    v.feed(_narration(src))
    # rasterised snapshot に mermaid source 行が残ること
    assert "flowchart LR" in v.last_render
    assert "A --> B" in v.last_render


def test_normal_code_block_is_never_expanded() -> None:
    """通常 ``` の code フェンスは mermaid_render=True でも触らない."""
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(diagram_render=True)
    src = "intro\n```python\nprint(1)\n```\n"
    v.feed(_narration(src))
    assert "print(1)" in v.last_render


# ---------------------------------------------------------------------------
# ASCII 経路 — ツール未検出
# ---------------------------------------------------------------------------


def test_mermaid_ascii_fallback_when_tools_missing(tmp_path: Path) -> None:
    """mmdc / 画像ツールが揃わないと ASCII フォールバック文字列が描画に入る."""
    from llove.views import mermaid_render as mr
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={
            "mermaid": lambda src, out: mr.MermaidRender(
                kind="ascii", ascii_text=mr.ascii_fallback(src)
            )
        },
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```mermaid\nflowchart LR\nA --> B\n```\n"))
    # マーカー行 + 元 source が描画に乗ること
    assert "ASCII fallback" in v.last_render
    assert "A --> B" in v.last_render


def test_mermaid_render_handles_multiple_blocks(tmp_path: Path) -> None:
    """ドキュメント内に mermaid フェンスが複数あっても全部展開される."""
    from llove.views import mermaid_render as mr
    from llove.views.markdown_view import MarkdownView

    captured: list[str] = []

    def renderer(src: str, out: Path) -> mr.MermaidRender:
        captured.append(src)
        return mr.MermaidRender(kind="ascii", ascii_text=mr.ascii_fallback(src))

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"mermaid": renderer},
        diagram_cache_dir=tmp_path,
    )
    src = (
        "first\n"
        "```mermaid\nflowchart LR\nA --> B\n```\n"
        "between\n"
        "```mermaid\nsequenceDiagram\nAlice->>Bob: hi\n```\n"
        "end\n"
    )
    v.feed(_narration(src))
    # 2 つの mermaid 領域が両方 renderer に流れたこと
    assert len(captured) == 2
    assert "A --> B" in captured[0]
    assert "Alice->>Bob" in captured[1]


# ---------------------------------------------------------------------------
# image 経路 — callback 経由のホスト連携
# ---------------------------------------------------------------------------


def test_mermaid_image_callback_invoked_on_image_render(tmp_path: Path) -> None:
    """kind="image" の MermaidRender が callback に渡されること."""
    from llove.views import mermaid_render as mr
    from llove.views.markdown_view import MarkdownView

    callback_calls: list[mr.MermaidRender] = []

    def fake_renderer(src: str, out: Path) -> mr.MermaidRender:
        svg = out / "diagram.svg"
        out.mkdir(parents=True, exist_ok=True)
        svg.write_text("<svg/>", encoding="utf-8")
        return mr.MermaidRender(
            kind="image",
            argv=("chafa", "--", str(svg)),
            svg_path=svg,
        )

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"mermaid": fake_renderer},
        diagram_image_callback=callback_calls.append,
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```mermaid\nflowchart LR\nA --> B\n```\n"))

    # callback が 1 回呼ばれて MermaidRender (image) を受けたこと
    assert len(callback_calls) == 1
    assert callback_calls[0].kind == "image"
    assert callback_calls[0].argv[0] == "chafa"
    # 本文には「画像でレンダリング中」マーカーが入る (元 source は消える)
    assert "A --> B" not in v.last_render
    assert "mermaid" in v.last_render.lower()


def test_mermaid_callback_not_invoked_for_ascii(tmp_path: Path) -> None:
    """ASCII 経路では callback は呼ばれない (subprocess 起動が不要なため)."""
    from llove.views import mermaid_render as mr
    from llove.views.markdown_view import MarkdownView

    calls: list[mr.MermaidRender] = []

    def renderer(src: str, out: Path) -> mr.MermaidRender:
        return mr.MermaidRender(kind="ascii", ascii_text=mr.ascii_fallback(src))

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"mermaid": renderer},
        diagram_image_callback=calls.append,
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```mermaid\nflowchart LR\n```\n"))
    assert calls == []


# ---------------------------------------------------------------------------
# fail-closed
# ---------------------------------------------------------------------------


def test_renderer_exception_falls_back_to_raw_source(tmp_path: Path) -> None:
    """renderer が raise しても view は落ちず、元 source が見えること."""
    from llove.views.markdown_view import MarkdownView

    def bad(src: str, out: Path):
        raise RuntimeError("renderer broke")

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"mermaid": bad},
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```mermaid\nflowchart LR\nA --> B\n```\n"))
    # 例外で view が壊れず、最低限元 source は見えること
    assert v.last_render
    assert "A --> B" in v.last_render


def test_image_callback_exception_does_not_break_view(tmp_path: Path) -> None:
    """callback の例外も view を壊さない."""
    from llove.views import mermaid_render as mr
    from llove.views.markdown_view import MarkdownView

    def renderer(src: str, out: Path) -> mr.MermaidRender:
        out.mkdir(parents=True, exist_ok=True)
        svg = out / "d.svg"
        svg.write_text("<svg/>", encoding="utf-8")
        return mr.MermaidRender(kind="image", argv=("x",), svg_path=svg)

    def bad_callback(r: mr.MermaidRender) -> None:
        raise RuntimeError("dispatch broke")

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"mermaid": renderer},
        diagram_image_callback=bad_callback,
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```mermaid\nflowchart LR\n```\n"))
    assert v.last_render  # didn't blow up


# ---------------------------------------------------------------------------
# fold との互換性
# ---------------------------------------------------------------------------


def test_mermaid_expansion_keeps_fold_state_intact(tmp_path: Path) -> None:
    """mermaid 展開は fold の region 計算 (元 source ベース) を壊さない."""
    from llove.views import mermaid_render as mr
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(
        mermaid_render=True,
        mermaid_renderer=lambda s, o: mr.MermaidRender(
            kind="ascii", ascii_text=mr.ascii_fallback(s)
        ),
        mermaid_cache_dir=tmp_path,
    )
    v.feed(_narration("```mermaid\nflowchart LR\nA --> B\n```\n"))
    # fold_regions は元 source ベースなので mermaid kind が見える
    kinds = {r.kind for r in v.fold_regions()}
    assert "mermaid" in kinds
