"""F20(c) Command Palette — Command ABC + Registry + dispatch.

責務:

- ``Command`` データクラス (name / summary / args_hint / category / handler)
- ``CommandRegistry`` (登録 / 取得 / 列挙 / fuzzy 提案)
- ``parse_line`` (``:`` 接頭辞除去 + shlex 分割)
- ``dispatch`` (line -> CommandResult)
- ``CommandContext`` (aliases / macros / vars / 任意フック)

UI (Textual ``Input`` widget) は別ファイルで F20(c)③ として後実装.
このモジュールは UI 非依存で純粋関数として完結し、テスト容易.

設計参照:
- F17(m)(n) WindowType Registry の型・命名を踏襲
- F20(f) ``register_command`` で動的追加
- F20(g) alias / macro
- F20(i) fail-closed: 未知コマンドは ok=False + suggested 候補
"""

from __future__ import annotations

import difflib
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


CommandCategory = str  # "core" / "window" / "game" / "identity" / "demo" / ...


@dataclass(frozen=True)
class CommandResult:
    """1 コマンド実行の結果. ok=False は致命ではなく, UI 側は赤字表示する想定."""

    ok: bool
    output: tuple[str, ...] = ()
    error: str | None = None
    suggested: tuple[str, ...] = ()  # F20(i) 似たコマンド名候補


@dataclass
class CommandContext:
    """ハンドラに渡される実行コンテキスト.

    UI / WindowManager / Identity / LLMesh peer 等のフックは optional.
    最小骨組み段階ではすべて差し替え可能な field として持つだけで良い.
    """

    aliases: dict[str, str] = field(default_factory=dict)
    macros: dict[str, tuple[str, ...]] = field(default_factory=dict)
    vars: dict[str, str] = field(default_factory=dict)
    # 後段で WindowManager / Identity / LLMesh peer を差し込む slot.
    hooks: dict[str, Any] = field(default_factory=dict)


CommandHandler = Callable[[list[str], CommandContext], CommandResult]


@dataclass(frozen=True)
class Command:
    """1 コマンドの定義.

    ``name`` は ``:`` を含めない素の名前 ("help" / "identity" / "play"),
    ``args_hint`` はユーザ補助用 (`<game> <p1> <p2>` のような表記),
    ``category`` は F20(d) Help カテゴリ分け用.
    """

    name: str
    handler: CommandHandler
    summary: str = ""
    args_hint: str = ""
    category: CommandCategory = "core"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class CommandRegistry:
    """グローバル / ローカル両用の Registry.

    F17 の WindowType と同様, モジュールレベルでは ``DEFAULT_REGISTRY`` を
    1 つ用意し, テストや plugin で独立した Registry を作りたい場合は
    インスタンス化して使える.
    """

    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        if not command.name:
            raise ValueError("Command.name must be non-empty")
        if command.name in self._commands:
            raise ValueError(f"command already registered: {command.name!r}")
        self._commands[command.name] = command

    def unregister(self, name: str) -> None:
        self._commands.pop(name, None)

    def get(self, name: str) -> Command | None:
        return self._commands.get(name)

    def list(self, *, category: CommandCategory | None = None) -> list[Command]:
        items = list(self._commands.values())
        if category is not None:
            items = [c for c in items if c.category == category]
        return sorted(items, key=lambda c: (c.category, c.name))

    def names(self) -> list[str]:
        return sorted(self._commands)

    def suggest(self, name: str, *, n: int = 3) -> list[str]:
        """F20(i) 未知コマンド入力時の近似候補. difflib のラッパ."""
        return difflib.get_close_matches(name, self._commands, n=n, cutoff=0.5)

    def clear(self) -> None:
        self._commands.clear()


DEFAULT_REGISTRY = CommandRegistry()


def register_command(command: Command) -> None:
    """F20(f) plugin / script 向けの公開 API."""
    DEFAULT_REGISTRY.register(command)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedLine:
    name: str
    args: tuple[str, ...]


def parse_line(line: str) -> ParsedLine | None:
    """``:foo bar baz`` -> ParsedLine("foo", ("bar", "baz")).

    - 先頭の任意の空白と任意の単一 ``:`` を剥がす (Vim ex 風).
    - shlex でクォート対応分割 (``:set msg="hello world"`` 用).
    - 空入力 / ``:`` のみは None.
    - パース失敗 (未閉じクォート等) も None — caller 側でエラー化する.
    """
    stripped = line.strip()
    if not stripped:
        return None
    if stripped.startswith(":"):
        stripped = stripped[1:].lstrip()
    if not stripped:
        return None
    try:
        parts = shlex.split(stripped, posix=True)
    except ValueError:
        return None
    if not parts:
        return None
    return ParsedLine(name=parts[0], args=tuple(parts[1:]))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def dispatch(
    line: str,
    ctx: CommandContext,
    registry: CommandRegistry | None = None,
    *,
    _depth: int = 0,
) -> CommandResult:
    """F20(b) コマンド 1 行を実行する中核.

    解決順:
        1. parse_line で名前と引数を取り出す
        2. ctx.aliases に短縮形があれば実体に差し替え (1 段だけ)
        3. ctx.macros にあれば各行を再帰 dispatch (深さ 5 まで暴走防止)
        4. registry に登録された Command を呼ぶ
        5. 該当なし -> 似た名前を suggest して ok=False
    """
    reg = registry or DEFAULT_REGISTRY

    if _depth > 5:
        return CommandResult(
            ok=False,
            error=f"macro / alias 解決の入れ子が深すぎます (>{_depth - 1})",
        )

    parsed = parse_line(line)
    if parsed is None:
        return CommandResult(ok=False, error="入力が空または quote が閉じていません")

    # alias 展開 (1 段). 名前だけ置換し, 残りの args はそのまま結合.
    if parsed.name in ctx.aliases:
        replacement = ctx.aliases[parsed.name]
        # alias は ":" 付きで保存されてもしなくても許容
        if replacement.startswith(":"):
            replacement = replacement[1:]
        new_line = replacement
        if parsed.args:
            new_line += " " + shlex.join(parsed.args)
        return dispatch(new_line, ctx, reg, _depth=_depth + 1)

    # macro 展開 (各行を順に dispatch, 失敗で stop)
    if parsed.name in ctx.macros:
        outputs: list[str] = []
        for sub in ctx.macros[parsed.name]:
            sub_result = dispatch(sub, ctx, reg, _depth=_depth + 1)
            outputs.extend(sub_result.output)
            if not sub_result.ok:
                return CommandResult(
                    ok=False,
                    output=tuple(outputs),
                    error=(f"macro {parsed.name!r} が {sub!r} で停止: {sub_result.error}"),
                )
        return CommandResult(ok=True, output=tuple(outputs))

    cmd = reg.get(parsed.name)
    if cmd is None:
        return CommandResult(
            ok=False,
            error=f"unknown command: :{parsed.name}",
            suggested=tuple(reg.suggest(parsed.name)),
        )
    return cmd.handler(list(parsed.args), ctx)


__all__ = [
    "DEFAULT_REGISTRY",
    "Command",
    "CommandContext",
    "CommandHandler",
    "CommandRegistry",
    "CommandResult",
    "ParsedLine",
    "dispatch",
    "parse_line",
    "register_command",
]
