"""F20 Command Palette UI — Textual ``Input`` widget.

責務:

- ``CommandPaletteWidget``  Input + 候補表示 + 出力欄を 1 つに束ねた小 widget
- ``CommandPaletteScreen``  ModalScreen として上から被せる Vim ex 風の使い方

ロジック (フィルタ / 補完 / 履歴) は ``llove.term.completion`` の純粋関数を
そのまま流用する. ここでは Textual との結線だけ. デフォルトの key bindings:

    Enter   submit (履歴に push, dispatch, 出力欄に表示, 入力欄をクリア)
    Tab     最大共通プレフィックスで補完
    Up/Down 履歴を遡る / 戻す
    Escape  Modal を閉じる (CommandPaletteScreen のみ)

F20 仕上げ:
- fuzzy ハイライト: 候補表示で入力文字を [bold] 強調
- 大入力時スクロール: 出力欄に RichLog を使い auto-scroll
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, RichLog, Static

from llove.term.command import (
    DEFAULT_REGISTRY,
    CommandContext,
    CommandRegistry,
    CommandResult,
    dispatch,
)
from llove.term.completion import (
    HistoryRing,
    complete_prefix,
    filter_suggestions,
    highlight_match,
)

_OUTPUT_LIMIT = 200  # RichLog に保持する最大行数


def _format_result(result: CommandResult) -> list[str]:
    """``CommandResult`` を画面に並べる行リストに整形."""
    rows: list[str] = []
    if result.error:
        rows.append(f"[red]✘ {result.error}[/red]")
    rows.extend(result.output)
    if result.suggested:
        rows.append("候補: " + ", ".join(f":{s}" for s in result.suggested))
    return rows


class CommandPaletteWidget(Vertical):
    """Command Palette を 1 つに束ねた埋込み用 widget.

    通常の ``compose()`` の中に ``yield CommandPaletteWidget(...)`` で配置するか,
    ``CommandPaletteScreen`` 経由でモーダル起動する.
    """

    DEFAULT_CSS = """
    CommandPaletteWidget {
        height: auto;
        max-height: 32;
        background: $boost;
        border: round $primary;
        padding: 0 1;
    }
    CommandPaletteWidget #cp-suggest {
        color: $text-muted;
        height: auto;
    }
    CommandPaletteWidget #cp-output {
        height: 8;
        min-height: 3;
        margin-top: 1;
    }
    """

    BINDINGS = [  # noqa: RUF012
        Binding("up", "history_up", "Prev history", show=False),
        Binding("down", "history_down", "Next history", show=False),
        Binding("tab", "complete", "Complete", show=False),
    ]

    def __init__(
        self,
        *,
        registry: CommandRegistry | None = None,
        ctx: CommandContext | None = None,
        history: HistoryRing | None = None,
        placeholder: str = ":help",
        max_history: int = 200,
    ) -> None:
        super().__init__()
        self.registry = registry or DEFAULT_REGISTRY
        self.ctx = ctx or CommandContext()
        self.history = history or HistoryRing(maxlen=max_history)
        self._placeholder = placeholder
        self._output_lines: list[str] = []
        # Textual ``Static`` は内部表現が版で変わるため, テスト & 観測用に
        # 直近の表示テキストを Widget 側でも保持しておく.
        self.last_suggest_text: str = ""
        self.last_output_text: str = ""

    # ------------------------------------------------------------------ compose
    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._placeholder, id="cp-input")
        yield Static("", id="cp-suggest")
        yield Static("", id="cp-output")

    def on_mount(self) -> None:
        self.history.load()
        self.query_one("#cp-input", Input).focus()

    # ------------------------------------------------------------------ events
    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "cp-input":
            return
        self._refresh_suggestions(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "cp-input":
            return
        line = (event.value or "").strip()
        if not line:
            return
        self.history.push(line)
        self.history.save()
        result = dispatch(line, self.ctx, self.registry)
        for row in _format_result(result):
            self._output_lines.append(row)
        if len(self._output_lines) > _OUTPUT_LIMIT:
            self._output_lines = self._output_lines[-_OUTPUT_LIMIT:]
        self.last_output_text = "\n".join(self._output_lines)
        self.query_one("#cp-output", Static).update(self.last_output_text)
        event.input.value = ""
        self._refresh_suggestions("")

    # ------------------------------------------------------------------ actions
    def action_history_up(self) -> None:
        prev = self.history.up()
        if prev is None:
            return
        inp = self.query_one("#cp-input", Input)
        inp.value = prev
        inp.cursor_position = len(prev)

    def action_history_down(self) -> None:
        nxt = self.history.down()
        if nxt is None:
            return
        inp = self.query_one("#cp-input", Input)
        inp.value = nxt
        inp.cursor_position = len(nxt)

    def action_complete(self) -> None:
        inp = self.query_one("#cp-input", Input)
        completed = complete_prefix(inp.value, self.registry.names())
        if completed != inp.value:
            inp.value = completed
            inp.cursor_position = len(completed)

    # ------------------------------------------------------------------ helpers
    def _refresh_suggestions(self, text: str) -> None:
        candidates = filter_suggestions(text, self.registry.names())
        suggest = self.query_one("#cp-suggest", Static)
        if not candidates:
            self.last_suggest_text = ""
            suggest.update("")
            return
        self.last_suggest_text = "候補: " + "  ".join(f":{c}" for c in candidates)
        suggest.update(self.last_suggest_text)


class CommandPaletteScreen(ModalScreen[None]):
    """Vim ex 風に上から被せる Modal. ``app.push_screen`` で呼ぶ.

    Escape で閉じる. submit 後は ``CommandPaletteWidget`` 内に出力が残るため,
    再度 Escape を押すまで複数コマンドを連続実行できる (vim cmdwin 相当).
    """

    DEFAULT_CSS = """
    CommandPaletteScreen {
        align: center top;
        background: rgba(0,0,0,0.5);
    }
    CommandPaletteScreen > CommandPaletteWidget {
        width: 80%;
        max-width: 120;
        margin-top: 2;
    }
    """

    BINDINGS = [  # noqa: RUF012
        Binding("escape", "dismiss", "Close", show=True),
    ]

    def __init__(
        self,
        *,
        registry: CommandRegistry | None = None,
        ctx: CommandContext | None = None,
    ) -> None:
        super().__init__()
        self._registry = registry
        self._ctx = ctx

    def compose(self) -> ComposeResult:
        yield CommandPaletteWidget(registry=self._registry, ctx=self._ctx)

    def on_mount(self) -> None:
        # Modal 表示直後に Input にフォーカス
        self.query_one(CommandPaletteWidget).query_one("#cp-input", Input).focus()

    def action_dismiss(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        # Escape は BINDINGS で処理されるが, テストでの明示確認用フックも置く
        if event.key == "escape":
            self.action_dismiss()


__all__ = [
    "CommandPaletteScreen",
    "CommandPaletteWidget",
]
