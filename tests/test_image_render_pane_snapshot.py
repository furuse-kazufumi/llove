"""F15 (t2/t3) — ImageRenderPane の Textual snapshot test.

`pytest-textual-snapshot` で widget の実描画を SVG にキャプチャし、ベース
ライン画像と比較する。CSS / レイアウト / placeholder の表示崩れを検知する。

各テストは初回実行で `__snapshots__/` 以下に SVG を保存し、以降は差分検証。
意図的なレイアウト変更時は ``pytest --snapshot-update`` で更新。

注意: pytest-textual-snapshot は内部で Textual App を pilot し、実描画を
SVG export する。CI / dev 環境を問わずテスト可能 (バイナリ非依存)。
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from llove.views import mermaid_render as mr
from llove.views.image_render_pane import ImageRenderPane


class _PlaceholderApp(App):
    """初期 placeholder を表示するだけの App."""

    def compose(self) -> ComposeResult:
        yield ImageRenderPane()


class _AsciiApp(App):
    """ASCII fallback を貼った状態を表示する App."""

    def compose(self) -> ComposeResult:
        yield ImageRenderPane()

    def on_mount(self) -> None:
        pane = self.query_one(ImageRenderPane)
        pane.set_render(
            mr.MermaidRender(
                kind="ascii",
                ascii_text="◇ mermaid (ASCII fallback)\n----\nA --> B\n----\n",
            )
        )


class _ImageApp(App):
    """画像 ANSI 出力 (mocked chafa) を貼った状態を表示する App."""

    def compose(self) -> ComposeResult:
        # 固定 ANSI を返す runner で subprocess を踏まずに widget を更新
        yield ImageRenderPane(
            runner=lambda argv, *, timeout: (
                0,
                b"\x1b[31mRED\x1b[0m \x1b[32mGREEN\x1b[0m \x1b[34mBLUE\x1b[0m",
                b"",
            )
        )

    def on_mount(self) -> None:
        pane = self.query_one(ImageRenderPane)
        pane.set_render(
            mr.MermaidRender(
                kind="image", argv=("chafa", "--", "/tmp/x.svg")
            )
        )


@pytest.mark.skipif(
    pytest.importorskip("pytest_textual_snapshot", reason="snapshot plugin missing")
    is None,
    reason="pytest-textual-snapshot required",
)
def test_pane_placeholder_snapshot(snap_compare) -> None:
    """初期 placeholder のレイアウト/枠線/タイトルを snapshot で固定."""
    assert snap_compare(_PlaceholderApp(), terminal_size=(60, 12))


def test_pane_ascii_snapshot(snap_compare) -> None:
    """ASCII fallback がコードブロックとして見える状態."""
    assert snap_compare(_AsciiApp(), terminal_size=(60, 12))


def test_pane_image_snapshot(snap_compare) -> None:
    """ANSI 色付き出力 (Text.from_ansi 経由) が widget 内に色で出ている状態."""
    assert snap_compare(_ImageApp(), terminal_size=(60, 8))
