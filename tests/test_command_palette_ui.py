"""F20(c)③ Command Palette UI の最小 boot テスト.

Textual ``run_test()`` を使い:
    1. Widget が App に乗って boot する
    2. Enter で submit され, output が更新される
    3. Up で履歴遡行, Tab で補完が動く
    4. Modal Screen 版を push でき, Escape で閉じる

純粋関数の網羅は ``test_command_completion.py`` に分離済み. ここでは
Textual との結線のみを確認する.
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input

from llove.term import (
    CommandPaletteScreen,
    CommandPaletteWidget,
    CommandRegistry,
    make_default_context,
    register_builtins,
)


class _PaletteHostApp(App[None]):
    """``CommandPaletteWidget`` を 1 つだけ載せたテスト用ホスト."""

    def __init__(self) -> None:
        super().__init__()
        self.registry = CommandRegistry()
        register_builtins(self.registry)
        self.ctx = make_default_context(self.registry)
        self.palette = CommandPaletteWidget(registry=self.registry, ctx=self.ctx)

    def compose(self) -> ComposeResult:
        yield self.palette


class _ScreenHostApp(App[None]):
    """``CommandPaletteScreen`` を Escape で開閉できるテスト用ホスト."""

    def __init__(self) -> None:
        super().__init__()
        self.registry = CommandRegistry()
        register_builtins(self.registry)
        self.ctx = make_default_context(self.registry)

    def compose(self) -> ComposeResult:
        yield Input(id="dummy")  # 何か 1 つフォーカス対象が要る


# ---------------------------------------------------------------------------
# Widget boot
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_palette_widget_boots() -> None:
    app = _PaletteHostApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        # Input / Static 候補欄 / Static 出力欄が揃っているか
        assert app.palette.query_one("#cp-input", Input) is not None


@pytest.mark.asyncio
async def test_submit_dispatches_and_renders_output() -> None:
    app = _PaletteHostApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        inp = app.palette.query_one("#cp-input", Input)
        inp.focus()
        await pilot.press(*":help")
        await pilot.press("enter")
        await pilot.pause(0.05)
        # 履歴に push され, 出力欄に何か出ている
        assert ":help" in app.palette.history.items
        assert "[core]" in app.palette.last_output_text
        # 入力欄はクリア
        assert inp.value == ""


@pytest.mark.asyncio
async def test_history_up_recalls_last_submit() -> None:
    app = _PaletteHostApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        inp = app.palette.query_one("#cp-input", Input)
        inp.focus()
        await pilot.press(*":help")
        await pilot.press("enter")
        await pilot.pause(0.02)
        await pilot.press("up")
        await pilot.pause(0.02)
        assert inp.value == ":help"


@pytest.mark.asyncio
async def test_tab_completes_unique_prefix() -> None:
    app = _PaletteHostApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        inp = app.palette.query_one("#cp-input", Input)
        inp.focus()
        await pilot.press(*":id")
        await pilot.press("tab")
        await pilot.pause(0.02)
        assert inp.value == ":identity"


@pytest.mark.asyncio
async def test_suggestion_panel_updates_on_change() -> None:
    app = _PaletteHostApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        inp = app.palette.query_one("#cp-input", Input)
        inp.focus()
        await pilot.press(*":p")
        await pilot.pause(0.02)
        text = app.palette.last_suggest_text
        assert ":peer" in text and ":play" in text


# ---------------------------------------------------------------------------
# Modal Screen
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_modal_screen_pushes_and_dismisses() -> None:
    app = _ScreenHostApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.05)
        screen = CommandPaletteScreen(registry=app.registry, ctx=app.ctx)
        await app.push_screen(screen)
        await pilot.pause(0.05)
        # Modal が前面に出ている
        assert isinstance(app.screen, CommandPaletteScreen)
        # Escape で閉じる
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert not isinstance(app.screen, CommandPaletteScreen)
