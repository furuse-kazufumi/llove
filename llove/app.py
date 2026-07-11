"""LoveApp — the Textual application that hosts panes and feeds them events."""

from __future__ import annotations

import asyncio
import contextlib
import os
from pathlib import Path
from typing import TextIO

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Static

from llove.events import Event, EventKind
from llove.i18n import t
from llove.identity import load_local_identity
from llove.llm import (
    KNOWN_PROVIDERS,
    HttpTransport,
    LLMConfig,
    LLMConfigError,
    parse_llm_spec,
)
from llove.sources.base import DataSource
from llove.term.choice import ChoiceOption, ChoicePrompt
from llove.term.choice_screen import ChoiceScreen
from llove.term.command import Command, CommandContext, CommandRegistry, CommandResult
from llove.term.palette import CommandPaletteScreen
from llove.views.audit_log import AuditLogView
from llove.views.base import View
from llove.views.llive.cognitive_mesh_panel import CognitiveMeshPanel
from llove.views.narration import NarrationView
from llove.views.sensor_stream import SensorStreamView
from llove.views.spc_chart import SPCChartView

# M8.1 LoveApp 統合 — env=1 で CognitiveMeshPanel を attach.
# 既定無効 (LoveApp の既存 layout は破壊しない).
ENV_ENABLE_COG_MESH = "LLOVE_ENABLE_COG_MESH"

# ---------------------------------------------------------------------------
# F20(k) `:peer` — llove.llm 実配線の純粋レゾルバ
# ---------------------------------------------------------------------------

#: 未設定プロバイダを選ぼうとしたとき案内する環境変数名 (キー値は表示しない).
_PEER_ENV_HINTS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "llmesh": "LLMESH_PEER_URL",
}


def resolve_peer_command(
    args: list[str],
    config: LLMConfig,
    current_spec: str | None = None,
) -> tuple[bool, tuple[str, ...], str | None]:
    """`:peer` 1 回分を *config* に対して解決する純関数 (I/O・ネットワークなし).

    戻り値は ``(ok, lines, new_spec)``:

    - ``ok``       成功 / fail-closed 失敗
    - ``lines``    人間可読メッセージ (``ok=False`` では先頭行がエラー本文)
    - ``new_spec`` 保存すべき新しい peer spec。選択が config 検証を通った
      ときのみ非 ``None`` — 失敗時は絶対に選択を変えない (fail-closed)。

    検証は **config レベルのみ** (env が静的に揃っているか)。endpoint への
    疎通テストはしない — 到達可能性は実際に呼んで初めて分かる (honest)。
    秘密情報は表示しない: API キーは ``api_key=yes/no`` の真偽だけ。
    """
    if not args:
        lines: list[str] = [
            f"peer: {current_spec}" if current_spec else "peer: (未選択)",
            "available providers: " + ", ".join(config.available_providers()),
        ]
        for provider in KNOWN_PROVIDERS:
            st = config.status(provider)
            mark = "✓" if st.configured else "✗"
            lines.append(
                f"  {mark} {st.provider}: {st.reason}"
                f" (api_key={'yes' if st.has_api_key else 'no'})"
            )
        lines.append("select: :peer <provider:model> (例: :peer ollama:llama3.2)")
        return True, tuple(lines), None

    if len(args) > 1:
        return False, ("usage: :peer [<provider:model>]",), None

    try:
        provider, model = parse_llm_spec(args[0])
    except LLMConfigError as exc:
        # 未知 provider — parse_llm_spec のメッセージが known 一覧と例を含む.
        return False, (str(exc),), None

    status = config.status(provider)
    if not status.configured:
        # fail-closed: 保存せず, 有効化に必要な環境変数を案内する.
        failure = [f"{provider} is not configured: {status.reason}"]
        hint = _PEER_ENV_HINTS.get(provider)
        if hint:
            failure.append(f"ヒント: 環境変数 {hint} を設定すると {provider} を選択できます")
        return False, tuple(failure), None

    spec = f"{provider}:{model}"
    return True, (f"peer set: {spec}",), spec


class LoveApp(App):
    """Multi-pane Textual app for llove.

    Default layout (top → bottom):
        Header  (auto title + clock)
        Control row  (clickable Pause / Reset / Help / Quit buttons)
        Top row      SensorStream | SPCChart  (read-only displays)
        Audit log row                          (read-only display)
        Narration row (optional, when running a scenario)
        Footer  (keybinding hints; clicking a hint invokes the action)
    """

    CSS = """
    Screen {
        background: $surface;
    }
    #control-row {
        height: 3;
        padding: 0 1;
        background: $boost;
    }
    #control-row Button {
        margin: 0 1;
        min-width: 12;
    }
    #hint-bar {
        height: 1;
        padding: 0 2;
        background: $panel;
        color: $text-muted;
    }
    .top-row {
        height: 1fr;
    }
    """

    BINDINGS = [  # noqa: RUF012 — Textual reads BINDINGS as a class-level list, not per-instance.
        ("q", "quit", "Quit"),
        ("r", "reset", "Reset views"),
        ("space", "toggle_pause", "Pause/Resume"),
        ("h", "show_help", "Help"),
        (":", "command_palette", "Command Palette"),
    ]

    TITLE = "💗 llove"
    SUB_TITLE = "Made with llove"

    def __init__(
        self,
        source: DataSource,
        *,
        with_narration: bool = False,
        log_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._source = source
        self._views: list[View] = []
        self._paused = False
        self._task: asyncio.Task[None] | None = None
        self._with_narration = with_narration
        # Optional event-log path. When set, every dispatched Event is
        # appended as a JSON line so the run can be replayed with
        # `llove tail` (and serves as a permanent record — e.g. a full
        # shogi kifu).
        self._log_path = log_path
        self._log_file: TextIO | None = None
        # Pull localised app subtitle so it changes with --lang.
        self.sub_title = t("ui.subtitle")
        # M8.1 — optional Cognitive Mesh panel (env-gated, off by default).
        self._cog_mesh_enabled = os.environ.get(ENV_ENABLE_COG_MESH, "") == "1"
        self._cog_mesh_panel: CognitiveMeshPanel | None = None
        # Command Palette backing store, built once on first ':' so aliases /
        # macros / vars persist across opens (None until then).
        self._cmd_registry: CommandRegistry | None = None
        self._cmd_ctx: CommandContext | None = None
        # F20(k) — `:peer` で選択された LLM peer spec ("provider:model")。
        # config 検証を通った選択のみ保存される (fail-closed)。`:peer` の
        # 表示や将来のゲーム / シナリオ連携 (make_client) がここを参照する。
        self.active_peer_spec: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Explicit control row — these are obviously clickable, distinguishing
        # them from the read-only display panes below.
        with Horizontal(id="control-row"):
            self._btn_pause = Button(t("ui.button.pause"), id="btn-pause", variant="primary")
            self._btn_reset = Button(t("ui.button.reset"), id="btn-reset", variant="warning")
            yield self._btn_pause
            yield self._btn_reset
            yield Button(t("ui.button.help"), id="btn-help", variant="default")
            yield Button(t("ui.button.quit"), id="btn-quit", variant="error")
        # Hint bar makes the read/write split unambiguous at a glance.
        yield Static(t("ui.hint_bar"), id="hint-bar")
        with Vertical():
            with Horizontal(classes="top-row"):
                self._sensor = SensorStreamView()
                self._spc = SPCChartView()
                yield self._sensor
                yield self._spc
            self._audit = AuditLogView()
            yield self._audit
            # M8.1 — Cognitive Mesh panel (env-gated, audit log の下).
            # 既定無効. LLOVE_ENABLE_COG_MESH=1 で有効化.
            if self._cog_mesh_enabled:
                self._cog_mesh_panel = CognitiveMeshPanel()
                yield self._cog_mesh_panel
            self._narration: NarrationView | None = None
            if self._with_narration:
                self._narration = NarrationView()
                yield self._narration
        yield Footer()
        self._views = [self._sensor, self._spc, self._audit]
        if self._cog_mesh_panel is not None:
            self._views.append(self._cog_mesh_panel)
        if self._narration is not None:
            self._views.append(self._narration)

    async def on_mount(self) -> None:
        # Open the event log up-front (append) so every dispatched event is
        # captured. We close it on unmount.
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = self._log_path.open("a", encoding="utf-8")

        # llove is, first and foremost, a TUI window onto **llmesh**. Every
        # run opens with a verifiable "this came from peer:…" AUDIT line so
        # the user sees the identity story before the first sensor tick.
        # When no identity is reachable, we still fire an AUDIT — with copy
        # that nudges the user toward installing the llmesh SDK.
        self._emit_identity_event()

        # If the source is a DemoScenario, let it rename pane titles and
        # reshape the narration pane so that non-LLMesh-flavoured demos
        # (coin_toss, shogi, …) don't have to fit the LLMesh template.
        from collections import deque

        from llove.demo.scenarios.base import DemoScenario

        if isinstance(self._source, DemoScenario):
            s = self._source
            if s.sensor_pane_title_key:
                self._sensor.border_title = t(s.sensor_pane_title_key)
            if s.spc_pane_title_key:
                self._spc.border_title = t(s.spc_pane_title_key)
            if s.audit_pane_title_key:
                self._audit.border_title = t(s.audit_pane_title_key)
            if s.narration_pane_title_key and self._narration is not None:
                self._narration.border_title = t(s.narration_pane_title_key)
            if self._narration is not None:
                # Resize the narration pane (e.g. shogi needs ~28 rows for
                # a 9x9 board) and shrink its scrollback so the *latest*
                # board is never pushed off-screen by older snapshots.
                if s.narration_pane_height:
                    self._narration.styles.height = s.narration_pane_height
                if s.narration_max_entries:
                    self._narration._entries = deque(
                        self._narration._entries,
                        maxlen=s.narration_max_entries,
                    )
            # Audit pane reshape: shogi keeps the full kifu visible.
            if s.audit_pane_height:
                self._audit.styles.height = s.audit_pane_height
            if s.audit_max_entries:
                self._audit._rows = deque(
                    self._audit._rows,
                    maxlen=s.audit_max_entries,
                )

        # Interactive scenarios get an asker injected so their choice-points can
        # prompt the user and branch. Non-interactive sources are untouched.
        self._wire_interactive_asker()
        self._task = asyncio.create_task(self._consume())

    def _wire_interactive_asker(self) -> None:
        """Give an InteractiveScenario source a handle to prompt the user.

        Idempotent and isinstance-guarded, so non-interactive sources (JSONL
        tail, mock, every existing demo) are left exactly as they were.
        """
        from llove.demo.scenarios.interactive import InteractiveScenario

        if isinstance(self._source, InteractiveScenario):
            self._source._asker = self.ask_choice

    async def ask_choice(
        self,
        prompt: str,
        options: list[ChoiceOption],
        *,
        default_id: str | None = None,
    ) -> str:
        """Present an interactive choice-point and return the chosen option id.

        This is the ``ChoiceAsker`` injected into InteractiveScenario sources.
        It pushes a ``ChoiceScreen`` modal and resolves a Future from the
        screen's dismiss callback — so we never need a Textual worker context.
        Escape / dismissing with ``None`` falls back to the prompt's resolved
        default, keeping the flow deterministic. The decision is recorded as an
        AUDIT event so a ``--log`` JSONL replays the exact path taken.
        """
        cp = ChoicePrompt(prompt=prompt, options=tuple(options), default_id=default_id)
        future: asyncio.Future[str] = asyncio.get_running_loop().create_future()

        def _on_dismiss(result: str | None) -> None:
            if not future.done():
                future.set_result(result if result is not None else cp.resolved_default)

        self.push_screen(ChoiceScreen(cp), _on_dismiss)
        chosen = await future

        opt = cp.option(chosen)
        label = opt.label if opt is not None else chosen
        self._dispatch(
            Event(
                kind=EventKind.AUDIT,
                source_id="llove.choice",
                payload={
                    "event": "llove.choice",
                    "prompt": prompt,
                    "chosen": chosen,
                    "chosen_label": label,
                    "options": [o.id for o in options],
                    "display": t("ui.choice.audit", label=label),
                },
            )
        )
        return chosen

    async def on_unmount(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        if self._log_file is not None:
            try:
                self._log_file.close()
            finally:
                self._log_file = None
        await self._source.close()

    async def _consume(self) -> None:
        try:
            async for ev in self._source.stream():
                if self._paused:
                    continue
                self._dispatch(ev)
        except asyncio.CancelledError:
            return

    def _emit_identity_event(self) -> None:
        """First event of every run: the local llmesh node identity.

        We always fire something — either the resolved did:key, or a friendly
        "install llmesh-mcp to get one" line. That way the audit pane and the
        JSONL log both *start* with an identity story, no matter the scenario.
        """
        identity = load_local_identity()
        if identity is not None:
            payload: dict[str, object] = dict(identity.to_audit_payload())
        else:
            payload = {
                "event": "llove.identity.missing",
                "did": None,
                "display": t("ui.identity.missing"),
            }
        self._dispatch(Event(
            kind=EventKind.AUDIT,
            source_id="llove.identity",
            payload=payload,
        ))

    def _dispatch(self, event: Event) -> None:
        if self._log_file is not None:
            try:
                self._log_file.write(event.model_dump_json() + "\n")
                self._log_file.flush()
            except Exception:  # nosec B110 — fail-closed: a broken log must not kill the app.
                pass
        for v in self._views:
            try:
                v.feed(event)
            except Exception:  # nosec B110 — fail-closed: a broken view must not kill the app.
                continue

    def action_reset(self) -> None:
        # Reset = "play the scenario from the beginning". Cancel the current
        # consume task, clear every view, then for DemoScenarios re-instantiate
        # the source and start a fresh consume task so the game / demo plays
        # again from ply 1.
        from llove.demo.scenarios.base import DemoScenario

        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None

        self._clear_views()

        # Restart the source from scratch *only* for DemoScenarios — they
        # are stateless apart from their event generator, which is what we
        # want to re-roll. For arbitrary DataSource subclasses (JSONL tail,
        # custom test sources) we leave the existing instance alone and
        # do not start a new consume task: re-reading those is the caller's
        # responsibility, not Reset's.
        self._paused = False
        if hasattr(self, "_btn_pause"):
            self._btn_pause.label = t("ui.button.pause")
        if isinstance(self._source, DemoScenario):
            # Truncate the event log (if any) so the new run starts a fresh
            # record. Without this, Reset would keep appending the second
            # game underneath the first in the same .jsonl file — confusing
            # for shogi where the file is meant to be the kifu of *one* game.
            if self._log_file is not None and self._log_path is not None:
                # fail-closed: a broken log close must not kill reset.
                with contextlib.suppress(Exception):
                    self._log_file.close()
                self._log_file = self._log_path.open("w", encoding="utf-8")
            self._source = self._source.__class__()
            self._wire_interactive_asker()
            self._task = asyncio.create_task(self._consume())

    def action_toggle_pause(self) -> None:
        self._paused = not self._paused
        # Keep the visible button label in sync so users see the new state.
        if hasattr(self, "_btn_pause"):
            self._btn_pause.label = t("ui.button.resume") if self._paused else t("ui.button.pause")

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def _clear_views(self) -> None:
        """Clear the rolling state of every pane and redraw its empty state."""
        for v in self._views:
            if hasattr(v, "_rows"):
                v._rows.clear()
            if hasattr(v, "_alarms"):
                v._alarms.clear()
            if hasattr(v, "_entries"):
                v._entries.clear()
            if hasattr(v, "_values"):
                v._values.clear()
            if hasattr(v, "_count"):
                v._count = 0
            if hasattr(v, "_alarm_count"):
                v._alarm_count = 0
            if hasattr(v, "_beats"):
                v._beats = 0
            if hasattr(v, "_counts") and isinstance(v._counts, dict):
                for k in list(v._counts):
                    v._counts[k] = 0
            # Force a redraw of empty state.
            if hasattr(v, "update"):
                empty = getattr(v, "_initial", None)
                if empty is None:
                    empty = "(reset)"
                try:
                    v.update(empty)
                except Exception:  # nosec B110 — fail-closed: a broken redraw must not kill the app.
                    continue

    def _load_source(self, source: DataSource) -> None:
        """Swap the running data source — the Command Palette 'cartridge loader'.

        Cancels the current consume loop, clears the panes, installs the new
        source, re-wires the interactive asker, and starts consuming again. The
        panes are fixed at mount time, so a scenario's narration only shows when
        the app already has a narration pane (true for ``llove demo --scenario``).
        """
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        self._clear_views()
        self._paused = False
        if hasattr(self, "_btn_pause"):
            self._btn_pause.label = t("ui.button.pause")
        # Truncate the event log so the new run starts a fresh record.
        if self._log_file is not None and self._log_path is not None:
            with contextlib.suppress(Exception):
                self._log_file.close()
            self._log_file = self._log_path.open("w", encoding="utf-8")
        self._source = source
        self._wire_interactive_asker()
        self._task = asyncio.create_task(self._consume())

    def action_command_palette(self) -> None:
        registry, ctx = self._command_palette_context()
        self.push_screen(CommandPaletteScreen(registry=registry, ctx=ctx))

    def _command_palette_context(self) -> tuple[CommandRegistry, CommandContext]:
        """Build (once) the registry + context backing the ':' palette.

        Without this the palette opens with an empty registry, so ``:help``
        errors and every command is inert. Here we register the builtins and
        bind the hooks that genuinely work (help / demo / play / theme /
        identity / peer); the rest (``:open`` / ``:fold`` / ``:layout``)
        keep their honest "not wired yet" responses. ``:peer`` is re-registered
        with the real ``llove.llm``-backed handler (config-level validation,
        fail-closed, no network).
        """
        if self._cmd_registry is not None and self._cmd_ctx is not None:
            return self._cmd_registry, self._cmd_ctx
        from llove.term.builtins import make_default_context, register_builtins

        registry = CommandRegistry()
        register_builtins(registry)
        ctx = make_default_context(registry)  # binds the 'registry' hook for :help
        # :identity — real did:key when an llmesh identity is present.
        identity = load_local_identity()
        if identity is not None and getattr(identity, "did_key", None):
            ctx.hooks["identity_did"] = identity.did_key
        # :theme — wire to Textual's own theme machinery.
        ctx.hooks["get_theme"] = lambda: self.theme
        ctx.hooks["list_themes"] = lambda: sorted(getattr(self, "available_themes", {}))
        ctx.hooks["set_theme"] = self._set_app_theme
        # cartridge loaders: :demo <name> / :play <game> <p1> <p2>.
        ctx.hooks["start_demo"] = self._start_demo
        ctx.hooks["start_game"] = self._start_game
        # :peer — llove.llm 実配線 (builtins の "hook 未配線" handler を置換)。
        registry.unregister("peer")
        registry.register(
            Command(
                name="peer",
                handler=self._cmd_peer,
                summary="LLM peer 表示 / 選択 (config 検証のみ, 疎通テストなし)",
                args_hint="[<provider:model>]",
                category="llmesh",
            )
        )
        self._cmd_registry = registry
        self._cmd_ctx = ctx
        return registry, ctx

    def _set_app_theme(self, name: str) -> None:
        # Textual validates the name and raises on an unknown theme; the
        # command handler turns that into a friendly error.
        self.theme = name

    def _cmd_peer(self, args: list[str], ctx: CommandContext) -> CommandResult:
        """`:peer` — LLM peer の表示 / 選択 (F20(k) 実配線).

        検証は :func:`resolve_peer_command` (純関数) に委譲し, ここは
        ``active_peer_spec`` への保存と ``CommandResult`` への変換だけ行う.
        config は毎回 env から読み直す — セッション中に環境変数を整えた
        直後の `:peer` がすぐ反映されるように。
        """
        ok, lines, new_spec = resolve_peer_command(
            args, LLMConfig.from_env(), self.active_peer_spec
        )
        if ok and new_spec is not None:
            self.active_peer_spec = new_spec
        if ok:
            return CommandResult(ok=True, output=lines)
        error = lines[0] if lines else "peer command failed"
        return CommandResult(ok=False, error=error, output=lines[1:])

    def _start_demo(self, name: str) -> None:
        """`:demo <name>` — load a demo scenario into the running app."""
        from llove.demo.scenarios import get_scenario

        self._load_source(get_scenario(name))  # ValueError on unknown -> handler reports it

    def _start_game(self, game: str, p1: str, p2: str) -> None:
        """`:play <game> <p1> <p2>` — load a real game (shogi today)."""
        if game != "shogi":
            raise ValueError(f"unsupported game: {game!r} (only 'shogi' is available)")
        try:
            from llove.shogi import make_player
            from llove.shogi.source import ShogiSource
        except ImportError as exc:  # python-shogi not installed
            raise RuntimeError(
                f"shogi engine unavailable: {exc}; install: pip install 'llmesh-llove[shogi]'"
            ) from exc
        sente = make_player(p1, side="sente")
        gote = make_player(p2, side="gote")
        self._load_source(ShogiSource(sente, gote))

    def action_quit_now(self) -> None:
        """Synchronous quit so it can be wired from Button.Pressed."""
        self.exit()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Wire the top-row buttons to the same actions as the keybindings."""
        action_by_id = {
            "btn-pause": self.action_toggle_pause,
            "btn-reset": self.action_reset,
            "btn-help": self.action_show_help,
            "btn-quit": self.action_quit_now,
        }
        handler = action_by_id.get(event.button.id or "")
        if handler is not None:
            handler()


class HelpScreen(ModalScreen):
    """Modal overlay shown when the user clicks Help or presses 'h'."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > #help-box {
        width: 70;
        max-height: 80%;
        background: $boost;
        border: heavy $primary;
        padding: 1 2;
    }
    HelpScreen #help-close {
        margin-top: 1;
    }
    """

    BINDINGS = [  # noqa: RUF012 — Textual reads BINDINGS as a class-level list, not per-instance.
        ("escape", "dismiss", "Close"),
        ("h", "dismiss", "Close"),
        ("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="help-box"):
            yield Static(t("ui.help.title"))
            yield Static(t("ui.help.body"))
            yield Button(t("ui.help.close"), id="help-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "help-close":
            self.dismiss()
