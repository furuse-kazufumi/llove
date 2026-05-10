"""F15 (t2/t3) — ImageRenderPane の非同期化 (Textual run_worker 連携).

`set_render` は同期で subprocess を踏むため、chafa の起動が遅い大き目の
diagram で UI が凍る。これを `set_render_async` に切り替えると、内部で
Textual の `run_worker(thread=True)` 相当に dispatch され、メインスレッド
が即座に返る (UI が動き続ける)。

テストは worker dispatcher を注入できるようにすることで、Textual App を
mount しなくても **「dispatch されたか / work が呼ばれたか / widget 更新
が text として届いたか」** を検証できる。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from llove.views import mermaid_render as mr

# ---------------------------------------------------------------------------
# _compute_text — pure ロジック切り出し
# ---------------------------------------------------------------------------


def test_compute_text_image_success(tmp_path: Path) -> None:
    """image kind + 成功 runner → ANSI 出力を返す."""
    from llove.views.image_render_pane import ImageRenderPane

    pane = ImageRenderPane(
        runner=lambda argv, *, timeout: (0, b"\x1b[31mvisible\x1b[0m", b"")
    )
    text = pane._compute_text(
        mr.MermaidRender(kind="image", argv=("chafa", "x.svg"))
    )
    assert "visible" in text


def test_compute_text_image_failure_returns_fallback() -> None:
    """image kind + 失敗 runner → ascii_text または unavailable マーカー."""
    from llove.views.image_render_pane import ImageRenderPane

    pane = ImageRenderPane(runner=lambda argv, *, timeout: (1, b"", b"err"))
    text = pane._compute_text(
        mr.MermaidRender(kind="image", argv=("chafa", "x.svg"))
    )
    assert text
    assert "unavailable" in text.lower() or "fail" in text.lower()


def test_compute_text_ascii_passthrough() -> None:
    """ascii kind → ascii_text をそのまま返す."""
    from llove.views.image_render_pane import ImageRenderPane

    pane = ImageRenderPane()
    text = pane._compute_text(
        mr.MermaidRender(kind="ascii", ascii_text="some ASCII art")
    )
    assert "ASCII art" in text


# ---------------------------------------------------------------------------
# set_render_async — worker dispatcher 注入
# ---------------------------------------------------------------------------


def test_set_render_async_dispatches_work_through_injected_dispatcher() -> None:
    """注入した dispatcher 経由で work が呼ばれること."""
    from llove.views.image_render_pane import ImageRenderPane

    captured: list[Callable[[], None]] = []

    def fake_dispatcher(work: Callable[[], None]) -> None:
        captured.append(work)
        # 同期実行して widget まで届くか確認
        work()

    pane = ImageRenderPane(
        runner=lambda argv, *, timeout: (0, b"async-ok", b""),
        worker_dispatcher=fake_dispatcher,
    )
    pane.set_render_async(
        mr.MermaidRender(kind="image", argv=("chafa", "x.svg"))
    )
    assert len(captured) == 1
    assert "async-ok" in pane.last_render


def test_set_render_async_without_dispatcher_falls_back_to_sync() -> None:
    """dispatcher が無い + App 未 mount → 同期実行 (last_render が即更新)."""
    from llove.views.image_render_pane import ImageRenderPane

    pane = ImageRenderPane(
        runner=lambda argv, *, timeout: (0, b"sync-ok", b"")
    )
    pane.set_render_async(
        mr.MermaidRender(kind="image", argv=("chafa", "x.svg"))
    )
    # フォールバックが効いて即座に widget が更新されること
    assert "sync-ok" in pane.last_render


def test_set_render_async_dispatch_failure_still_updates() -> None:
    """dispatcher 自体が raise しても、最終的に同期で widget が更新されること.

    本番でも 'mount されていない / run_worker が使えない' 状況に出くわす
    可能性があるため、最後の砦として同期 fallback が走らないと困る。
    """
    from llove.views.image_render_pane import ImageRenderPane

    def broken_dispatcher(work: Callable[[], None]) -> None:
        raise RuntimeError("no app")

    pane = ImageRenderPane(
        runner=lambda argv, *, timeout: (0, b"recovered", b""),
        worker_dispatcher=broken_dispatcher,
    )
    pane.set_render_async(
        mr.MermaidRender(kind="image", argv=("chafa", "x.svg"))
    )
    assert "recovered" in pane.last_render


def test_set_render_async_ascii_skips_subprocess() -> None:
    """ascii kind は subprocess を呼ばずに dispatch + apply で済む."""
    from llove.views.image_render_pane import ImageRenderPane

    runner_calls: list[list[str]] = []

    def runner(argv, *, timeout):
        runner_calls.append(list(argv))
        return 0, b"", b""

    pane = ImageRenderPane(runner=runner)
    pane.set_render_async(
        mr.MermaidRender(kind="ascii", ascii_text="just text")
    )
    assert "just text" in pane.last_render
    # ASCII では subprocess を呼ばない (image でないため)
    assert runner_calls == []


# ---------------------------------------------------------------------------
# callback factory — デフォルトで async path を使うか
# ---------------------------------------------------------------------------


def test_callback_factory_uses_async_by_default() -> None:
    """make_image_render_callback は async 経路を使うことが既定."""
    from llove.views.image_render_pane import (
        ImageRenderPane,
        make_image_render_callback,
    )

    captured: list[Callable[[], None]] = []

    def dispatcher(work: Callable[[], None]) -> None:
        captured.append(work)
        work()

    pane = ImageRenderPane(
        runner=lambda argv, *, timeout: (0, b"via-async", b""),
        worker_dispatcher=dispatcher,
    )
    cb = make_image_render_callback(pane)
    cb(mr.MermaidRender(kind="image", argv=("chafa", "x.svg")))

    # dispatcher が呼ばれたこと + widget が更新されたこと
    assert len(captured) == 1
    assert "via-async" in pane.last_render


def test_callback_factory_async_false_uses_sync_path() -> None:
    """async_dispatch=False で旧来の同期 set_render を呼ぶ."""
    from llove.views.image_render_pane import (
        ImageRenderPane,
        make_image_render_callback,
    )

    dispatcher_calls: list[Callable[[], None]] = []

    def dispatcher(work: Callable[[], None]) -> None:
        dispatcher_calls.append(work)

    pane = ImageRenderPane(
        runner=lambda argv, *, timeout: (0, b"sync-direct", b""),
        worker_dispatcher=dispatcher,
    )
    cb = make_image_render_callback(pane, async_dispatch=False)
    cb(mr.MermaidRender(kind="image", argv=("chafa", "x.svg")))

    # dispatcher は呼ばれず、同期で last_render に直接書かれる
    assert dispatcher_calls == []
    assert "sync-direct" in pane.last_render
