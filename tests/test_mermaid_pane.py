"""F15 (t3) — Mermaid 画像描画 Pane (Textual subprocess worker 連携).

`MermaidRender(kind="image")` を受け取り、subprocess (chafa / viu / ...) を
実起動して **stdout の ANSI 出力を Static widget に貼る** 経路。

役割分担:

- ``run_image_render(argv, runner=None)``: pure 関数。argv を実行して
  捕捉した stdout (str) を返す。失敗時は ``None``。テストでは runner を
  注入して subprocess を踏まずに argv 検証 / 出力検証ができる。
- ``MermaidImagePane(Static)``: Textual widget。``set_render(mr)`` で
  上記 helper を呼び、結果を ``Text.from_ansi`` で widget に貼る。
  失敗時は ASCII fallback または「render unavailable」マーカー。
- ``make_mermaid_image_callback(pane)``: MarkdownView の
  ``mermaid_image_callback`` 互換ファクトリ。同期 callback として動き、
  内部で pane.set_render(mr) を呼ぶ。Textual の worker thread 連携は
  pane 側責務 (UI スレッド凍結を回避)。

設計の柱:
- subprocess は list-based argv のみ。timeout 付き。
- 例外 / non-zero は全部 ``None`` 経由で fallback に降りる (fail-closed)。
- Static.update() は App mount しなくても呼べる (既存 MarkdownView と同様)。
"""

from __future__ import annotations

from pathlib import Path

from llove.views import mermaid_render as mr


# ---------------------------------------------------------------------------
# run_image_render — pure 関数
# ---------------------------------------------------------------------------


def test_run_image_render_returns_stdout_on_success() -> None:
    from llove.views.mermaid_pane import run_image_render

    captured: dict[str, list[str]] = {}

    def fake_runner(argv: list[str], *, timeout: int) -> tuple[int, bytes, bytes]:
        captured["argv"] = argv
        return 0, b"\x1b[31mhello\x1b[0m image bytes", b""

    out = run_image_render(["chafa", "--", "/tmp/x.svg"], runner=fake_runner)
    assert out is not None
    assert "hello" in out
    assert captured["argv"] == ["chafa", "--", "/tmp/x.svg"]


def test_run_image_render_returns_none_on_nonzero_exit() -> None:
    from llove.views.mermaid_pane import run_image_render

    out = run_image_render(
        ["chafa", "--", "/missing.svg"],
        runner=lambda argv, *, timeout: (1, b"", b"file not found"),
    )
    assert out is None


def test_run_image_render_returns_none_on_oserror() -> None:
    from llove.views.mermaid_pane import run_image_render

    def explode(argv: list[str], *, timeout: int):
        raise OSError("not found")

    out = run_image_render(["nope"], runner=explode)
    assert out is None


def test_run_image_render_returns_none_on_empty_argv() -> None:
    from llove.views.mermaid_pane import run_image_render

    assert run_image_render([]) is None


# ---------------------------------------------------------------------------
# MermaidImagePane
# ---------------------------------------------------------------------------


def test_mermaid_image_pane_initial_state_is_placeholder() -> None:
    from llove.views.mermaid_pane import MermaidImagePane

    pane = MermaidImagePane()
    # placeholder 文字列 (詳細は実装側で決めて良いが、空ではない)
    assert pane.last_render
    assert isinstance(pane.last_render, str)


def test_mermaid_image_pane_set_render_image_updates_with_stdout(
    tmp_path: Path,
) -> None:
    from llove.views.mermaid_pane import MermaidImagePane

    svg = tmp_path / "x.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    pane = MermaidImagePane(
        runner=lambda argv, *, timeout: (0, b"\x1b[32mok\x1b[0m image", b"")
    )
    pane.set_render(
        mr.MermaidRender(
            kind="image",
            argv=("chafa", "--", str(svg)),
            svg_path=svg,
        )
    )
    assert "ok" in pane.last_render


def test_mermaid_image_pane_set_render_ascii_shows_fallback_text(
    tmp_path: Path,
) -> None:
    """ASCII kind を渡されても落ちず、ascii_text を表示する."""
    from llove.views.mermaid_pane import MermaidImagePane

    pane = MermaidImagePane()
    pane.set_render(
        mr.MermaidRender(
            kind="ascii",
            ascii_text=mr.ascii_fallback("flowchart LR\nA --> B\n"),
        )
    )
    assert "A --> B" in pane.last_render


def test_mermaid_image_pane_subprocess_failure_falls_back_to_ascii(
    tmp_path: Path,
) -> None:
    """subprocess 失敗 → ASCII fallback に降りる (UI 凍結なし)."""
    from llove.views.mermaid_pane import MermaidImagePane

    svg = tmp_path / "x.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    pane = MermaidImagePane(runner=lambda argv, *, timeout: (1, b"", b"err"))
    pane.set_render(
        mr.MermaidRender(
            kind="image",
            argv=("chafa", "--", str(svg)),
            svg_path=svg,
        )
    )
    # 失敗マーカーが出ること
    assert pane.last_render
    assert "image render unavailable" in pane.last_render.lower() or "fail" in pane.last_render.lower()


def test_mermaid_image_pane_set_render_image_without_argv_falls_back() -> None:
    from llove.views.mermaid_pane import MermaidImagePane

    pane = MermaidImagePane()
    pane.set_render(mr.MermaidRender(kind="image", argv=()))
    assert pane.last_render
    # サブプロセスを呼ぶべき argv が無いので何らかの fallback メッセージ
    assert "unavailable" in pane.last_render.lower() or "fail" in pane.last_render.lower()


# ---------------------------------------------------------------------------
# make_mermaid_image_callback — MarkdownView との繋ぎ込み
# ---------------------------------------------------------------------------


def test_make_mermaid_image_callback_routes_to_pane(tmp_path: Path) -> None:
    from llove.views.mermaid_pane import (
        MermaidImagePane,
        make_mermaid_image_callback,
    )

    svg = tmp_path / "y.svg"
    svg.write_text("<svg/>", encoding="utf-8")

    pane = MermaidImagePane(runner=lambda argv, *, timeout: (0, b"chafa-out", b""))
    cb = make_mermaid_image_callback(pane)

    cb(
        mr.MermaidRender(
            kind="image", argv=("chafa", "--", str(svg)), svg_path=svg
        )
    )
    assert "chafa-out" in pane.last_render


def test_callback_is_safe_when_pane_set_render_raises() -> None:
    """pane が暴れても callback は raise しない (View を巻き込まないため)."""
    from llove.views.mermaid_pane import make_mermaid_image_callback

    class BadPane:
        def set_render(self, *args, **kwargs):
            raise RuntimeError("pane broken")

    cb = make_mermaid_image_callback(BadPane())  # type: ignore[arg-type]
    # 例外が外まで漏れない
    cb(mr.MermaidRender(kind="ascii", ascii_text="x"))


# ---------------------------------------------------------------------------
# 統合 — MarkdownView から pane に画像が届く
# ---------------------------------------------------------------------------


def test_full_chain_markdownview_to_pane(tmp_path: Path) -> None:
    """MarkdownView (mermaid_render=True) → callback → pane.set_render → ANSI."""
    from llove.events import Event, EventKind
    from llove.views.markdown_view import MarkdownView
    from llove.views.mermaid_pane import (
        MermaidImagePane,
        make_mermaid_image_callback,
    )

    svg = tmp_path / "diag.svg"

    def fake_renderer(src: str, out: Path) -> mr.MermaidRender:
        out.mkdir(parents=True, exist_ok=True)
        target = out / "diagram.svg"
        target.write_text("<svg/>", encoding="utf-8")
        return mr.MermaidRender(
            kind="image",
            argv=("chafa", "--", str(target)),
            svg_path=target,
        )

    pane = MermaidImagePane(
        runner=lambda argv, *, timeout: (0, b"\x1b[33mPANE-IMAGE\x1b[0m", b"")
    )
    callback = make_mermaid_image_callback(pane)

    view = MarkdownView(
        mermaid_render=True,
        mermaid_renderer=fake_renderer,
        mermaid_image_callback=callback,
        mermaid_cache_dir=tmp_path,
    )
    view.feed(
        Event(
            kind=EventKind.NARRATION,
            payload={"text": "```mermaid\nflowchart LR\nA --> B\n```\n"},
        )
    )

    # markdown stream にはマーカー、pane には ANSI 出力が届いている
    assert "A --> B" not in view.last_render
    assert "PANE-IMAGE" in pane.last_render
    # svg path は使ってないけど未使用 var で warning が出ないように
    assert isinstance(svg, Path)
