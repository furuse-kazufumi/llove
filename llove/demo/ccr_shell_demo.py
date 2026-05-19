"""F23/F24 — Minimal PowerShell + ccr 起動 PoC (stand-alone Textual demo).

F23 (PowerShell 互換シェル) と F24 (Claude Code 統合) は本要件として
は計画段階で未実装. 本 demo は最小 PoC として:

1. Textual UI の中で subprocess 経由で PowerShell コマンドを実行
2. 出力を panel に流す
3. ``ccr`` (claude code) を起動するボタンを用意

PoC のため:
- 実 F23 の本格 shell 互換は無 (chdir / env propagation は単純化)
- 履歴管理 / vim mode / 補完は無
- 大規模実装は Phase 2-3 (要件 dogfooding-day0-gap.md 参照)

実行:
    py -3.11 -m llove.demo.ccr_shell_demo

bindings:
- Enter: コマンド実行
- Ctrl+C: clear output
- Ctrl+L: ccr (claude code) 起動 (subprocess を新ウィンドウで)
- q: quit
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static


class _OutputPane(Static):
    """コマンド実行結果を貯めるペイン."""

    def __init__(self) -> None:
        super().__init__("(no output yet — type a command and press Enter)")
        self.border_title = "PowerShell output"
        self._buf: list[str] = []

    DEFAULT_CSS = """
    _OutputPane {
        border: round $secondary;
        padding: 0 1;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def append(self, text: str) -> None:
        self._buf.append(text)
        # 直近 200 行だけ保持 (memory bounded)
        if len(self._buf) > 200:
            self._buf = self._buf[-200:]
        self.update("\n".join(self._buf))


class CcrShellDemoApp(App):
    """Minimal PoC for F23 PowerShell shell + F24 Claude Code launcher."""

    CSS = """
    Screen { background: $surface; }
    #cmd-row {
        height: 3;
        padding: 0 1;
    }
    #cmd-input { width: 1fr; }
    #status-bar {
        height: 1;
        padding: 0 2;
        background: $panel;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "clear_output", "Clear", show=True),
        Binding("ctrl+l", "launch_ccr", "Launch ccr", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    TITLE = "💗 llove — F23/F24 PoC"
    SUB_TITLE = "PowerShell shell + Claude Code launcher (skeleton)"

    def __init__(self) -> None:
        super().__init__()
        self._cwd = Path.cwd()
        self._output: _OutputPane | None = None
        self._status: Static | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            self._output = _OutputPane()
            yield self._output
            with Horizontal(id="cmd-row"):
                yield Input(
                    placeholder="powershell command (e.g. Get-ChildItem)",
                    id="cmd-input",
                )
            self._status = Static(f"cwd: {self._cwd}", id="status-bar")
            yield self._status
        yield Footer()

    def on_mount(self) -> None:
        if self._output is not None:
            self._output.append("$ # llove F23/F24 PoC — type a PowerShell command below")
            self._output.append(f"$ # cwd: {self._cwd}")
            self._output.append("$ # Ctrl+L で ccr (claude code) を新ウィンドウで起動")

    def _run_powershell(self, cmd: str) -> None:
        assert self._output is not None
        # list-based subprocess (shell=False) で安全に実行.
        # PowerShell 7+ (pwsh) が優先、なければ Windows PowerShell.
        ps = shutil.which("pwsh") or shutil.which("powershell")
        if ps is None:
            self._output.append("✗ PowerShell not found in PATH")
            return
        self._output.append(f"$ {cmd}")
        try:
            proc = subprocess.run(
                [ps, "-NoProfile", "-NonInteractive", "-Command", cmd],
                cwd=str(self._cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if proc.stdout:
                self._output.append(proc.stdout.rstrip())
            if proc.stderr:
                self._output.append(f"[stderr] {proc.stderr.rstrip()}")
            if proc.returncode != 0:
                self._output.append(f"[exit code: {proc.returncode}]")
        except subprocess.TimeoutExpired:
            self._output.append("✗ command timed out (30s)")
        except FileNotFoundError as e:
            self._output.append(f"✗ {e}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if not cmd:
            return
        # 特例: cd <path> はアプリ内 cwd を更新 (subprocess の cwd は保持されない仕様の補完)
        if cmd.startswith("cd "):
            target = cmd[3:].strip().strip('"').strip("'")
            try:
                new_path = (self._cwd / target).resolve() if not Path(target).is_absolute() else Path(target).resolve()
                if new_path.is_dir():
                    self._cwd = new_path
                    if self._status is not None:
                        self._status.update(f"cwd: {self._cwd}")
                    if self._output is not None:
                        self._output.append(f"$ cd {new_path}")
                else:
                    if self._output is not None:
                        self._output.append(f"✗ not a directory: {new_path}")
            except Exception as e:  # noqa: BLE001
                if self._output is not None:
                    self._output.append(f"✗ cd failed: {e}")
        else:
            self._run_powershell(cmd)
        # クリア入力フィールド
        event.input.value = ""

    def action_clear_output(self) -> None:
        if self._output is not None:
            self._output._buf.clear()  # noqa: SLF001
            self._output.update("(cleared)")

    def action_launch_ccr(self) -> None:
        """ccr (claude code) を新ウィンドウで起動する.

        Windows なら ``start cmd /k claude`` 相当. Linux/Mac なら別ターミナル.
        本 demo は最小実装で Windows のみ.
        """
        assert self._output is not None
        # claude (ccr) の在処
        ccr = shutil.which("claude") or shutil.which("ccr") or shutil.which("ccm")
        if ccr is None:
            self._output.append(
                "✗ claude / ccr / ccm not found in PATH. "
                "Install Claude Code (https://claude.com/claude-code) and ensure it's on PATH."
            )
            return
        try:
            if sys.platform == "win32":
                # 新 cmd ウィンドウで claude を起動
                subprocess.Popen(
                    ["cmd", "/c", "start", "cmd", "/k", ccr],
                    cwd=str(self._cwd),
                )
                self._output.append(f"✓ launched ccr in new window: {ccr} (cwd={self._cwd})")
            else:
                # 簡易: 同じ端末で start (Linux/Mac は別ターミナル起動が environment 依存)
                subprocess.Popen([ccr], cwd=str(self._cwd))
                self._output.append(f"✓ launched ccr in background: {ccr}")
        except Exception as e:  # noqa: BLE001
            self._output.append(f"✗ failed to launch ccr: {e}")


def main() -> int:
    CcrShellDemoApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
