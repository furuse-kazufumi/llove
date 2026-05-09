"""``llove.window`` — F17 MainWindow / Window 管理基盤の最小骨組み.

公開 API:

    from llove.window import (
        WindowType,                     # F17(m)(n) ウィンドウ種カタログの単位
        register_window_type,
        get_window_type,
        list_window_types,
        Window, WindowGroup,            # 個別 Window インスタンス + コンテナ
        FreeContainer, LockedContainer, # F17(b) 2 種コンテナ
        WindowManager,                  # F17(h) 全体管理
        WindowLayout, WindowSpec,       # F17(r) シナリオ駆動レイアウト宣言
        IconSet, get_iconset,           # F17(s) アイコン体系
    )

設計原則:
- **2.1.2 ウィンドウ哲学**: 1 ウィンドウ種 = 1 責務. 機能追加は新ウィンドウ種.
- **F17(m) Registry 駆動**: 60+ ウィンドウ種カタログ. 動的登録可.
- **F17(s) アイコン**: 論理 ID 文字列 ("game.board" 等) を IconSet が
  動作環境別に展開 (Nerd/Emoji/ASCII).
- **F18 Cargo 境界**: 将来 ``llove-window-core`` クレートにそのまま乗る
  ディレクトリ構成.
"""

from __future__ import annotations

from llove.window.containers import (
    FreeContainer,
    LockedContainer,
    Window,
    WindowGroup,
)
from llove.window.iconset import IconSet, get_iconset
from llove.window.manager import (
    WindowLayout,
    WindowManager,
    WindowSpec,
)
from llove.window.types import (
    WindowType,
    get_window_type,
    list_window_types,
    register_window_type,
)

__all__ = [
    "FreeContainer",
    "IconSet",
    "LockedContainer",
    "Window",
    "WindowGroup",
    "WindowLayout",
    "WindowManager",
    "WindowSpec",
    "WindowType",
    "get_iconset",
    "get_window_type",
    "list_window_types",
    "register_window_type",
]
