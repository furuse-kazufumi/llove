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
from llove.term.choice import (
    ChoiceAsker,
    ChoiceOption,
    ChoicePrompt,
    make_prompt,
    render_choice,
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
from llove.term.completion import (
    HistoryRing,
    complete_prefix,
    filter_suggestions,
)


def __getattr__(name: str):  # PEP 562 lazy import
    """UI widget は Textual を import するため遅延ロード.

    UI 非依存層 (command / completion / builtins) をテストする時に
    Textual を巻き込まないために, ``CommandPaletteWidget`` /
    ``CommandPaletteScreen`` は最初の参照時に遅延 import する.
    """
    if name in {"CommandPaletteWidget", "CommandPaletteScreen"}:
        from llove.term import palette as _palette

        return getattr(_palette, name)
    if name == "ChoiceScreen":
        from llove.term import choice_screen as _choice_screen

        return _choice_screen.ChoiceScreen
    raise AttributeError(f"module 'llove.term' has no attribute {name!r}")


__all__ = [
    "DEFAULT_REGISTRY",
    "ChoiceAsker",
    "ChoiceOption",
    "ChoicePrompt",
    "ChoiceScreen",
    "Command",
    "CommandContext",
    "CommandHandler",
    "CommandPaletteScreen",
    "CommandPaletteWidget",
    "CommandRegistry",
    "CommandResult",
    "HistoryRing",
    "ParsedLine",
    "builtin_commands",
    "complete_prefix",
    "dispatch",
    "filter_suggestions",
    "make_default_context",
    "make_prompt",
    "parse_line",
    "register_builtins",
    "register_command",
    "render_choice",
]
