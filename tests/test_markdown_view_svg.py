"""F15 (t2) — MarkdownView の SVG 自動展開 (mermaid と汎化共存).

`_expand_diagram_blocks_in` は mermaid + svg を同じ経路で処理する。
本ファイルは svg 側のパスと、mermaid + svg が同一ドキュメント内で
共存したときに正しく分岐することを検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llove.events import Event, EventKind
from llove.views import mermaid_render as mr
from llove.views import svg_render as sv


def _narration(text: str) -> Event:
    return Event(kind=EventKind.NARRATION, payload={"text": text})


# ---------------------------------------------------------------------------
# SVG 単独
# ---------------------------------------------------------------------------


def test_svg_block_is_expanded_via_dedicated_renderer(tmp_path: Path) -> None:
    """svg フェンスは ``diagram_renderers["svg"]`` に流れる."""
    from llove.views.markdown_view import MarkdownView

    captured: list[str] = []

    def svg_renderer(src: str, out: Path) -> sv.SVGRender:
        captured.append(src)
        return sv.SVGRender(
            kind="ascii", ascii_text=sv.ascii_fallback_for_svg(src)
        )

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"svg": svg_renderer},
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```svg\n<svg width='10'/>\n```\n"))
    assert len(captured) == 1
    assert "<svg width='10'/>" in captured[0]
    # ASCII fallback marker は描画に乗る
    assert "svg" in v.last_render.lower()


def test_svg_image_callback_invoked_with_svg_render(tmp_path: Path) -> None:
    from llove.views.markdown_view import MarkdownView

    callback_calls: list[sv.SVGRender] = []

    def fake(src: str, out: Path) -> sv.SVGRender:
        out.mkdir(parents=True, exist_ok=True)
        png = out / "diagram.png"
        png.write_bytes(b"\x89PNG\r\n")
        return sv.SVGRender(
            kind="image", argv=("chafa", "--", str(png)), png_path=png
        )

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={"svg": fake},
        diagram_image_callback=callback_calls.append,
        diagram_cache_dir=tmp_path,
    )
    v.feed(_narration("```svg\n<svg/>\n```\n"))
    assert len(callback_calls) == 1
    assert callback_calls[0].kind == "image"
    # marker に "svg diagram" が入る (mermaid と区別できる)
    assert "svg diagram" in v.last_render.lower()


# ---------------------------------------------------------------------------
# mermaid + svg 共存
# ---------------------------------------------------------------------------


def test_mixed_mermaid_and_svg_each_routes_to_own_renderer(
    tmp_path: Path,
) -> None:
    """同一ドキュメント内で mermaid + svg が共存しても kind 別に分岐."""
    from llove.views.markdown_view import MarkdownView

    mermaid_seen: list[str] = []
    svg_seen: list[str] = []

    def mermaid_render_fn(src: str, out: Path) -> mr.MermaidRender:
        mermaid_seen.append(src)
        return mr.MermaidRender(
            kind="ascii", ascii_text=mr.ascii_fallback(src)
        )

    def svg_render_fn(src: str, out: Path) -> sv.SVGRender:
        svg_seen.append(src)
        return sv.SVGRender(
            kind="ascii", ascii_text=sv.ascii_fallback_for_svg(src)
        )

    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={
            "mermaid": mermaid_render_fn,
            "svg": svg_render_fn,
        },
        diagram_cache_dir=tmp_path,
    )
    src = (
        "```mermaid\nflowchart LR\nA --> B\n```\n"
        "```svg\n<svg width='5'/>\n```\n"
    )
    v.feed(_narration(src))
    # 各 renderer が対応する kind だけを受け取っている
    assert len(mermaid_seen) == 1
    assert "A --> B" in mermaid_seen[0]
    assert len(svg_seen) == 1
    assert "<svg width='5'/>" in svg_seen[0]


def test_unknown_diagram_kind_is_left_intact(tmp_path: Path) -> None:
    """登録されていない kind は触らずに source がそのまま見える."""
    from llove.views.markdown_view import MarkdownView

    # mermaid しか登録しない
    v = MarkdownView(
        diagram_render=True,
        diagram_renderers={
            "mermaid": lambda s, o: mr.MermaidRender(
                kind="ascii", ascii_text=mr.ascii_fallback(s)
            )
        },
        diagram_cache_dir=tmp_path,
    )
    # svg ブロックは未登録 → 何もせず本文をそのまま残す
    v.feed(_narration("```svg\n<svg width='99'/>\n```\n"))
    assert "<svg width='99'/>" in v.last_render


# ---------------------------------------------------------------------------
# Default renderers — constructor 省略時
# ---------------------------------------------------------------------------


def test_default_renderers_cover_mermaid_and_svg(tmp_path: Path) -> None:
    """diagram_renderers を省略しても mermaid / svg 両方の既定 renderer が動く.

    既定 renderer は実際に mmdc / rsvg-convert を呼ぶが、未インストール
    環境では ASCII fallback に降りるので本文に元 source の抜粋が残る。
    """
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(diagram_render=True, diagram_cache_dir=tmp_path)
    # mermaid: ASCII fallback で元 source が残る
    v.feed(_narration("```mermaid\nflowchart LR\nA --> B\n```\n"))
    assert "A --> B" in v.last_render
    # svg: ASCII fallback で先頭抜粋が残る
    v.feed(_narration("```svg\n<svg width='42'/>\n```\n"))
    assert "<svg width='42'/>" in v.last_render
