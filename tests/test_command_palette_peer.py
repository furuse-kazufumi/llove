"""F20(k) `:peer` 実配線 (llove.llm config 検証) のテスト.

カバー対象:
- ``resolve_peer_command`` 純関数: 状態表示 / 選択 / fail-closed / 未知 provider
- LoveApp 配線: ``active_peer_spec`` への保存, 失敗時に保存されないこと
- 秘密情報 (API キー値) と赤緑インジケータが出力に現れないこと

検証は config レベルのみ (env が静的に揃っているか) — 疎通テストはしない
(``llove.llm.config`` の honest 方針と一致)。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from llove.app import LoveApp, resolve_peer_command
from llove.events import Event
from llove.llm import DEFAULT_MODELS, LLMConfig
from llove.sources.base import DataSource
from llove.term import dispatch


class _NullSource(DataSource):
    """イベントを 1 つも流さない最小ソース (palette 配線のテスト専用)."""

    name = "null"

    async def stream(self) -> AsyncIterator[Event]:
        return
        yield  # pragma: no cover — generator 型にするための到達しない yield


def _cfg(**env: str) -> LLMConfig:
    """env 注入で LLMConfig を構築 (os.environ 非依存の純関数テスト用)."""
    return LLMConfig.from_env(env=dict(env))


# ---------------------------------------------------------------------------
# resolve_peer_command — 引数なし (状態表示)
# ---------------------------------------------------------------------------


class TestResolvePeerStatus:
    def test_no_args_shows_unselected_and_all_providers(self) -> None:
        ok, lines, new_spec = resolve_peer_command([], _cfg())
        assert ok is True
        assert new_spec is None
        joined = "\n".join(lines)
        assert "(未選択)" in joined
        # KNOWN_PROVIDERS 全員の status 行が出る
        assert "ollama" in joined
        assert "anthropic" in joined
        assert "llmesh" in joined
        # 未設定 provider は reason で理由が分かる
        assert "ANTHROPIC_API_KEY not set" in joined

    def test_no_args_with_key_lists_anthropic_available(self) -> None:
        ok, lines, _ = resolve_peer_command([], _cfg(ANTHROPIC_API_KEY="sk-test-secret"))
        assert ok is True
        assert any("available" in line and "anthropic" in line for line in lines)
        # キー値そのものは絶対に表示しない (has_api_key の真偽だけ)
        assert "sk-test-secret" not in "\n".join(lines)

    def test_no_args_shows_current_selection(self) -> None:
        ok, lines, _ = resolve_peer_command([], _cfg(), current_spec="ollama:llama3.2")
        assert ok is True
        assert any("peer: ollama:llama3.2" in line for line in lines)

    def test_no_red_green_indicators(self) -> None:
        # RAPTOR 規約: 🔴/🟢 は perspective 依存なので使わない (✓/✗ は可)
        for env in ({}, {"ANTHROPIC_API_KEY": "k"}):
            _, lines, _ = resolve_peer_command([], LLMConfig.from_env(env=dict(env)))
            joined = "\n".join(lines)
            assert "🔴" not in joined
            assert "🟢" not in joined


# ---------------------------------------------------------------------------
# resolve_peer_command — 選択 (検証 + fail-closed)
# ---------------------------------------------------------------------------


class TestResolvePeerSelect:
    def test_select_ollama_returns_new_spec(self) -> None:
        ok, lines, new_spec = resolve_peer_command(["ollama:llama3.2"], _cfg())
        assert ok is True
        assert new_spec == "ollama:llama3.2"
        assert any("peer set: ollama:llama3.2" in line for line in lines)

    def test_select_provider_only_uses_default_model(self) -> None:
        ok, _, new_spec = resolve_peer_command(["ollama"], _cfg())
        assert ok is True
        assert new_spec == f"ollama:{DEFAULT_MODELS['ollama']}"

    def test_select_unconfigured_anthropic_fails_closed(self) -> None:
        ok, lines, new_spec = resolve_peer_command(["anthropic:claude-haiku-4-5"], _cfg())
        assert ok is False
        assert new_spec is None
        joined = "\n".join(lines)
        assert "anthropic is not configured" in joined
        # 有効化に必要な環境変数を案内する
        assert "ANTHROPIC_API_KEY" in joined

    def test_select_configured_anthropic_succeeds(self) -> None:
        ok, _, new_spec = resolve_peer_command(
            ["anthropic:claude-haiku-4-5"], _cfg(ANTHROPIC_API_KEY="k")
        )
        assert ok is True
        assert new_spec == "anthropic:claude-haiku-4-5"

    def test_unknown_provider_polite_error(self) -> None:
        ok, lines, new_spec = resolve_peer_command(["bogus:x"], _cfg())
        assert ok is False
        assert new_spec is None
        joined = "\n".join(lines)
        assert "unknown provider" in joined
        assert "bogus" in joined
        # known 一覧を案内する (parse_llm_spec のメッセージ)
        assert "anthropic" in joined

    def test_too_many_args_is_usage_error(self) -> None:
        ok, lines, new_spec = resolve_peer_command(["a", "b"], _cfg())
        assert ok is False
        assert new_spec is None
        assert "usage" in lines[0]


# ---------------------------------------------------------------------------
# LoveApp 配線 — active_peer_spec の保存と palette dispatch
# ---------------------------------------------------------------------------


class TestAppPeerWiring:
    def test_peer_set_saves_active_spec(self) -> None:
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        assert app.active_peer_spec is None
        result = dispatch(":peer ollama:llama3.2", ctx, registry)
        assert result.ok is True
        assert app.active_peer_spec == "ollama:llama3.2"
        assert any("peer set: ollama:llama3.2" in line for line in result.output)

    def test_peer_fail_closed_does_not_save(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":peer anthropic:claude-haiku-4-5", ctx, registry)
        assert result.ok is False
        assert app.active_peer_spec is None
        assert "not configured" in (result.error or "")

    def test_peer_no_args_reports_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-abc")
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":peer", ctx, registry)
        assert result.ok is True
        joined = "\n".join(result.output)
        assert "ollama" in joined
        assert "anthropic" in joined
        assert "llmesh" in joined
        # キー値は表示しない
        assert "sk-test-abc" not in joined

    def test_peer_status_reflects_saved_selection(self) -> None:
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        assert dispatch(":peer ollama:llama3.2", ctx, registry).ok is True
        result = dispatch(":peer", ctx, registry)
        assert result.ok is True
        assert any("peer: ollama:llama3.2" in line for line in result.output)

    def test_peer_unknown_provider_via_app(self) -> None:
        app = LoveApp(_NullSource())
        registry, ctx = app._command_palette_context()
        result = dispatch(":peer bogus:x", ctx, registry)
        assert result.ok is False
        assert app.active_peer_spec is None
        assert "unknown provider" in (result.error or "")

    def test_peer_registered_with_new_hint(self) -> None:
        # builtins の ":peer <NodeID> [verb]" が app registry では置換済み
        app = LoveApp(_NullSource())
        registry, _ = app._command_palette_context()
        cmd = registry.get("peer")
        assert cmd is not None
        assert cmd.args_hint == "[<provider:model>]"
