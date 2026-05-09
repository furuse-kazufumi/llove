"""F17(b) Window コンテナの 2 種類 — Free と Locked.

- ``FreeContainer``: ユーザがメニューから自由に新規 / 閉じる / 移動
- ``LockedContainer``: デモが ``pinned=True`` で要求した常駐 view.
  追加 / 削除を **API レベルで拒否** する. UI は + / × ボタン非表示.

両者は ``WindowGroup`` (1 group = 1 container) として扱う. Layout 保存
時に別ノードとして直列化されるので、シナリオ宣言レイアウト (F17(r))
で「どのウィンドウが locked / free か」を区別できる.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


WindowState = Literal["normal", "minimized", "maximized"]


@dataclass
class Window:
    """個別ウィンドウインスタンスの状態.

    Fields
    ------
    type_id
        ``WindowType.id`` と一致 (``"data.sensor_stream"`` 等). Registry
        から実体 view を build するためのキー.
    title
        タブ / ヘッダ表示用. 空ならデフォルト (WindowType.display_name).
    size
        (cols, rows). TUI では文字単位、Qt では px に換算.
    position
        (x, y). レイアウト復元時にここから配置を再現.
    state
        ``"normal"`` / ``"minimized"`` / ``"maximized"``.
    config
        WindowType ごとの追加設定 (``BrowserView`` の URI 指定など).
    pinned
        True なら LockedContainer に居る. UI で + / × 非表示の判定にも使う.
    """

    type_id: str
    title: str = ""
    size: tuple[int, int] = (60, 20)
    position: tuple[int, int] = (0, 0)
    state: WindowState = "normal"
    config: dict[str, Any] = field(default_factory=dict)
    pinned: bool = False


# ---------------------------------------------------------------------------
# Container base + 2 種類
# ---------------------------------------------------------------------------


class WindowGroup:
    """``FreeContainer`` / ``LockedContainer`` の共通基底.

    内部は ``list[Window]`` を保持し、追加 / 削除 / 検索 API を提供する.
    順序は意味を持つ (タブ並び順そのまま).
    """

    name: str = ""
    locked: bool = False  # サブクラスで上書き

    def __init__(self) -> None:
        self._windows: list[Window] = []

    @property
    def windows(self) -> list[Window]:
        return list(self._windows)  # 防御的コピー

    def __len__(self) -> int:
        return len(self._windows)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._windows)

    def find(self, type_id: str) -> Window | None:
        """同じ type_id の最初のウィンドウを返す (なければ None)."""
        for w in self._windows:
            if w.type_id == type_id:
                return w
        return None

    # ---- 操作 (サブクラスで違いが出る) -------------------------------
    def add(self, window: Window) -> Window:
        self._windows.append(window)
        return window

    def remove(self, window: Window) -> None:
        # サブクラス側でロック判定
        self._windows.remove(window)

    def clear(self) -> None:
        self._windows.clear()


class FreeContainer(WindowGroup):
    """自由に増減可能なコンテナ. + / × ボタン有効."""

    name = "free"
    locked = False


class LockedContainer(WindowGroup):
    """デモ要件の常駐コンテナ. add/remove を API で拒否.

    シナリオが ``WindowLayout(locked=[...])`` で宣言する用.
    `register_demo_pinned(window)` で「シナリオ起動時にだけ追加」する API
    も将来追加予定 (現状は普通に add すればよい — UI 側で操作不能).
    """

    name = "locked"
    locked = True

    def remove(self, window: Window) -> None:  # type: ignore[override]
        """Locked コンテナからの remove は禁止 (fail-closed)."""
        raise PermissionError(
            f"cannot remove from LockedContainer (window={window.type_id!r}); "
            "this is pinned by the demo. Switch to a different scenario or "
            "use FreeContainer for ad-hoc views."
        )

    def clear(self) -> None:  # type: ignore[override]
        """同じく clear も拒否."""
        raise PermissionError("cannot clear LockedContainer; pinned by the demo.")
