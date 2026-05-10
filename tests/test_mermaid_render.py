"""F15 (t3) — Mermaid → SVG → ターミナル画像チェイン.

`kind="mermaid"` の fold ブロックを既存の image renderer chain
(chafa / viu / timg / kitty) に流すための薄い shim。
mmdc / 画像ツールが両方揃えば argv を返し、片方でも欠ければ ASCII
フォールバック文字列で返すように設計する。

設計方針 (CLAUDE.md `feedback_dev_rules`):

- Pure 関数 + 依存性注入: subprocess 実行 / which 検出はテストから差し替え可能
- Fail-closed: mmdc の異常終了・出力ファイル欠損は ``None`` で返す
- ASCII フォールバックは描画パイプラインを 1 本に保つために必須
- I/O はテンポラリ書き込みのみ。元 mermaid source を改変しない
"""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 検出系
# ---------------------------------------------------------------------------


def test_mmdc_available_returns_false_when_not_on_path(monkeypatch) -> None:
    from llove.views import mermaid_render

    monkeypatch.setattr(mermaid_render.shutil, "which", lambda name: None)
    assert mermaid_render.mmdc_available() is False


def test_mmdc_available_returns_true_when_shutil_finds_it(monkeypatch) -> None:
    from llove.views import mermaid_render

    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/mmdc" if name == "mmdc" else None

    monkeypatch.setattr(mermaid_render.shutil, "which", fake_which)
    assert mermaid_render.mmdc_available() is True


def test_find_image_tool_returns_first_available(monkeypatch) -> None:
    """Image chain helper delegates to llove.browser.external."""
    from llove.browser.external import ExternalTool
    from llove.views import mermaid_render

    fake = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )
    monkeypatch.setattr(mermaid_render, "available_tools", lambda scheme: [fake])
    tool = mermaid_render.find_image_tool()
    assert tool is fake


def test_find_image_tool_returns_none_when_no_chain(monkeypatch) -> None:
    from llove.views import mermaid_render

    monkeypatch.setattr(mermaid_render, "available_tools", lambda scheme: [])
    assert mermaid_render.find_image_tool() is None


# ---------------------------------------------------------------------------
# render_mermaid_to_svg — mmdc 呼び出し
# ---------------------------------------------------------------------------


def test_render_to_svg_returns_none_when_mmdc_path_missing(tmp_path: Path) -> None:
    from llove.views import mermaid_render

    out = tmp_path / "diagram.svg"
    result = mermaid_render.render_mermaid_to_svg(
        "flowchart LR\nA --> B\n", out, mmdc_path=None
    )
    assert result is None
    assert not out.exists()


def test_render_to_svg_invokes_mmdc_with_correct_argv(tmp_path: Path) -> None:
    """mmdc は `-i input.mmd -o output.svg` で呼ばれること。"""
    from llove.views import mermaid_render

    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        # Simulate successful svg write
        Path(argv[argv.index("-o") + 1]).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>',
            encoding="utf-8",
        )
        return 0

    out = tmp_path / "diagram.svg"
    result = mermaid_render.render_mermaid_to_svg(
        "flowchart LR\nA --> B\n",
        out,
        mmdc_path="/usr/local/bin/mmdc",
        runner=fake_runner,
    )

    assert result == out
    assert out.exists()
    argv = captured["argv"]
    assert argv[0] == "/usr/local/bin/mmdc"
    # -i and -o flags both present
    assert "-i" in argv
    assert "-o" in argv
    # Output target matches our requested path
    assert argv[argv.index("-o") + 1] == str(out)


def test_render_to_svg_returns_none_when_mmdc_fails(tmp_path: Path) -> None:
    from llove.views import mermaid_render

    out = tmp_path / "diagram.svg"
    result = mermaid_render.render_mermaid_to_svg(
        "garbage source",
        out,
        mmdc_path="/usr/local/bin/mmdc",
        runner=lambda argv: 1,  # non-zero exit
    )
    assert result is None


def test_render_to_svg_returns_none_when_output_missing_after_success(
    tmp_path: Path,
) -> None:
    """mmdc が exit-0 でも出力ファイルが無ければ失敗扱い (fail-closed)."""
    from llove.views import mermaid_render

    out = tmp_path / "diagram.svg"
    result = mermaid_render.render_mermaid_to_svg(
        "flowchart LR\nA --> B\n",
        out,
        mmdc_path="/usr/local/bin/mmdc",
        runner=lambda argv: 0,  # claims success but writes nothing
    )
    assert result is None


def test_render_to_svg_runner_exception_is_swallowed(tmp_path: Path) -> None:
    """subprocess の OSError 等で UI が落ちないこと."""
    from llove.views import mermaid_render

    def explode(argv: list[str]) -> int:
        raise OSError("permission denied")

    out = tmp_path / "diagram.svg"
    result = mermaid_render.render_mermaid_to_svg(
        "flowchart LR\n",
        out,
        mmdc_path="/usr/local/bin/mmdc",
        runner=explode,
    )
    assert result is None


# ---------------------------------------------------------------------------
# ASCII fallback
# ---------------------------------------------------------------------------


def test_ascii_fallback_includes_source_and_marker() -> None:
    from llove.views import mermaid_render

    text = mermaid_render.ascii_fallback("flowchart LR\nA --> B\n")
    assert "flowchart LR" in text
    assert "A --> B" in text
    # Visual marker so the user can tell it's a diagram block, not plain text
    assert "mermaid" in text.lower()


def test_ascii_fallback_is_safe_for_empty_source() -> None:
    from llove.views import mermaid_render

    text = mermaid_render.ascii_fallback("")
    assert isinstance(text, str)
    assert "mermaid" in text.lower()


# ---------------------------------------------------------------------------
# render_mermaid — 統合
# ---------------------------------------------------------------------------


def test_render_mermaid_returns_image_when_both_tools_present(
    tmp_path: Path,
) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import mermaid_render

    image_tool = ExternalTool(
        name="chafa",
        scheme="image",
        args_template=["--", "{path}"],
        priority=10,
    )

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_text("<svg/>", encoding="utf-8")
        return 0

    result = mermaid_render.render_mermaid(
        "flowchart LR\nA --> B\n",
        output_dir=tmp_path,
        mmdc_path="/usr/local/bin/mmdc",
        image_tool=image_tool,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv  # populated
    assert result.argv[0] == "chafa"
    assert result.svg_path is not None
    assert result.svg_path.exists()


def test_render_mermaid_falls_back_to_ascii_without_mmdc(
    tmp_path: Path,
) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import mermaid_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    result = mermaid_render.render_mermaid(
        "flowchart LR\nA --> B\n",
        output_dir=tmp_path,
        mmdc_path=None,
        image_tool=image_tool,
    )

    assert result.kind == "ascii"
    assert "A --> B" in result.ascii_text
    assert result.argv == ()


def test_render_mermaid_falls_back_to_ascii_without_image_tool(
    tmp_path: Path,
) -> None:
    from llove.views import mermaid_render

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_text("<svg/>", encoding="utf-8")
        return 0

    result = mermaid_render.render_mermaid(
        "flowchart LR\nA --> B\n",
        output_dir=tmp_path,
        mmdc_path="/usr/local/bin/mmdc",
        image_tool=None,
        runner=fake_runner,
    )

    assert result.kind == "ascii"
    assert "A --> B" in result.ascii_text


def test_render_mermaid_falls_back_when_mmdc_fails(tmp_path: Path) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import mermaid_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    result = mermaid_render.render_mermaid(
        "broken",
        output_dir=tmp_path,
        mmdc_path="/usr/local/bin/mmdc",
        image_tool=image_tool,
        runner=lambda argv: 2,
    )

    assert result.kind == "ascii"


def test_render_mermaid_auto_detects_when_args_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mmdc_path / image_tool が明示されない場合は which / catalog から自動検出."""
    from llove.browser.external import ExternalTool
    from llove.views import mermaid_render

    fake_image = ExternalTool(
        name="viu", scheme="image", args_template=["--", "{path}"], priority=20
    )

    monkeypatch.setattr(
        mermaid_render.shutil,
        "which",
        lambda name: "/opt/mmdc" if name == "mmdc" else None,
    )
    monkeypatch.setattr(
        mermaid_render, "available_tools", lambda scheme: [fake_image]
    )

    def fake_runner(argv: list[str]) -> int:
        Path(argv[argv.index("-o") + 1]).write_text("<svg/>", encoding="utf-8")
        return 0

    result = mermaid_render.render_mermaid(
        "flowchart LR\nA --> B\n",
        output_dir=tmp_path,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv[0] == "viu"
