"""``llove.term`` — F20 Command Palette 最小骨組み.

公開 API:

    from llove.term import (
        Command, CommandContext, CommandResult, CommandRegistry,
        DEFAULT_REGISTRY,
        register_command, dispatch, parse_line,
        builtin_commands, register_builtins, make_default_context,
    )

UI (Textual ``Input`` widget) は別段階で追加予定.
このパッケージは UI 非依存で純粋関数として完結する.
"""

from __future__ import annotations

from llove.term.builtins import (
    builtin_commands,
    make_default_context,
    register_builtins,
)
from llove.term.command import (
    DEFAULT_REGISTRY,
    Command,
    CommandContext,
    CommandHandler,
    CommandRegistry,
    CommandResult,
    ParsedLine,
    dispatch,
    parse_line,
    register_command,
)

__all__ = [
    "DEFAULT_REGISTRY",
    "Command",
    "CommandContext",
    "CommandHandler",
    "CommandRegistry",
    "CommandResult",
    "ParsedLine",
    "builtin_commands",
    "dispatch",
    "make_default_context",
    "parse_line",
    "register_builtins",
    "register_command",
]
