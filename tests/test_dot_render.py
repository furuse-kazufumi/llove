"""F15 (t2/t3) — Graphviz dot → SVG → ターミナル画像チェイン.

`mermaid_render` / `svg_render` / `plantuml_render` と同じ哲学
(pure 関数 + 依存性注入 + fail-closed + ASCII フォールバック)。dot / chafa
等が未インストールの CI でもフルテストできる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 検出系
# ---------------------------------------------------------------------------


def test_dot_available_returns_false_when_not_on_path(monkeypatch) -> None:
    from llove.views import dot_render

    monkeypatch.setattr(dot_render.shutil, "which", lambda name: None)
    assert dot_render.dot_available() is False


def test_dot_available_returns_true_when_shutil_finds_it(monkeypatch) -> None:
    from llove.views import dot_render

    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/dot" if name == "dot" else None

    monkeypatch.setattr(dot_render.shutil, "which", fake_which)
    assert dot_render.dot_available() is True


def test_find_image_tool_returns_first_available(monkeypatch) -> None:
    """Image chain helper delegates to llove.browser.external."""
    from llove.browser.external import ExternalTool
    from llove.views import dot_render

    fake = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )
    monkeypatch.setattr(dot_render, "available_tools", lambda scheme: [fake])
    tool = dot_render.find_image_tool()
    assert tool is fake


def test_find_image_tool_returns_none_when_no_chain(monkeypatch) -> None:
    from llove.views import dot_render

    monkeypatch.setattr(dot_render, "available_tools", lambda scheme: [])
    assert dot_render.find_image_tool() is None


# ---------------------------------------------------------------------------
# render_dot_to_svg — dot 呼び出し
# ---------------------------------------------------------------------------


def test_render_to_svg_returns_none_when_dot_path_missing(tmp_path: Path) -> None:
    from llove.views import dot_render

    out = tmp_path / "diagram.svg"
    result = dot_render.render_dot_to_svg(
        "digraph G { A -> B }", out, dot_path=None
    )
    assert result is None
    assert not out.exists()


def test_render_to_svg_invokes_dot_with_correct_argv(tmp_path: Path) -> None:
    """dot は ``-Tsvg -o output.svg input.dot`` で呼ばれること。"""
    from llove.views import dot_render

    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        Path(argv[argv.index("-o") + 1]).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>',
            encoding="utf-8",
        )
        return 0

    out = tmp_path / "diagram.svg"
    result = dot_render.render_dot_to_svg(
        "digraph G { A -> B }",
        out,
        dot_path="/usr/local/bin/dot",
        runner=fake_runner,
    )

    assert result == out
    assert out.exists()
    argv = captured["argv"]
    assert argv[0] == "/usr/local/bin/dot"
    assert "-Tsvg" in argv
    assert "-o" in argv
    assert argv[argv.index("-o") + 1] == str(out)
    # 入力 .dot は output と同じステムで temp 書き出しされる
    assert argv[-1].endswith("diagram.dot")


def test_render_to_svg_returns_none_when_dot_fails(tmp_path: Path) -> None:
    from llove.views import dot_render

    out = tmp_path / "diagram.svg"
    result = dot_render.render_dot_to_svg(
        "garbage source",
        out,
        dot_path="/usr/local/bin/dot",
        runner=lambda argv: 1,
    )
    assert result is None


def test_render_to_svg_returns_none_when_output_missing_after_success(
    tmp_path: Path,
) -> None:
    """dot が exit-0 でも出力 SVG が無ければ失敗扱い (fail-closed)."""
    from llove.views import dot_render

    out = tmp_path / "diagram.svg"
    result = dot_render.render_dot_to_svg(
        "digraph G { A -> B }",
        out,
        dot_path="/usr/local/bin/dot",
        runner=lambda argv: 0,
    )
    assert result is None


def test_render_to_svg_runner_exception_is_swallowed(tmp_path: Path) -> None:
    """subprocess の OSError 等で UI が落ちないこと."""
    from llove.views import dot_render

    def explode(argv: list[str]) -> int:
        raise OSError("permission denied")

    out = tmp_path / "diagram.svg"
    result = dot_render.render_dot_to_svg(
        "digraph G { A -> B }",
        out,
        dot_path="/usr/local/bin/dot",
        runner=explode,
    )
    assert result is None


# ---------------------------------------------------------------------------
# ASCII fallback
# ---------------------------------------------------------------------------


def test_ascii_fallback_includes_source_and_marker() -> None:
    from llove.views import dot_render

    text = dot_render.ascii_fallback("digraph G { A -> B }")
    assert "digraph G" in text
    assert "A -> B" in text
    assert "dot" in text.lower()


def test_ascii_fallback_is_safe_for_empty_source() -> None:
    from llove.views import dot_render

    text = dot_render.ascii_fallback("")
    assert isinstance(text, str)
    assert "dot" in text.lower()


# ---------------------------------------------------------------------------
# render_dot — 統合
# ---------------------------------------------------------------------------


def test_render_dot_returns_image_when_both_tools_present(
    tmp_path: Path,
) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import dot_render

    image_tool = ExternalTool(
        name="chafa",
        scheme="image",
        args_template=["--", "{path}"],
        priority=10,
    )

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_text("<svg/>", encoding="utf-8")
        return 0

    result = dot_render.render_dot(
        "digraph G { A -> B }",
        output_dir=tmp_path,
        dot_path="/usr/local/bin/dot",
        image_tool=image_tool,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv
    assert result.argv[0] == "chafa"
    assert result.svg_path is not None
    assert result.svg_path.exists()


def test_render_dot_falls_back_to_ascii_without_dot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import dot_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    monkeypatch.setattr(dot_render.shutil, "which", lambda name: None)

    result = dot_render.render_dot(
        "digraph G { A -> B }",
        output_dir=tmp_path,
        dot_path=None,
        image_tool=image_tool,
    )

    assert result.kind == "ascii"
    assert "A -> B" in result.ascii_text
    assert result.argv == ()


def test_render_dot_falls_back_to_ascii_without_image_tool(
    tmp_path: Path,
) -> None:
    from llove.views import dot_render

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_text("<svg/>", encoding="utf-8")
        return 0

    result = dot_render.render_dot(
        "digraph G { A -> B }",
        output_dir=tmp_path,
        dot_path="/usr/local/bin/dot",
        image_tool=None,
        runner=fake_runner,
    )

    assert result.kind == "ascii"
    assert "A -> B" in result.ascii_text


def test_render_dot_falls_back_when_dot_fails(tmp_path: Path) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import dot_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    result = dot_render.render_dot(
        "broken",
        output_dir=tmp_path,
        dot_path="/usr/local/bin/dot",
        image_tool=image_tool,
        runner=lambda argv: 2,
    )

    assert result.kind == "ascii"


def test_render_dot_auto_detects_when_args_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """dot_path / image_tool 省略時は which / catalog から自動検出."""
    from llove.browser.external import ExternalTool
    from llove.views import dot_render

    fake_image = ExternalTool(
        name="viu", scheme="image", args_template=["--", "{path}"], priority=20
    )

    monkeypatch.setattr(
        dot_render.shutil,
        "which",
        lambda name: "/opt/dot" if name == "dot" else None,
    )
    monkeypatch.setattr(dot_render, "available_tools", lambda scheme: [fake_image])

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_text("<svg/>", encoding="utf-8")
        return 0

    result = dot_render.render_dot(
        "digraph G { A -> B }",
        output_dir=tmp_path,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv[0] == "viu"
