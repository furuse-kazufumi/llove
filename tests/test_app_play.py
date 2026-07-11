"""App レベル `:play` 実配線 (chess/shogi + @peer + 汎用 GameSource) のテスト.

`:peer` と同じく builtins の固定版を App が置換する。ここでは:
- ``:play`` の引数検証 (0 / >3 引数)
- ``@peer`` 解決 (未選択は fail-closed で honest error)
- 未知ゲームの案内 (shogi / chess を列挙)
- run_test 実配線: ``:peer`` 選択 → ``:play chess`` で GameSource がロードされる
  (fake transport seam で実 LLM サーバ不要)
- shogi 経路が壊れていないこと (mock:script、ネットワーク不要)
を確認する。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from textual.widgets import Input

from llove.app import LoveApp
from llove.demo.scenarios import get_scenario
from llove.events import Event
from llove.games.base.source import GameSource
from llove.llm import make_fake_http_transport
from llove.shogi.source import ShogiSource
from llove.sources.base import DataSource
from llove.term import dispatch
from llove.term.palette import CommandPaletteScreen, CommandPaletteWidget


class _NullSource(DataSource):
    """イベントを流さない最小ソース (unmounted な dispatch テスト用)."""

    name = "null"

    async def stream(self) -> AsyncIterator[Event]:
        return
        yield  # pragma: no cover — generator 型にするための到達しない yield


def _fixed_move_transport(move: str = "e2e4"):  # type: ignore[no-untyped-def]
    """常に固定手を返す ollama 形状 fake (wiring 用; すぐ終局しても source は不変)."""

    def handler(method, url, headers, body):  # type: ignore[no-untyped-def]
        return 200, json.dumps(
            {"model": "m", "message": {"role": "assistant", "content": move}, "done": True}
        ).encode()

    return make_fake_http_transport(handler)


async def _run_cmd(pilot, app, command: str) -> CommandPaletteWidget:  # type: ignore[no-untyped-def]
    await pilot.press(":")
    await pilot.pause(0.05)
    assert isinstance(app.screen, CommandPaletteScreen)
    widget = app.screen.query_one(CommandPaletteWidget)
    inp = widget.query_one("#cp-input", Input)
    inp.focus()
    inp.value = command
    await pilot.press("enter")
    await pilot.pause(0.05)
    return widget


# ---------------------------------------------------------------------------
# 純関数 / unmounted dispatch (event loop 不要 — _load_source に到達しない経路)
# ---------------------------------------------------------------------------


class TestPlayRegistration:
    def test_play_registered_with_new_hint(self) -> None:
        app = LoveApp(_NullSource())
        registry, _ = app._command_palette_context()
        cmd = registry.get("play")
        assert cmd is not None
        # builtins の "<game> <p1> <p2>" が App registry では省略可版に置換済み.
        assert cmd.args_hint == "<game> [<p1>] [<p2>]"

    def test_play_no_args_is_usage_error(self) -> None:
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":play", ctx, registry)
        assert result.ok is False
        assert "usage" in (result.error or "")

    def test_play_too_many_args_is_usage_error(self) -> None:
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":play chess a b c", ctx, registry)
        assert result.ok is False
        assert "usage" in (result.error or "")


class TestResolvePeerToken:
    def test_passthrough_non_peer(self) -> None:
        app = LoveApp(_NullSource())
        assert app._resolve_peer_token("ollama:llama3.2") == "ollama:llama3.2"

    def test_peer_token_with_selection(self) -> None:
        app = LoveApp(_NullSource())
        app.active_peer_spec = "ollama:qwen2.5:14b"
        assert app._resolve_peer_token("@peer") == "ollama:qwen2.5:14b"

    def test_peer_token_without_selection_raises(self) -> None:
        app = LoveApp(_NullSource())
        with pytest.raises(ValueError, match="no peer selected"):
            app._resolve_peer_token("@peer")


class TestPlayErrorPaths:
    def test_play_peer_token_without_selection_reports_honestly(self) -> None:
        # ':play chess' (p1/p2 省略 → @peer) を peer 未選択で叩くと fail-closed.
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":play chess", ctx, registry)
        assert result.ok is False
        assert "対局起動失敗" in (result.error or "")
        assert "no peer selected" in (result.error or "")
        # 到達前に失敗 — source は差し替わらない.
        assert isinstance(app._source, _NullSource)

    def test_play_unknown_game_lists_available(self) -> None:
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":play go ollama:x ollama:y", ctx, registry)
        assert result.ok is False
        err = result.error or ""
        assert "unsupported game" in err
        # 案内に shogi と chess の両方を含む.
        assert "shogi" in err
        assert "chess" in err


# ---------------------------------------------------------------------------
# run_test 実配線 (event loop あり; fake transport seam で LLM サーバ不要)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_play_chess_loads_game_source() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    app._game_transport = _fixed_move_transport("e2e4")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        # peer を選択 → :play chess (p1/p2 省略) で両者にその peer を据える.
        widget = await _run_cmd(pilot, app, "peer ollama:qwen2.5:7b")
        assert "peer set: ollama:qwen2.5:7b" in widget.last_output_text
        widget = await _run_cmd(pilot, app, "play chess")
        assert "対局開始: chess" in widget.last_output_text
        assert isinstance(app._source, GameSource)
        assert app._source._engine.game == "chess"


@pytest.mark.asyncio
async def test_play_chess_explicit_specs_loads_game_source() -> None:
    app = LoveApp(get_scenario("scada"), with_narration=True)
    app._game_transport = _fixed_move_transport("e2e4")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "play chess ollama:llama3.2 ollama:llama3.2")
        assert "対局開始: chess" in widget.last_output_text
        assert isinstance(app._source, GameSource)


@pytest.mark.asyncio
async def test_play_chess_events_reach_the_audit_pane() -> None:
    # 「TUI で完結」の核心: 対局イベントが実際に audit ペインに描画される。
    # fixed "e2e4" fake → white が 1 手指し、black は不一致で resign → 即終局。
    from llove.events import EventKind

    app = LoveApp(get_scenario("scada"), with_narration=True)
    app._game_transport = _fixed_move_transport("e2e4")
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        await _run_cmd(pilot, app, "play chess ollama:llama3.2 ollama:llama3.2")
        # 短い対局が流れ切るまで少しポンプする。
        for _ in range(10):
            await pilot.pause(0.05)
        rows = "\n".join(app._audit._rows)
        assert "chess game start" in rows  # game.start が描画された
        # 少なくとも 1 手 + 終局まで audit に届いている。
        assert app._audit._counts.get(EventKind.AUDIT, 0) >= 2
        assert "game end" in rows


@pytest.mark.asyncio
async def test_play_shogi_still_works_with_mock() -> None:
    # shogi 経路 (別スタック) が壊れていないこと — mock:script はネットワーク不要.
    app = LoveApp(get_scenario("scada"), with_narration=True)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause(0.1)
        widget = await _run_cmd(pilot, app, "play shogi mock:script mock:script")
        assert "対局開始: shogi" in widget.last_output_text
        assert isinstance(app._source, ShogiSource)
