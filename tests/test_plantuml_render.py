"""F15 (t2/t3) — PlantUML → SVG → ターミナル画像チェイン.

`mermaid_render` / `svg_render` と同じ哲学 (pure 関数 + 依存性注入 +
fail-closed + ASCII フォールバック) を踏襲。plantuml / chafa 等が
未インストールの CI でもフルテストできる。
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# 検出系
# ---------------------------------------------------------------------------


def test_plantuml_available_returns_false_when_not_on_path(monkeypatch) -> None:
    from llove.views import plantuml_render

    monkeypatch.setattr(plantuml_render.shutil, "which", lambda name: None)
    assert plantuml_render.plantuml_available() is False


def test_plantuml_available_returns_true_when_shutil_finds_it(monkeypatch) -> None:
    from llove.views import plantuml_render

    def fake_which(name: str) -> str | None:
        return "/usr/local/bin/plantuml" if name == "plantuml" else None

    monkeypatch.setattr(plantuml_render.shutil, "which", fake_which)
    assert plantuml_render.plantuml_available() is True


def test_find_image_tool_returns_first_available(monkeypatch) -> None:
    """Image chain helper delegates to llove.browser.external."""
    from llove.browser.external import ExternalTool
    from llove.views import plantuml_render

    fake = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )
    monkeypatch.setattr(plantuml_render, "available_tools", lambda scheme: [fake])
    tool = plantuml_render.find_image_tool()
    assert tool is fake


def test_find_image_tool_returns_none_when_no_chain(monkeypatch) -> None:
    from llove.views import plantuml_render

    monkeypatch.setattr(plantuml_render, "available_tools", lambda scheme: [])
    assert plantuml_render.find_image_tool() is None


# ---------------------------------------------------------------------------
# render_plantuml_to_svg — plantuml 呼び出し
# ---------------------------------------------------------------------------


def test_render_to_svg_returns_none_when_plantuml_path_missing(
    tmp_path: Path,
) -> None:
    from llove.views import plantuml_render

    out = tmp_path / "diagram.svg"
    result = plantuml_render.render_plantuml_to_svg(
        "@startuml\nAlice -> Bob\n@enduml\n", out, plantuml_path=None
    )
    assert result is None
    assert not out.exists()


def test_render_to_svg_invokes_plantuml_with_correct_argv(tmp_path: Path) -> None:
    """plantuml は ``-tsvg <input.puml>`` の list-based argv で呼ばれること。"""
    from llove.views import plantuml_render

    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str]) -> int:
        captured["argv"] = argv
        # plantuml 本物は同じディレクトリの <stem>.svg を作る。これを模擬。
        puml_path = Path(argv[-1])
        svg_path = puml_path.with_suffix(".svg")
        svg_path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>',
            encoding="utf-8",
        )
        return 0

    out = tmp_path / "diagram.svg"
    result = plantuml_render.render_plantuml_to_svg(
        "@startuml\nAlice -> Bob\n@enduml\n",
        out,
        plantuml_path="/usr/local/bin/plantuml",
        runner=fake_runner,
    )

    assert result == out
    assert out.exists()
    argv = captured["argv"]
    assert argv[0] == "/usr/local/bin/plantuml"
    assert "-tsvg" in argv
    # 入力 puml は output と同じステムで一時書き出しされていること
    assert argv[-1].endswith("diagram.puml")


def test_render_to_svg_returns_none_when_plantuml_fails(tmp_path: Path) -> None:
    from llove.views import plantuml_render

    out = tmp_path / "diagram.svg"
    result = plantuml_render.render_plantuml_to_svg(
        "garbage source",
        out,
        plantuml_path="/usr/local/bin/plantuml",
        runner=lambda argv: 1,  # non-zero exit
    )
    assert result is None


def test_render_to_svg_returns_none_when_output_missing_after_success(
    tmp_path: Path,
) -> None:
    """plantuml が exit-0 でも出力 SVG が無ければ失敗扱い (fail-closed)."""
    from llove.views import plantuml_render

    out = tmp_path / "diagram.svg"
    result = plantuml_render.render_plantuml_to_svg(
        "@startuml\nAlice -> Bob\n@enduml\n",
        out,
        plantuml_path="/usr/local/bin/plantuml",
        runner=lambda argv: 0,  # claims success but writes nothing
    )
    assert result is None


def test_render_to_svg_runner_exception_is_swallowed(tmp_path: Path) -> None:
    """subprocess の OSError 等で UI が落ちないこと."""
    from llove.views import plantuml_render

    def explode(argv: list[str]) -> int:
        raise OSError("permission denied")

    out = tmp_path / "diagram.svg"
    result = plantuml_render.render_plantuml_to_svg(
        "@startuml\nAlice -> Bob\n@enduml\n",
        out,
        plantuml_path="/usr/local/bin/plantuml",
        runner=explode,
    )
    assert result is None


# ---------------------------------------------------------------------------
# ASCII fallback
# ---------------------------------------------------------------------------


def test_ascii_fallback_includes_source_and_marker() -> None:
    from llove.views import plantuml_render

    text = plantuml_render.ascii_fallback("@startuml\nAlice -> Bob\n@enduml\n")
    assert "Alice -> Bob" in text
    # Visual marker so the user can tell it's a plantuml block, not plain text
    assert "plantuml" in text.lower()


def test_ascii_fallback_is_safe_for_empty_source() -> None:
    from llove.views import plantuml_render

    text = plantuml_render.ascii_fallback("")
    assert isinstance(text, str)
    assert "plantuml" in text.lower()


# ---------------------------------------------------------------------------
# render_plantuml — 統合
# ---------------------------------------------------------------------------


def test_render_plantuml_returns_image_when_both_tools_present(
    tmp_path: Path,
) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import plantuml_render

    image_tool = ExternalTool(
        name="chafa",
        scheme="image",
        args_template=["--", "{path}"],
        priority=10,
    )

    def fake_runner(argv: list[str]) -> int:
        puml_path = Path(argv[-1])
        puml_path.with_suffix(".svg").write_text("<svg/>", encoding="utf-8")
        return 0

    result = plantuml_render.render_plantuml(
        "@startuml\nAlice -> Bob\n@enduml\n",
        output_dir=tmp_path,
        plantuml_path="/usr/local/bin/plantuml",
        image_tool=image_tool,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv  # populated
    assert result.argv[0] == "chafa"
    assert result.svg_path is not None
    assert result.svg_path.exists()


def test_render_plantuml_falls_back_to_ascii_without_plantuml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import plantuml_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    # 実 dev 環境に plantuml が入っていても確実に「不在」を表現する。
    monkeypatch.setattr(plantuml_render.shutil, "which", lambda name: None)

    result = plantuml_render.render_plantuml(
        "@startuml\nAlice -> Bob\n@enduml\n",
        output_dir=tmp_path,
        plantuml_path=None,
        image_tool=image_tool,
    )

    assert result.kind == "ascii"
    assert "Alice -> Bob" in result.ascii_text
    assert result.argv == ()


def test_render_plantuml_falls_back_to_ascii_without_image_tool(
    tmp_path: Path,
) -> None:
    from llove.views import plantuml_render

    def fake_runner(argv: list[str]) -> int:
        puml_path = Path(argv[-1])
        puml_path.with_suffix(".svg").write_text("<svg/>", encoding="utf-8")
        return 0

    result = plantuml_render.render_plantuml(
        "@startuml\nAlice -> Bob\n@enduml\n",
        output_dir=tmp_path,
        plantuml_path="/usr/local/bin/plantuml",
        image_tool=None,
        runner=fake_runner,
    )

    assert result.kind == "ascii"
    assert "Alice -> Bob" in result.ascii_text


def test_render_plantuml_falls_back_when_plantuml_fails(tmp_path: Path) -> None:
    from llove.browser.external import ExternalTool
    from llove.views import plantuml_render

    image_tool = ExternalTool(
        name="chafa", scheme="image", args_template=["--", "{path}"], priority=10
    )

    result = plantuml_render.render_plantuml(
        "broken",
        output_dir=tmp_path,
        plantuml_path="/usr/local/bin/plantuml",
        image_tool=image_tool,
        runner=lambda argv: 2,
    )

    assert result.kind == "ascii"


def test_render_plantuml_auto_detects_when_args_omitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """plantuml_path / image_tool が省略時は which / catalog から自動検出."""
    from llove.browser.external import ExternalTool
    from llove.views import plantuml_render

    fake_image = ExternalTool(
        name="viu", scheme="image", args_template=["--", "{path}"], priority=20
    )

    monkeypatch.setattr(
        plantuml_render.shutil,
        "which",
        lambda name: "/opt/plantuml" if name == "plantuml" else None,
    )
    monkeypatch.setattr(
        plantuml_render, "available_tools", lambda scheme: [fake_image]
    )

    def fake_runner(argv: list[str]) -> int:
        puml_path = Path(argv[-1])
        puml_path.with_suffix(".svg").write_text("<svg/>", encoding="utf-8")
        return 0

    result = plantuml_render.render_plantuml(
        "@startuml\nAlice -> Bob\n@enduml\n",
        output_dir=tmp_path,
        runner=fake_runner,
    )

    assert result.kind == "image"
    assert result.argv[0] == "viu"
