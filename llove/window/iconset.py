"""F17(s) IconSet — 動作環境別アイコン体系.

優先順 (検出順):
1. Sixel / Kitty graphics (実画像 SVG/PNG) — 最終モード、本実装は後日
2. **Nerd Font** ( / / / 等)
3. **絵文字** (📊 📋 💬 🔑 ♟ 等)
4. **ASCII** (`[D]` / `>>` / `*` 等、最終フォールバック)

論理 ID 文字列 (``"data.sensor_stream"`` / ``"game.board"`` 等) を
動作環境に応じて変換する. ``WindowType.id`` がそのままキー.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Literal


IconKind = Literal["nerd", "emoji", "ascii"]


class IconSet(ABC):
    """論理 ID → 表示文字列の変換テーブル."""

    kind: IconKind = "ascii"

    @abstractmethod
    def for_window_type(self, type_id: str) -> str:
        """``"data.sensor_stream"`` 等の id をアイコン文字列に変換."""

    def for_command(self, command: str) -> str:
        """Command Palette のコマンドに使うアイコン. デフォルトは空."""
        return self._lookup_or_default(f"cmd.{command}", default="")

    def for_category(self, category: str) -> str:
        """カテゴリメニュー用. デフォルトは空."""
        return self._lookup_or_default(f"cat.{category}", default="")

    def _lookup_or_default(self, key: str, *, default: str) -> str:
        """サブクラスが override しなければ default を返す."""
        return default


# ---------------------------------------------------------------------------
# Concrete sets
# ---------------------------------------------------------------------------


class _AsciiIconSet(IconSet):
    """フォントなしでも確実に出るプレーン ASCII セット (最終フォールバック)."""

    kind: IconKind = "ascii"

    _MAP: dict[str, str] = {
        # data category
        "data.sensor_stream": "[~]",
        "data.spc_chart":     "[#]",
        "data.audit_log":     "[L]",
        "data.narration":     "[T]",
        # viewer category
        "viewer.image":       "[I]",
        "viewer.pdf":         "[P]",
        "viewer.mesh":        "[3]",
        "viewer.video":       "[V]",
        "viewer.audio":       "[A]",
        "viewer.map":         "[M]",
        # game category
        "game.board":         "[B]",
        "game.kifu":          "[K]",
        "game.eval_chart":    "[E]",
        "game.commentary":    "[C]",
        "game.hands":         "[H]",
        "game.timer":         "[t]",
        # editor category
        "editor.text":        "[e]",
        "editor.notebook":    "[N]",
        "editor.repl":        [">>"][0],
        "editor.tree":        "[/]",
        # dialogue
        "dialogue.chat":      "[c]",
        "dialogue.console":   "[$]",
        "dialogue.palette":   "[:]",
        # meta
        "meta.identity_panel": "[id]",
        "meta.workspace":     "[w]",
        # llmesh
        "llmesh.peer_list":   "[p]",
        "llmesh.topology":    "[*]",
        # typing
        "typing.area":        "[T]",
        "typing.wpm":         "[w]",
        # debug
        "debug.event":        "[d]",
        "debug.json_tree":    "[{}]",
    }

    def for_window_type(self, type_id: str) -> str:
        return self._MAP.get(type_id, "[?]")


class _EmojiIconSet(IconSet):
    """UTF-8 対応端末向け絵文字セット (CP932 で出ない可能性に注意)."""

    kind: IconKind = "emoji"

    _MAP: dict[str, str] = {
        "data.sensor_stream": "📡",
        "data.spc_chart":     "📊",
        "data.audit_log":     "📋",
        "data.narration":     "💬",
        "viewer.image":       "🖼",
        "viewer.pdf":         "📄",
        "viewer.mesh":        "🧊",
        "viewer.video":       "🎬",
        "viewer.audio":       "🎵",
        "viewer.map":         "🗺",
        "game.board":         "♟",
        "game.kifu":          "📜",
        "game.eval_chart":    "📈",
        "game.commentary":    "🗨",
        "game.hands":         "✋",
        "game.timer":         "⏱",
        "editor.text":        "✏",
        "editor.notebook":    "📓",
        "editor.repl":        "⌨",
        "editor.tree":        "📂",
        "dialogue.chat":      "💬",
        "dialogue.console":   "💻",
        "dialogue.palette":   "🎨",
        "meta.identity_panel": "🔑",
        "meta.workspace":     "🗂",
        "llmesh.peer_list":   "👥",
        "llmesh.topology":    "🕸",
        "typing.area":        "⌨",
        "typing.wpm":         "⏱",
        "debug.event":        "🐛",
        "debug.json_tree":    "🌳",
    }

    def for_window_type(self, type_id: str) -> str:
        return self._MAP.get(type_id, "❔")


class _NerdFontIconSet(IconSet):
    """Nerd Font (Powerline / DevIcons / FontAwesome / Material 等) セット.

    フォントが入っていれば多くの開発者環境で綺麗に表示される. PUA エリア
    (U+E000-F8FF / U+F0000-) のグリフを使うので、フォントが無いと豆腐
    (□) になる. ``LLOVE_ICONS=ascii`` で逃がせる.
    """

    kind: IconKind = "nerd"

    # 主要グリフだけ. 不足分は emoji / ascii にフォールバックする実装方針も
    # あるが、ここでは固定文字列で簡素化.
    _MAP: dict[str, str] = {
        "data.sensor_stream": "",  #
        "data.spc_chart":     "",  #
        "data.audit_log":     "",  #
        "data.narration":     "",  #
        "viewer.image":       "",  #
        "viewer.pdf":         "",  #
        "viewer.mesh":        "",  #
        "viewer.video":       "",  #
        "viewer.audio":       "",  #
        "viewer.map":         "",  #
        "game.board":         "",  #  (chess / 棋)
        "game.kifu":          "",  #
        "game.eval_chart":    "",  #
        "game.commentary":    "",  #
        "game.hands":         "",  #
        "game.timer":         "",  #
        "editor.text":        "",  #
        "editor.notebook":    "",  #
        "editor.repl":        "",  #
        "editor.tree":        "",  #
        "dialogue.chat":      "",  #
        "dialogue.console":   "",  #
        "dialogue.palette":   "",  #
        "meta.identity_panel": "",  #
        "meta.workspace":     "",  #
        "llmesh.peer_list":   "",  #
        "llmesh.topology":    "",  #
        "typing.area":        "",  #
        "typing.wpm":         "",  #
        "debug.event":        "",  #
        "debug.json_tree":    "",  #
    }

    def for_window_type(self, type_id: str) -> str:
        return self._MAP.get(type_id, "")  #


# ---------------------------------------------------------------------------
# Auto detection
# ---------------------------------------------------------------------------


def _detect_kind() -> IconKind:
    """環境変数 / `$TERM_PROGRAM` を見て auto 選択."""
    forced = os.environ.get("LLOVE_ICONS", "auto").lower()
    if forced in ("nerd", "emoji", "ascii"):
        return forced  # type: ignore[return-value]
    if forced == "sixel":
        # Sixel / Kitty 実装はまだ無いので Nerd にフォールバック
        return "nerd"
    # auto detection: very lightweight heuristics. 100% accurate ではない.
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program in ("WezTerm", "iTerm.app", "kitty") or os.environ.get("KITTY_INSTALLATION_DIR"):
        # 高機能ターミナルなら Nerd Font が入っている可能性が高い
        return "nerd"
    if os.name == "nt":
        # Windows console は CP932 で絵文字が壊れがち → ASCII デフォ
        return "ascii"
    # POSIX で TERM_PROGRAM 不明 → 絵文字を試す
    return "emoji"


_INSTANCES: dict[IconKind, IconSet] = {
    "ascii": _AsciiIconSet(),
    "emoji": _EmojiIconSet(),
    "nerd": _NerdFontIconSet(),
}


def get_iconset(kind: IconKind | Literal["auto"] = "auto") -> IconSet:
    """指定 kind の IconSet を返す. ``"auto"`` で環境検出."""
    if kind == "auto":
        kind = _detect_kind()
    return _INSTANCES[kind]
