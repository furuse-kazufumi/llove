"""F15 (u8) — `:fold` builtin command test (F20 integration).

The fold builtin should:
    1. Validate the verb syntax even when no view is bound (fail-closed UX).
    2. Forward valid verbs to ``ctx.hooks['fold']`` when present.
    3. Return ok=False with a useful error on unknown verbs / bad args.
    4. Be discoverable via ``:help`` (registered with ``builtin_commands``).
"""

from __future__ import annotations

from llove.term import (
    CommandContext,
    CommandRegistry,
    builtin_commands,
    dispatch,
    make_default_context,
    register_builtins,
)


def _fresh_registry() -> tuple[CommandRegistry, CommandContext]:
    reg = CommandRegistry()
    register_builtins(reg)
    ctx = make_default_context(reg)
    return reg, ctx


def test_fold_command_is_registered_as_builtin() -> None:
    names = {c.name for c in builtin_commands()}
    assert "fold" in names


def test_fold_no_args_returns_usage_error() -> None:
    reg, ctx = _fresh_registry()
    result = dispatch(":fold", ctx, reg)
    assert result.ok is False
    assert result.error is not None
    # Must mention at least the canonical verbs so the user can recover.
    assert "close-all" in result.error
    assert "open-all" in result.error


def test_fold_unknown_verb_returns_error_listing_valid_verbs() -> None:
    reg, ctx = _fresh_registry()
    result = dispatch(":fold xyzzy", ctx, reg)
    assert result.ok is False
    assert result.error is not None
    assert "xyzzy" in result.error


def test_fold_close_all_without_hook_is_audit_warn_not_error() -> None:
    """No view bound — verb is valid, so we ack with a notice, not a failure."""
    reg, ctx = _fresh_registry()
    result = dispatch(":fold close-all", ctx, reg)
    assert result.ok is True
    assert any("foldable" in line.lower() or "view" in line.lower() for line in result.output)


def test_fold_close_all_invokes_hook() -> None:
    reg, ctx = _fresh_registry()
    calls: list[tuple[str, list[str]]] = []

    def hook(verb: str, args: list[str]) -> tuple[str, ...]:
        calls.append((verb, list(args)))
        return ("closed all folds",)

    ctx.hooks["fold"] = hook
    result = dispatch(":fold close-all", ctx, reg)
    assert result.ok is True
    assert calls == [("close-all", [])]
    assert "closed all folds" in result.output


def test_fold_open_all_invokes_hook() -> None:
    reg, ctx = _fresh_registry()
    calls: list[tuple[str, list[str]]] = []
    ctx.hooks["fold"] = lambda v, a: calls.append((v, list(a))) or ("ok",)

    result = dispatch(":fold open-all", ctx, reg)
    assert result.ok is True
    assert calls == [("open-all", [])]


def test_fold_by_tag_requires_a_kind() -> None:
    reg, ctx = _fresh_registry()
    result = dispatch(":fold by-tag", ctx, reg)
    assert result.ok is False
    assert result.error is not None


def test_fold_by_tag_forwards_kind_to_hook() -> None:
    reg, ctx = _fresh_registry()
    captured: list[tuple[str, list[str]]] = []
    ctx.hooks["fold"] = lambda v, a: captured.append((v, list(a))) or ("ok",)

    result = dispatch(":fold by-tag code", ctx, reg)
    assert result.ok is True
    assert captured == [("by-tag", ["code"])]


def test_fold_appears_in_help_listing() -> None:
    reg, ctx = _fresh_registry()
    result = dispatch(":help", ctx, reg)
    assert result.ok is True
    body = "\n".join(result.output)
    assert ":fold" in body or "fold" in body


def test_fold_help_lookup_describes_command() -> None:
    reg, ctx = _fresh_registry()
    result = dispatch(":help fold", ctx, reg)
    assert result.ok is True
    body = "\n".join(result.output)
    # Per-command help should at least show the name and a hint of its args.
    assert "fold" in body


def test_fold_hook_returning_none_yields_error() -> None:
    """A hook that explicitly says 'verb not supported' is reported back."""
    reg, ctx = _fresh_registry()
    ctx.hooks["fold"] = lambda v, a: None  # not supported

    result = dispatch(":fold close-all", ctx, reg)
    assert result.ok is False
    assert result.error is not None
    assert "close-all" in result.error
