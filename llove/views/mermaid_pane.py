"""F15 (t3) — Mermaid 画像描画 Pane (Textual subprocess worker 連携).

`MermaidRender(kind="image")` を受け取り、サブプロセス
(chafa / viu / timg / kitty +kitten icat / wezterm imgcat) を実起動して
**stdout の ANSI 出力を Static widget に貼る** Textual ペイン。

レイヤ:

1. ``run_image_render(argv, runner)`` — pure 関数。argv を実行して stdout
   を str で返す。失敗時は ``None``。テストでは ``runner`` を注入し
   subprocess を踏まずに argv 検証ができる。
2. ``MermaidImagePane(Static)`` — Textual widget。``set_render(mr)`` で
   上記 helper を呼び、結果を Rich の ``Text.from_ansi`` 経由で widget に
   貼る。失敗時は ASCII fallback / 「render unavailable」マーカー。
3. ``make_mermaid_image_callback(pane)`` — ``MarkdownView`` の
   ``mermaid_image_callback`` 互換ファクトリ。同期 callback として動き、
   内部で ``pane.set_render(mr)`` を呼ぶ。

セキュリティ:
- subprocess は **list-based argv のみ** (shell=True 禁止)
- timeout を必ず付ける (デフォルト 10 秒)
- 異常終了 / OSError / TimeoutExpired はすべて ``None`` 経由で
  fallback に降りる (fail-closed)

テスト容易性:
- ``runner`` 差し替えで subprocess を踏まずに argv / 出力検証可能
- ``Static.update()`` は App mount 不要なので widget 単体テスト可能
"""

from __future__ import annotations

import contextlib
import subprocess  # nosec B404 — list-based argv only.
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.text import Text
from textual.widgets import Static

from llove.views.mermaid_render import MermaidRender

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# subprocess runner
# ---------------------------------------------------------------------------

# (returncode, stdout_bytes, stderr_bytes) を返す callable。
# テストはこれを差し替えて subprocess を実行せずに argv 検証ができる。
SubprocessRunner = Callable[..., tuple[int, bytes, bytes]]

# `set_render_async` が work 関数を渡す dispatcher。Textual の
# ``self.run_worker`` と互換 (引数 1 つの callable を受ける)。テストでは
# 同期実行する fake に差し替えて、subprocess + widget 更新を検証する。
WorkerDispatcher = Callable[[Callable[[], None]], None]


def _default_runner(argv: list[str], *, timeout: int) -> tuple[int, bytes, bytes]:
    """``subprocess.run`` のデフォルト実装. capture_output で stdout/stderr 捕捉."""
    proc = subprocess.run(  # nosec B603 — argv is fully controlled by caller.
        argv,
        check=False,
        capture_output=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or b"", proc.stderr or b""


def run_image_render(
    argv: list[str] | tuple[str, ...],
    *,
    runner: SubprocessRunner | None = None,
    timeout: int = 10,
) -> str | None:
    """``argv`` を実行し、stdout (UTF-8 デコード済) を返す.

    Returns
    -------
    成功時: 捕捉した stdout 文字列 (chafa の ANSI 出力等)。
    失敗時: ``None`` (空 argv / 非ゼロ終了 / OSError / TimeoutExpired)。
    """
    if not argv:
        return None
    run = runner or _default_runner
    try:
        rc, stdout, _stderr = run(list(argv), timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if rc != 0:
        return None
    try:
        return stdout.decode("utf-8", errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

_PLACEHOLDER = "_(no mermaid render yet)_"
_UNAVAILABLE_MARKER = "_(◇ image render unavailable — falling back to ASCII)_"


class MermaidImagePane(Static):
    """Textual pane that displays the latest mermaid image render.

    Lifecycle:
        - 初期表示は placeholder
        - ``set_render(mr)`` で MermaidRender を渡すと、kind に応じて
          subprocess (image) / ascii_text (ascii) を表示する
        - subprocess 失敗時は ASCII fallback (mr.ascii_text) があればそれ、
          無ければ ``_UNAVAILABLE_MARKER`` を出す
    """

    name = "mermaid_image"
    title = "Mermaid"

    DEFAULT_CSS = """
    MermaidImagePane {
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        *,
        runner: SubprocessRunner | None = None,
        timeout: int = 10,
    ) -> None:
        super().__init__(_PLACEHOLDER)
        self._runner: SubprocessRunner = runner or _default_runner
        self._timeout: int = timeout
        self.last_render: str = _PLACEHOLDER
        self.border_title = "Mermaid"

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def set_render(self, mr: MermaidRender) -> None:
        """``MermaidRender`` を受け取り、widget の表示を更新する.

        - kind == "image": subprocess を起動して stdout (ANSI) を貼る
        - kind == "ascii": ascii_text を貼る
        - 失敗時: ASCII fallback or unavailable マーカー
        """
        if mr.kind == "image":
            captured = run_image_render(
                list(mr.argv), runner=self._runner, timeout=self._timeout
            )
            if captured is not None and captured.strip():
                self._show_ansi(captured)
                return
            # 失敗時: ascii_text があれば使う、無ければ unavailable
            self._show_text(mr.ascii_text or _UNAVAILABLE_MARKER)
            return
        if mr.kind == "ascii":
            self._show_text(mr.ascii_text or _PLACEHOLDER)
            return
        # 想定外 kind: placeholder に戻すと意味不明なので unavailable を出す
        self._show_text(_UNAVAILABLE_MARKER)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _show_ansi(self, ansi: str) -> None:
        """ANSI 文字列を Rich Text 経由で widget に貼る."""
        self.last_render = ansi
        try:
            self.update(Text.from_ansi(ansi))
        except Exception:  # nosec B110 — widget が App 外でも落ちない
            self.update(ansi)

    def _show_text(self, text: str) -> None:
        """プレーン文字列を widget に貼る."""
        self.last_render = text
        try:
            self.update(text)
        except Exception:  # nosec B110 — widget が App 外でも落ちない
            return


# ---------------------------------------------------------------------------
# MarkdownView 連携 — 同期 callback ファクトリ
# ---------------------------------------------------------------------------


def make_mermaid_image_callback(
    pane: MermaidImagePane,
) -> Callable[[MermaidRender], None]:
    """``MarkdownView.mermaid_image_callback`` 互換の同期 callback を作る.

    ``MarkdownView`` の callback は同期。pane 側で実 subprocess 起動を
    する設計 (将来 Textual の ``run_worker(thread=True)`` でラップする
    ときも、この callback ファクトリは触らずに pane の中だけ書き換えれば
    良い)。callback 自体は ``pane.set_render`` 例外を吸収するだけ。
    """

    def callback(mr: MermaidRender) -> None:
        with contextlib.suppress(Exception):
            pane.set_render(mr)

    return callback


__all__ = [
    "MermaidImagePane",
    "SubprocessRunner",
    "make_mermaid_image_callback",
    "run_image_render",
]
