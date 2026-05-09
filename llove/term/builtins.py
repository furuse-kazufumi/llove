"""F20(b) ビルトインコマンド群.

最小骨組み段階では各コマンドは「正しく解釈・引数検証して
``CommandResult.output`` に説明的メッセージを返す」レベルに留め, 実際の
WindowManager / Identity / LLMesh peer / DemoScenario への副作用配線は
``CommandContext.hooks`` に差し込み可能な形で空にしておく.

UI / WindowManager / Identity が成熟したら各 handler が ``ctx.hooks`` から
取り出して呼び出すだけで本物に昇格できる構造.
"""

from __future__ import annotations

import shlex

from llove.term.command import (
    Command,
    CommandContext,
    CommandRegistry,
    CommandResult,
)

# ---------------------------------------------------------------------------
# Help / 情報系
# ---------------------------------------------------------------------------


def _cmd_help(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:help [name]` — 全コマンド一覧 / 個別ヘルプ."""
    reg: CommandRegistry = ctx.hooks.get("registry")  # type: ignore[assignment]
    if reg is None:
        return CommandResult(ok=False, error="registry hook 未設定 (内部エラー)")

    if args:
        target = args[0].lstrip(":")
        cmd = reg.get(target)
        if cmd is None:
            return CommandResult(
                ok=False,
                error=f"unknown command: :{target}",
                suggested=tuple(reg.suggest(target)),
            )
        lines = [
            f":{cmd.name}  {cmd.args_hint}".rstrip(),
            f"  category: {cmd.category}",
            f"  {cmd.summary}" if cmd.summary else "",
        ]
        return CommandResult(ok=True, output=tuple(line for line in lines if line))

    # 一覧モード — category ごとに 1 行
    lines: list[str] = []
    by_cat: dict[str, list[Command]] = {}
    for c in reg.list():
        by_cat.setdefault(c.category, []).append(c)
    for category in sorted(by_cat):
        names = " ".join(f":{c.name}" for c in by_cat[category])
        lines.append(f"[{category}] {names}")
    return CommandResult(ok=True, output=tuple(lines))


def _cmd_identity(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:identity` — 現ノード did:key を表示 (hook で実値, 無ければ案内)."""
    if args:
        return CommandResult(ok=False, error=":identity は引数を取りません")
    did = ctx.hooks.get("identity_did")
    if did is None:
        return CommandResult(
            ok=True,
            output=(
                "did:key: (未設定)",
                "ヒント: pip install llmesh-mcp で識別子取得",
            ),
        )
    return CommandResult(ok=True, output=(f"did:key: {did}",))


# ---------------------------------------------------------------------------
# Layout / Demo / Game (副作用配線は後段)
# ---------------------------------------------------------------------------


def _cmd_layout(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:layout <preset>` — レイアウトプリセット切替 (F17(p) と接続予定)."""
    if not args:
        return CommandResult(ok=False, error="usage: :layout <preset>")
    preset = args[0]
    apply = ctx.hooks.get("apply_layout")
    if callable(apply):
        try:
            apply(preset)
        except Exception as e:
            return CommandResult(ok=False, error=f"layout 切替失敗: {e}")
        return CommandResult(ok=True, output=(f"layout 切替: {preset}",))
    return CommandResult(
        ok=True,
        output=(f"layout '{preset}' を適用 (hook 未配線, 表示のみ)",),
    )


def _cmd_demo(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:demo <name>` — シナリオ起動 (CLI ``llove demo`` の内部口)."""
    if not args:
        return CommandResult(ok=False, error="usage: :demo <name>")
    name = args[0]
    start = ctx.hooks.get("start_demo")
    if callable(start):
        try:
            start(name)
        except Exception as e:
            return CommandResult(ok=False, error=f"demo 起動失敗: {e}")
        return CommandResult(ok=True, output=(f"demo 起動: {name}",))
    return CommandResult(ok=True, output=(f"demo '{name}' を起動 (hook 未配線, 表示のみ)",))


def _cmd_play(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:play <game> <p1> <p2>` — F16 対局起動."""
    if len(args) < 3:
        return CommandResult(ok=False, error="usage: :play <game> <p1> <p2>")
    game, p1, p2 = args[0], args[1], args[2]
    start = ctx.hooks.get("start_game")
    if callable(start):
        try:
            start(game, p1, p2)
        except Exception as e:
            return CommandResult(ok=False, error=f"対局起動失敗: {e}")
        return CommandResult(ok=True, output=(f"対局開始: {game} ({p1} vs {p2})",))
    return CommandResult(
        ok=True,
        output=(f"対局 '{game}' ({p1} vs {p2}) を開始 (hook 未配線)",),
    )


def _cmd_open(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:open <uri>` — F15 BrowserView で URI を開く."""
    if not args:
        return CommandResult(ok=False, error="usage: :open <uri>")
    uri = args[0]
    if "://" not in uri:
        return CommandResult(
            ok=False,
            error=f"URI scheme が必要: {uri!r} (例: image:///path)",
        )
    open_uri = ctx.hooks.get("open_uri")
    if callable(open_uri):
        try:
            open_uri(uri)
        except Exception as e:
            return CommandResult(ok=False, error=f"open 失敗: {e}")
        return CommandResult(ok=True, output=(f"open: {uri}",))
    return CommandResult(ok=True, output=(f"open '{uri}' (hook 未配線, 表示のみ)",))


def _cmd_peer(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:peer <NodeID> [verb]` — F20(k) llmesh peer 接続."""
    if not args:
        return CommandResult(ok=False, error="usage: :peer <NodeID> [verb]")
    node_id = args[0]
    verb = args[1] if len(args) > 1 else "info"
    peer_call = ctx.hooks.get("peer_call")
    if callable(peer_call):
        try:
            response = peer_call(node_id, verb)
        except Exception as e:
            return CommandResult(ok=False, error=f"peer 失敗: {e}")
        return CommandResult(ok=True, output=(f"peer {node_id} {verb} -> {response}",))
    return CommandResult(
        ok=True,
        output=(f"peer '{node_id}' {verb} (hook 未配線, 表示のみ)",),
    )


# ---------------------------------------------------------------------------
# Variable / Alias / Macro
# ---------------------------------------------------------------------------


def _cmd_set(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:set key=value` — ctx.vars に変数を保存."""
    if len(args) != 1 or "=" not in args[0]:
        return CommandResult(ok=False, error="usage: :set key=value")
    key, _, value = args[0].partition("=")
    if not key:
        return CommandResult(ok=False, error="key が空です")
    ctx.vars[key] = value
    return CommandResult(ok=True, output=(f"set {key}={value}",))


def _cmd_get(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:get [key]` — ctx.vars 1 件 / 全件表示."""
    if not args:
        if not ctx.vars:
            return CommandResult(ok=True, output=("(no vars)",))
        lines = [f"{k}={v}" for k, v in sorted(ctx.vars.items())]
        return CommandResult(ok=True, output=tuple(lines))
    key = args[0]
    if key not in ctx.vars:
        return CommandResult(ok=False, error=f"未定義: {key}")
    return CommandResult(ok=True, output=(f"{key}={ctx.vars[key]}",))


def _cmd_alias(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:alias <short> <long>` / 引数なしで一覧."""
    if not args:
        if not ctx.aliases:
            return CommandResult(ok=True, output=("(no aliases)",))
        lines = [f":{k} -> {v}" for k, v in sorted(ctx.aliases.items())]
        return CommandResult(ok=True, output=tuple(lines))
    if len(args) < 2:
        return CommandResult(ok=False, error="usage: :alias <short> <long...>")
    short, *rest = args
    long = " ".join(rest)
    ctx.aliases[short] = long
    return CommandResult(ok=True, output=(f"alias :{short} -> {long}",))


def _cmd_macro(args: list[str], ctx: CommandContext) -> CommandResult:
    """`:macro <name> <line1> ; <line2> ; ...` ; 区切りで複数行登録."""
    if not args:
        if not ctx.macros:
            return CommandResult(ok=True, output=("(no macros)",))
        lines = [f":{name} = " + " ; ".join(steps) for name, steps in sorted(ctx.macros.items())]
        return CommandResult(ok=True, output=tuple(lines))
    if len(args) < 2:
        return CommandResult(ok=False, error="usage: :macro <name> <line1> ; <line2> ...")
    name, *rest = args
    body = " ".join(rest)
    steps = tuple(s.strip() for s in body.split(";") if s.strip())
    if not steps:
        return CommandResult(ok=False, error="macro 本体が空です")
    ctx.macros[name] = steps
    return CommandResult(ok=True, output=(f"macro :{name} = {' ; '.join(steps)}",))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def builtin_commands() -> tuple[Command, ...]:
    """F20(b) ビルトインコマンドを返す. テストや別 Registry でも使える."""
    return (
        Command(
            name="help",
            handler=_cmd_help,
            summary="全コマンド一覧 / `:help <name>` で個別ヘルプ",
            args_hint="[name]",
            category="core",
        ),
        Command(
            name="identity",
            handler=_cmd_identity,
            summary="現ノードの did:key を表示",
            category="identity",
        ),
        Command(
            name="layout",
            handler=_cmd_layout,
            summary="F17 レイアウトプリセット切替",
            args_hint="<preset>",
            category="window",
        ),
        Command(
            name="demo",
            handler=_cmd_demo,
            summary="シナリオ起動 (`llove demo --scenario` の内部口)",
            args_hint="<name>",
            category="demo",
        ),
        Command(
            name="play",
            handler=_cmd_play,
            summary="F16 対局起動",
            args_hint="<game> <p1> <p2>",
            category="game",
        ),
        Command(
            name="open",
            handler=_cmd_open,
            summary="F15 BrowserView で URI を開く",
            args_hint="<uri>",
            category="viewer",
        ),
        Command(
            name="peer",
            handler=_cmd_peer,
            summary="llmesh peer 接続 (F20(k))",
            args_hint="<NodeID> [verb]",
            category="llmesh",
        ),
        Command(
            name="set",
            handler=_cmd_set,
            summary="変数設定 (ctx.vars)",
            args_hint="key=value",
            category="core",
        ),
        Command(
            name="get",
            handler=_cmd_get,
            summary="変数取得",
            args_hint="[key]",
            category="core",
        ),
        Command(
            name="alias",
            handler=_cmd_alias,
            summary="短縮コマンド登録",
            args_hint="[<short> <long>]",
            category="core",
        ),
        Command(
            name="macro",
            handler=_cmd_macro,
            summary="複数コマンド連鎖を登録 (`;` 区切り)",
            args_hint="[<name> <body>]",
            category="core",
        ),
    )


def register_builtins(registry: CommandRegistry) -> None:
    """与えられた Registry に F20(b) のビルトイン群を一括登録."""
    for cmd in builtin_commands():
        registry.register(cmd)


def make_default_context(registry: CommandRegistry) -> CommandContext:
    """Help が registry を参照するためのフックを仕込んだ既定 ctx."""
    ctx = CommandContext()
    ctx.hooks["registry"] = registry
    return ctx


# 内部ユーティリティ — alias 値が ":" を含まない場合にも quote-safe に
# 引数を再構成する shlex.join を使うのは command.py 側の責務.
__all__ = [
    "builtin_commands",
    "make_default_context",
    "register_builtins",
]


# 実行時 import 順で副作用を起こさないよう shlex を使用していることだけ宣言
_ = shlex  # 型チェッカに使用宣言
