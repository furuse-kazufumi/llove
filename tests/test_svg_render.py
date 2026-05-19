"""F15 (t2) — SVG → PNG → ターミナル画像チェイン.

mermaid_render と並行する構造。SVG XML 文字列を ``rsvg-convert`` で PNG に
変換し、既存 image renderer chain (chafa / viu / timg / kitty / wezterm) に
流す。両ツールが揃わないか subprocess が失敗した場合は、ASCII フォール
バックに降りる (fail-closed)。

設計方針:
- Pure 関数 + 依存性注入 (rsvg_path / image_tool / runner)
- subprocess は list-based argv のみ (shell=True 禁止)
- 入力 SVG はテンポラリ ``.svg`` ファイルに書き出してから渡す
"""

from __future__ import annotations

from pathlib import Path

import pytest  # noqa: F401

# ---------------------------------------------------------------------------
# 検出系
# ---------------------------------------------------------------------------


def test_rsvg_convert_available_returns_false_when_not_on_path(monkeypatch) -> None:
    from llove.views import svg_render

    monkeypatch.setattr(svg_render.shutil, "which", lambda name: None)
    assert svg_render.rsvg_convert_available() is False


def test_rsvg_convert_available_returns_true_when_shutil_finds_it(
    monkeypatch,
) -> None:
    from llove.views import svg_render

    def fake_which(name: str) -> str | None:
        return "/usr/bin/rsvg-convert" if name == "rsvg-convert" else None

    monkeypatch.setattr(svg_render.shutil, "which", fake_which)
    assert svg_render.rsvg_convert_available() is True


# ---------------------------------------------------------------------------
# render_svg_to_png — rsvg-convert 呼び出し
# ---------------------------------------------------------------------------


def test_render_to_png_returns_none_when_rsvg_path_missing(tmp_path: Path) -> None:
    from llove.views import svg_render

    out = tmp_path / "diagram.png"
    result = svg_render.render_svg_to_png(
        "<svg xmlns='http://www.w3.org/2000/svg'/>", out, rsvg_path=None
    )
    assert result is None
    assert not out.exists()


def test_render_to_png_invokes_rsvg_with_correct_argv(tmp_path: Path) -> None:
    """rsvg-convert は `-o output.png input.svg` で呼ばれること."""
    from llove.views import svg_render

    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        # Simulate successful PNG write
        Path(argv[argv.index("-o") + 1]).write_bytes(b"\x89PNG\r\n")
        return 0

    out = tmp_path / "diagram.png"
    result = svg_render.render_svg_to_png(
        "<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>",
        out,
        rsvg_path="/usr/bin/rsvg-convert",
        runner=fake_runner,
    )

    assert result == out
    assert out.exists()
    argv = captured["argv"]
    assert argv[0] == "/usr/bin/rsvg-convert"
    assert "-o" in argv
    assert argv[argv.index("-o") + 1] == str(out)
    # 入力 svg が argv のどこかに入っていること
    assert any(a.endswith(".svg") for a in argv)


def test_render_to_png_returns_none_when_rsvg_fails(tmp_path: Path) -> None:
    from llove.views import svg_render

    out = tmp_path / "diagram.png"
    result = svg_render.render_svg_to_png(
        "<svg></svg>",
        out,
        rsvg_path="/usr/bin/rsvg-convert",
        runner=lambda argv: 1,
    )
    assert result is None


def test_render_to_png_returns_none_when_output_missing_after_success(
    tmp_path: Path,
) -> None:
    """rsvg が exit-0 でも出力ファイルが無ければ失敗扱い (fail-closed)."""
    from llove.views import svg_render

    out = tmp_path / "diagram.png"
    result = svg_render.render_svg_to_png(
        "<svg></svg>",
        out,
        rsvg_path="/usr/bin/rsvg-convert",
        runner=lambda argv: 0,  # claims success but writes nothing
    )
    assert result is None


def test_render_to_png_runner_exception_is_swallowed(tmp_path: Path) -> None:
    from llove.views import svg_render

    def explode(argv: list[str]) -> int:
        raise OSError("permission denied")

    out = tmp_path / "diagram.png"
    result = svg_render.render_svg_to_png(
        "<svg></svg>",
        out,
        rsvg_path="/usr/bin/rsvg-convert",
        runner=explode,
    )
    assert result is None


# ---------------------------------------------------------------------------
# ASCII fallback
# ---------------------------------------------------------------------------


def test_ascii_fallback_includes_marker_and_source_excerpt() -> None:
    from llove.views import svg_render

    text = svg_render.ascii_fallback_for_svg(
        "<svg xmlns='http://www.w3.org/2000/svg'><rect width='10'/></svg>"
    )
    # マーカーで「画像レンダ不能」と分かること
    assert "svg" in text.lower()
    # XML を全文流すと爆発するので、要約行 or 抜粋で十分
    assert isinstance(text, str)
    assert text  # 空文字でない


def test_ascii_fallback_safe_for_empty_source() -> None:
    from llove.views import svg_render

    text = svg_render.ascii_fallback_for_svg("")
    assert isinstance(text, str)
    assert "svg" in text.lower()


# ---------------------------------------------------------------------------
# render_svg — 統合
# ---------------------------------------------------------------------------


def test_render_svg_returns_image_when_both_tools_present(tmp_path: Path) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import svg_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_bytes(b"\x89PNG\r\n")
        return 0

    result = svg_render.render_svg(
        "<svg xmlns='http://www.w3.org/2000/svg'/>",
        output_dir=tmp_path,
        rsvg_path="/usr/bin/rsvg-convert",
        image_tool=image_tool,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv
    assert result.argv[0] == "chafa"
    assert result.png_path is not None
    assert result.png_path.exists()


def test_render_svg_falls_back_to_ascii_without_rsvg(tmp_path: Path) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import svg_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    result = svg_render.render_svg(
        "<svg/>",
        output_dir=tmp_path,
        rsvg_path=None,
        image_tool=image_tool,
    )

    assert result.kind == "ascii"
    assert "svg" in result.ascii_text.lower()
    assert result.argv == ()


def test_render_svg_falls_back_to_ascii_without_image_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from llove.views import svg_render

    # image_tool=None でも find_image_tool() が環境上の chafa 等を拾うため,
    # PATH 検索を抑止して「画像ツール一切なし」を再現する.
    monkeypatch.setattr(svg_render.shutil, "which", lambda name: None)

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_bytes(b"\x89PNG\r\n")
        return 0

    result = svg_render.render_svg(
        "<svg/>",
        output_dir=tmp_path,
        rsvg_path="/usr/bin/rsvg-convert",
        image_tool=None,
        runner=fake_runner,
    )

    assert result.kind == "ascii"


def test_render_svg_falls_back_when_rsvg_fails(tmp_path: Path) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import svg_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    result = svg_render.render_svg(
        "<svg/>",
        output_dir=tmp_path,
        rsvg_path="/usr/bin/rsvg-convert",
        image_tool=image_tool,
        runner=lambda argv: 2,
    )
    assert result.kind == "ascii"


def test_render_svg_auto_detects_when_args_omitted(
    tmp_path: Path, monkeypatch
) -> None:
    """rsvg_path / image_tool が省略されたら which / catalog から自動検出."""
    from llove.browser.external import ExternalTool
    from llove.views import svg_render

    fake_image = ExternalTool(
        name="viu", scheme="image", args_template=["--", "{path}"], priority=20
    )

    monkeypatch.setattr(
        svg_render.shutil,
        "which",
        lambda name: "/opt/rsvg-convert" if name == "rsvg-convert" else None,
    )
    monkeypatch.setattr(
        svg_render, "available_tools", lambda scheme: [fake_image]
    )

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_bytes(b"\x89PNG\r\n")
        return 0

    result = svg_render.render_svg(
        "<svg/>",
        output_dir=tmp_path,
        runner=fake_runner,
    )
    assert result.kind == "image"
    assert result.argv[0] == "viu"
