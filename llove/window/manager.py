"""F17(c)(h)(r) WindowManager — 全 Window をホストする一級オブジェクト.

責務:
- ``FreeContainer`` / ``LockedContainer`` の保持
- ``WindowLayout`` (F17(r) シナリオ駆動レイアウト) の適用
- ``layout.toml`` (F17(c) 位置記憶) の保存 / 復元

最小スキーマ (F17(c) のフル機能は後実装):
- ``windows`` リスト (group / type_id / title / size / position / state / config / pinned)
- マルチディスプレイ識別 (F17(d)) は次バージョンで

```toml
[meta]
schema = 1
mode = "MDI"

[[window]]
group = "locked"
type_id = "data.sensor_stream"
title = "📡 Sensors"
size = [60, 20]
position = [0, 0]
state = "normal"
pinned = true

[[window]]
group = "free"
type_id = "data.audit_log"
title = "Audit"
size = [80, 12]
position = [0, 24]
state = "normal"
pinned = false
```

LoveApp との互換: ``window_layout=None`` の DemoScenario は WindowManager を
使わない従来の 4 ペイン直配置で動く. 段階移行.
"""

from __future__ import annotations

import tomllib  # type: ignore[import-not-found]
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from llove.window.containers import (
    FreeContainer,
    LockedContainer,
    Window,
    WindowGroup,
)
from llove.window.types import get_window_type

WindowMode = Literal["SDI", "MDI", "Tabbed", "Tile"]


# ---------------------------------------------------------------------------
# Layout 宣言 (F17(r))
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowSpec:
    """シナリオがレイアウト宣言で使う 1 ウィンドウの仕様.

    ``WindowType.id`` を type_id として指定し、size_hint / position_hint /
    config を渡す. ``Window`` (実体) との違いは「まだ build 前」という点.
    """

    type_id: str
    title: str = ""
    size_hint: tuple[int, int] = (60, 20)
    position_hint: str = "auto"
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WindowLayout:
    """シナリオ駆動レイアウト宣言.

    Fields
    ------
    locked
        ``LockedContainer`` に固定配置されるウィンドウの一覧 (デモ要件).
    free
        ``FreeContainer`` に最初から開かれるウィンドウの一覧 (任意).
    initial_mode
        SDI / MDI / Tabbed / Tile.
    preset_name
        `:layout <preset>` で再呼び出し可能な名前. 空なら登録しない.
    """

    locked: tuple[WindowSpec, ...] = ()
    free: tuple[WindowSpec, ...] = ()
    initial_mode: WindowMode = "MDI"
    preset_name: str = ""


# ---------------------------------------------------------------------------
# WindowManager
# ---------------------------------------------------------------------------


class WindowManager:
    """全 Window をホストするマネージャ. シングルトンっぽく扱うが、
    インスタンス管理は呼び出し側責任 (将来テストで複数インスタンスを
    使えるように、明示的 ``WindowManager()`` で作る形を維持).
    """

    def __init__(self, *, mode: WindowMode = "MDI") -> None:
        self.locked = LockedContainer()
        self.free = FreeContainer()
        self.mode: WindowMode = mode

    # ---- Container アクセス ------------------------------------------
    def container(self, group: str) -> WindowGroup:
        if group == "locked":
            return self.locked
        if group == "free":
            return self.free
        raise ValueError(f"unknown group {group!r} (use 'locked' / 'free')")

    @property
    def all_windows(self) -> list[Window]:
        return list(self.locked) + list(self.free)

    # ---- 直接的な register --------------------------------------------
    def register_view(
        self,
        type_id: str,
        *,
        group: Literal["locked", "free"] = "free",
        title: str = "",
        size: tuple[int, int] | None = None,
        config: dict[str, Any] | None = None,
    ) -> Window:
        """1 つの Window を該当 group に追加する.

        ``type_id`` が Registry に無い場合 → fail-closed で
        ``data.audit_log`` (常時存在) に置き換え + 警告メッセージは
        呼び出し側 (LoveApp) に audit イベントとして流す形.
        ここでは黙って fallback だけ実施 (UI が落ちないことを最優先).
        """
        wt = get_window_type(type_id)
        if wt is None:
            wt = get_window_type("data.audit_log")
            if wt is None:  # ビルトインまで消えた → 例外
                raise RuntimeError("audit_log builtin missing; registry corrupted")
            type_id = wt.id

        win = Window(
            type_id=type_id,
            title=title or wt.display_name,
            size=size if size is not None else wt.default_size,
            position=(0, 0),
            state="normal",
            config=config or {},
            pinned=(group == "locked"),
        )
        self.container(group).add(win)
        return win

    # ---- Layout 適用 (F17(r)) -----------------------------------------
    def apply_layout(self, layout: WindowLayout) -> None:
        """``WindowLayout`` を現在のマネージャに適用.

        Locked container は実用上「シナリオ切替時に毎回 clear したい」が、
        LockedContainer.clear() は禁止されているので、内部 _windows を
        privileged にいじる (シナリオ切替は Manager の責務として許可).
        """
        # locked の付け替え (privileged: シナリオ切替で内部 _windows を強制 reset)
        self.locked._windows.clear()
        for spec in layout.locked:
            self.register_view(
                spec.type_id, group="locked",
                title=spec.title,
                size=spec.size_hint,
                config=spec.config,
            )
        # free は clear せず追記 (ユーザが既に開いた window を残す)
        for spec in layout.free:
            self.register_view(
                spec.type_id, group="free",
                title=spec.title,
                size=spec.size_hint,
                config=spec.config,
            )
        self.mode = layout.initial_mode

    # ---- layout.toml シリアライズ ------------------------------------
    def to_toml(self) -> str:
        """現状を TOML 文字列に直列化. F17(c) 位置記憶用."""
        lines: list[str] = []
        lines.append("[meta]")
        lines.append("schema = 1")
        lines.append(f'mode = "{self.mode}"')
        lines.append("")
        for group_name, container in (("locked", self.locked), ("free", self.free)):
            for w in container:
                lines.append("[[window]]")
                lines.append(f'group = "{group_name}"')
                lines.append(f'type_id = "{w.type_id}"')
                # title は記号入り得るので escape: ダブルクォート + バック
                # スラッシュエスケープのみ.
                escaped = w.title.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'title = "{escaped}"')
                lines.append(f'size = [{w.size[0]}, {w.size[1]}]')
                lines.append(f'position = [{w.position[0]}, {w.position[1]}]')
                lines.append(f'state = "{w.state}"')
                lines.append(f'pinned = {"true" if w.pinned else "false"}')
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    @classmethod
    def from_toml(cls, text: str) -> WindowManager:
        """TOML 文字列から WindowManager を構築 (位置復元)."""
        data: dict[str, Any] = tomllib.loads(text)
        mode = data.get("meta", {}).get("mode", "MDI")
        if mode not in ("SDI", "MDI", "Tabbed", "Tile"):
            mode = "MDI"
        mgr = cls(mode=mode)  # type: ignore[arg-type]
        for entry in data.get("window", []):
            group = entry.get("group", "free")
            if group not in ("locked", "free"):
                group = "free"
            type_id = entry.get("type_id", "data.audit_log")
            title = entry.get("title", "")
            size = tuple(entry.get("size", (60, 20)))[:2]
            position = tuple(entry.get("position", (0, 0)))[:2]
            state = entry.get("state", "normal")
            pinned = bool(entry.get("pinned", group == "locked"))
            config = entry.get("config", {})

            wt = get_window_type(type_id)
            display_name = wt.display_name if wt is not None else type_id

            win = Window(
                type_id=type_id,
                title=title or display_name,
                size=size,  # type: ignore[arg-type]
                position=position,  # type: ignore[arg-type]
                state=state,
                pinned=pinned,
                config=config,
            )
            mgr.container(group).add(win)
        return mgr

    def save(self, path: str | Path) -> None:
        """``layout.toml`` に保存 (XDG パス想定)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.to_toml(), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> WindowManager:
        return cls.from_toml(Path(path).read_text(encoding="utf-8"))
