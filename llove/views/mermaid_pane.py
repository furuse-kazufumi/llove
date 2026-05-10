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
        worker_dispatcher: WorkerDispatcher | None = None,
    ) -> None:
        super().__init__(_PLACEHOLDER)
        self._runner: SubprocessRunner = runner or _default_runner
        self._timeout: int = timeout
        # worker_dispatcher が None のときは Textual の ``self.run_worker``
        # にフォールバックを試み、それも失敗したら同期実行に降りる。
        self._worker_dispatcher: WorkerDispatcher | None = worker_dispatcher
        self.last_render: str = _PLACEHOLDER
        self.border_title = "Mermaid"

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def set_render(self, mr: MermaidRender) -> None:
        """``MermaidRender`` を受け取り、**同期で** widget の表示を更新する.

        subprocess は呼び出しスレッドで走る。chafa が遅い diagram で UI を
        凍らせたくない場合は ``set_render_async`` を使うこと。
        """
        text = self._compute_text(mr)
        self._apply_text(text)

    def set_render_async(self, mr: MermaidRender) -> None:
        """``MermaidRender`` を **worker 経由で非同期に** 適用する.

        worker_dispatcher が注入されていればそれを使う。注入されていない場合
        Textual の ``self.run_worker(thread=True)`` を試み、それも使えない
        (App 未 mount / 例外) なら同期 fallback で `set_render` 相当の処理を
        実行する。最後の砦として fallback が走るので呼び出し側は失敗を
        気にしなくて良い。
        """
        def work() -> None:
            text = self._compute_text(mr)
            self._apply_text_thread_safe(text)

        try:
            self._dispatch_to_worker(work)
        except Exception:
            # dispatch 自体が落ちた → 同期 fallback で widget を更新
            self.set_render(mr)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _compute_text(self, mr: MermaidRender) -> str:
        """``MermaidRender`` から widget に貼る文字列を計算する pure 関数.

        画像経路で subprocess が成功すれば ANSI 文字列を返す (ESC が含まれる
        ので ``_apply_text`` 側が Rich の ``Text.from_ansi`` で描画する)。
        失敗時は ``mr.ascii_text`` か ``_UNAVAILABLE_MARKER`` に降りる。
        """
        if mr.kind == "image":
            captured = run_image_render(
                list(mr.argv), runner=self._runner, timeout=self._timeout
            )
            if captured is not None and captured.strip():
                return captured
            return mr.ascii_text or _UNAVAILABLE_MARKER
        if mr.kind == "ascii":
            return mr.ascii_text or _PLACEHOLDER
        # 想定外 kind: placeholder ではなく unavailable で「描けない」と伝える
        return _UNAVAILABLE_MARKER

    def _apply_text(self, text: str) -> None:
        """widget に文字列を貼る. ESC を含むなら ANSI 経由で描画."""
        self.last_render = text
        is_ansi = "\x1b" in text
        try:
            self.update(Text.from_ansi(text) if is_ansi else text)
        except Exception:  # nosec B110 — widget が App 外でも落ちない
            with contextlib.suppress(Exception):
                self.update(text)

    def _apply_text_thread_safe(self, text: str) -> None:
        """worker thread から widget を更新するための入口.

        Textual App 内なら ``self.app.call_from_thread`` 経由で main thread に
        飛ばす。App 外なら直接更新で問題ない (テストはこちらの経路に乗る)。
        """
        try:
            self.app.call_from_thread(self._apply_text, text)
            return
        except Exception:  # nosec B110 — App 外 or call_from_thread 不可
            self._apply_text(text)

    def _dispatch_to_worker(self, work: Callable[[], None]) -> None:
        """work 関数を worker に dispatch する.

        優先度:
            1. ``worker_dispatcher`` が注入されていればそれ
            2. Textual の ``self.run_worker(work, thread=True, exclusive=True)``
            3. 同期実行 (fallback)
        """
        if self._worker_dispatcher is not None:
            self._worker_dispatcher(work)
            return
        try:
            self.run_worker(work, thread=True, exclusive=True)
            return
        except Exception:  # nosec B110 — App 外 / 利用不可
            work()


# ---------------------------------------------------------------------------
# MarkdownView 連携 — 同期 callback ファクトリ
# ---------------------------------------------------------------------------


def make_mermaid_image_callback(
    pane: MermaidImagePane,
    *,
    async_dispatch: bool = True,
) -> Callable[[MermaidRender], None]:
    """``MarkdownView.mermaid_image_callback`` 互換の同期 callback を作る.

    既定 (``async_dispatch=True``) では `pane.set_render_async` 経由で
    Textual worker に dispatch する (UI が凍らない)。テストや subprocess
    完了を即座に待ちたい場合は ``async_dispatch=False`` で同期版に切替。

    どちらの場合も pane 側の例外は callback の外まで漏れない (View に
    波及させないため)。
    """

    def callback(mr: MermaidRender) -> None:
        with contextlib.suppress(Exception):
            if async_dispatch:
                pane.set_render_async(mr)
            else:
                pane.set_render(mr)

    return callback


__all__ = [
    "MermaidImagePane",
    "SubprocessRunner",
    "make_mermaid_image_callback",
    "run_image_render",
]
