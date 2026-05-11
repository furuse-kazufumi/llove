"""F20 Command Palette 最小骨組みのテスト.

カバー対象:
- parse_line: ``:`` 接頭辞 / 空入力 / quote / 未閉じ quote
- CommandRegistry: register / get / list / suggest / 重複拒否
- dispatch: alias / macro / 未知 / 入れ子上限
- ビルトイン: help / identity / layout / demo / play / open / peer
              / set / get / alias / macro
- hook 配線: 副作用 callable が呼ばれる
"""

from __future__ import annotations

import pytest

from llove.term import (
    Command,
    CommandContext,
    CommandRegistry,
    CommandResult,
    builtin_commands,
    dispatch,
    make_default_context,
    parse_line,
    register_builtins,
)

# ---------------------------------------------------------------------------
# parse_line
# ---------------------------------------------------------------------------


class TestParseLine:
    def test_strips_colon_prefix(self) -> None:
        p = parse_line(":help")
        assert p is not None
        assert p.name == "help"
        assert p.args == ()

    def test_works_without_colon(self) -> None:
        p = parse_line("help foo")
        assert p is not None
        assert p.name == "help"
        assert p.args == ("foo",)

    def test_quoted_arg(self) -> None:
        p = parse_line(':set msg="hello world"')
        assert p is not None
        assert p.name == "set"
        assert p.args == ("msg=hello world",)

    def test_empty_returns_none(self) -> None:
        assert parse_line("") is None
        assert parse_line("   ") is None
        assert parse_line(":") is None
        assert parse_line(":   ") is None

    def test_unterminated_quote_returns_none(self) -> None:
        assert parse_line(':set msg="unclosed') is None


# ---------------------------------------------------------------------------
# CommandRegistry
# ---------------------------------------------------------------------------


def _noop_handler(args: list[str], ctx: CommandContext) -> CommandResult:
    return CommandResult(ok=True, output=("noop",))


class TestRegistry:
    def test_register_and_get(self) -> None:
        reg = CommandRegistry()
        cmd = Command(name="foo", handler=_noop_handler, category="test")
        reg.register(cmd)
        assert reg.get("foo") is cmd
        assert reg.get("bar") is None

    def test_duplicate_rejected(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="foo", handler=_noop_handler))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(Command(name="foo", handler=_noop_handler))

    def test_empty_name_rejected(self) -> None:
        reg = CommandRegistry()
        with pytest.raises(ValueError, match="non-empty"):
            reg.register(Command(name="", handler=_noop_handler))

    def test_list_filtered_by_category(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="a", handler=_noop_handler, category="x"))
        reg.register(Command(name="b", handler=_noop_handler, category="y"))
        reg.register(Command(name="c", handler=_noop_handler, category="x"))
        assert [c.name for c in reg.list(category="x")] == ["a", "c"]
        assert [c.name for c in reg.list()] == ["a", "c", "b"]

    def test_suggest_close_match(self) -> None:
        reg = CommandRegistry()
        reg.register(Command(name="identity", handler=_noop_handler))
        reg.register(Command(name="layout", handler=_noop_handler))
        assert "identity" in reg.suggest("identty")
        # 完全に違う名前は候補ゼロ
        assert reg.suggest("xyzzy") == []


# ---------------------------------------------------------------------------
# dispatch — basic
# ---------------------------------------------------------------------------


class TestDispatchBasic:
    def test_unknown_returns_suggestion(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        ctx = make_default_context(reg)
        result = dispatch(":identty", ctx, reg)
        assert result.ok is False
        assert "identity" in result.suggested

    def test_empty_input(self) -> None:
        reg = CommandRegistry()
        ctx = make_default_context(reg)
        result = dispatch("", ctx, reg)
        assert result.ok is False
        assert result.error is not None

    def test_alias_redirects(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        ctx = make_default_context(reg)
        ctx.aliases["id"] = "identity"
        result = dispatch(":id", ctx, reg)
        assert result.ok is True
        assert any("did:key" in line for line in result.output)

    def test_macro_runs_each_step(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        ctx = make_default_context(reg)
        ctx.macros["bootstrap"] = ("set host=local", "set port=8080")
        result = dispatch(":bootstrap", ctx, reg)
        assert result.ok is True
        assert ctx.vars == {"host": "local", "port": "8080"}

    def test_macro_stops_on_first_error(self) -> None:
        reg = CommandRegistry()
        register_builtins(reg)
        ctx = make_default_context(reg)
        ctx.macros["bad"] = ("set ok=1", "play", "set never=2")
        result = dispatch(":bad", ctx, reg)
        assert result.ok is False
        assert ctx.vars == {"ok": "1"}  # 失敗以降は実行されない

    def test_alias_macro_recursion_caps(self) -> None:
        # alias を循環させても暴走しない
        reg = CommandRegistry()
        register_builtins(reg)
        ctx = make_default_context(reg)
        ctx.aliases["a"] = ":a"
        result = dispatch(":a", ctx, reg)
        assert result.ok is False
        assert "入れ子" in (result.error or "")


# ---------------------------------------------------------------------------
# Builtin commands
# ---------------------------------------------------------------------------


@pytest.fixture
def reg_ctx() -> tuple[CommandRegistry, CommandContext]:
    reg = CommandRegistry()
    register_builtins(reg)
    ctx = make_default_context(reg)
    return reg, ctx


class TestBuiltins:
    def test_builtin_count(self) -> None:
        # 期待: help / identity / layout / demo / play / open / peer
        # / set / get / alias / macro / fold / theme = 13 件
        # (2026-05-10 F15 (u8) で `fold`, 2026-05-11 F20 (d4) で `theme` を追加)
        names = {c.name for c in builtin_commands()}
        assert names == {
            "help",
            "identity",
            "layout",
            "demo",
            "play",
            "open",
            "peer",
            "set",
            "get",
            "alias",
            "macro",
            "fold",
            "theme",
        }

    def test_help_lists_categories(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":help", ctx, reg)
        assert result.ok is True
        joined = "\n".join(result.output)
        # 各カテゴリのタグが含まれる
        for tag in ("[core]", "[identity]", "[window]", "[game]"):
            assert tag in joined

    def test_help_specific(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":help play", ctx, reg)
        assert result.ok is True
        joined = "\n".join(result.output)
        assert "play" in joined and "<game>" in joined

    def test_help_unknown(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":help xyzzy", ctx, reg)
        assert result.ok is False

    def test_identity_no_hook(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":identity", ctx, reg)
        assert result.ok is True
        assert any("未設定" in line for line in result.output)

    def test_identity_with_hook(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        ctx.hooks["identity_did"] = "did:key:zABC"
        result = dispatch(":identity", ctx, reg)
        assert result.ok is True
        assert any("did:key:zABC" in line for line in result.output)

    def test_layout_calls_hook(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        called: list[str] = []
        ctx.hooks["apply_layout"] = lambda preset: called.append(preset)
        result = dispatch(":layout shogi-watcher", ctx, reg)
        assert result.ok is True
        assert called == ["shogi-watcher"]

    def test_layout_hook_failure_propagates(
        self, reg_ctx: tuple[CommandRegistry, CommandContext]
    ) -> None:
        reg, ctx = reg_ctx

        def boom(preset: str) -> None:
            raise RuntimeError("nope")

        ctx.hooks["apply_layout"] = boom
        result = dispatch(":layout x", ctx, reg)
        assert result.ok is False
        assert "nope" in (result.error or "")

    def test_layout_requires_arg(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":layout", ctx, reg)
        assert result.ok is False

    def test_demo_calls_hook(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        called: list[str] = []
        ctx.hooks["start_demo"] = lambda name: called.append(name)
        result = dispatch(":demo cost", ctx, reg)
        assert result.ok is True
        assert called == ["cost"]

    def test_play_requires_three_args(
        self, reg_ctx: tuple[CommandRegistry, CommandContext]
    ) -> None:
        reg, ctx = reg_ctx
        assert dispatch(":play chess", ctx, reg).ok is False
        assert dispatch(":play chess a", ctx, reg).ok is False
        assert dispatch(":play chess a b", ctx, reg).ok is True

    def test_play_calls_hook(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        called: list[tuple[str, str, str]] = []
        ctx.hooks["start_game"] = lambda g, a, b: called.append((g, a, b))
        result = dispatch(":play chess mock:a mock:b", ctx, reg)
        assert result.ok is True
        assert called == [("chess", "mock:a", "mock:b")]

    def test_open_requires_scheme(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":open ./a.png", ctx, reg)
        assert result.ok is False
        assert "scheme" in (result.error or "").lower()
        result = dispatch(":open image:///a.png", ctx, reg)
        assert result.ok is True

    def test_peer_default_verb_is_info(
        self, reg_ctx: tuple[CommandRegistry, CommandContext]
    ) -> None:
        reg, ctx = reg_ctx
        seen: list[tuple[str, str]] = []
        ctx.hooks["peer_call"] = lambda nid, verb: (
            seen.append((nid, verb)) or "ok"  # type: ignore[func-returns-value]
        )
        result = dispatch(":peer NodeA", ctx, reg)
        assert result.ok is True
        assert seen == [("NodeA", "info")]

    def test_peer_explicit_verb(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        ctx.hooks["peer_call"] = lambda nid, verb: f"{verb}:{nid}"
        result = dispatch(":peer NodeA ping", ctx, reg)
        assert result.ok is True
        assert any("ping:NodeA" in line for line in result.output)


# ---------------------------------------------------------------------------
# set / get / alias / macro
# ---------------------------------------------------------------------------


class TestVarsAliasMacro:
    def test_set_then_get(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        assert dispatch(":set theme=dark", ctx, reg).ok is True
        result = dispatch(":get theme", ctx, reg)
        assert result.ok is True
        assert any("theme=dark" in line for line in result.output)

    def test_set_invalid(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        assert dispatch(":set theme", ctx, reg).ok is False
        assert dispatch(":set =dark", ctx, reg).ok is False

    def test_get_unknown_key(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":get theme", ctx, reg)
        assert result.ok is False

    def test_get_lists_all_when_no_arg(
        self, reg_ctx: tuple[CommandRegistry, CommandContext]
    ) -> None:
        reg, ctx = reg_ctx
        ctx.vars.update({"a": "1", "b": "2"})
        result = dispatch(":get", ctx, reg)
        assert result.ok is True
        assert "a=1" in result.output and "b=2" in result.output

    def test_alias_register_and_use(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        assert dispatch(":alias id identity", ctx, reg).ok is True
        result = dispatch(":id", ctx, reg)
        assert result.ok is True

    def test_alias_list_when_empty(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":alias", ctx, reg)
        assert result.ok is True
        assert "(no aliases)" in result.output[0]

    def test_macro_register_and_use(self, reg_ctx: tuple[CommandRegistry, CommandContext]) -> None:
        reg, ctx = reg_ctx
        ok = dispatch(":macro init set a=1 ; set b=2 ; set c=3", ctx, reg)
        assert ok.ok is True
        assert ctx.macros["init"] == ("set a=1", "set b=2", "set c=3")
        result = dispatch(":init", ctx, reg)
        assert result.ok is True
        assert ctx.vars == {"a": "1", "b": "2", "c": "3"}

    def test_macro_empty_body_rejected(
        self, reg_ctx: tuple[CommandRegistry, CommandContext]
    ) -> None:
        reg, ctx = reg_ctx
        result = dispatch(":macro empty   ;  ;  ", ctx, reg)
        assert result.ok is False
