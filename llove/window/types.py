"""F17(m)(n) WindowType ABC + Registry — 「ウィンドウ種カタログ」の中身.

設計原則 2.1.2 (ウィンドウ哲学) に基づき、各 WindowType は 1 責務.
``id`` は安定文字列 (例 ``"data.sensor_stream"`` / ``"game.board"`` /
``"viewer.image"``). IconSet (F17(s)) はこの id をキーにアイコンを引く.

サードパーティが ``register_window_type`` で新種を差し込める. 既存ウィン
ドウを膨らませる代わりに新ウィンドウ種を追加するのが正しい (2.1.2).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WindowType:
    """1 つのウィンドウ種の記述子.

    Fields
    ------
    id
        安定識別子 (``"data.sensor_stream"``). カテゴリ.名前 形式を推奨.
        IconSet がこの id をアイコンに変換する.
    display_name
        メニュー表示用の人間可読名 (``"SensorEvent stream"``).
    category
        F17(m) の 12 カテゴリ ("data" / "viewer" / "game" / "editor" /
        "dialogue" / "input" / "visualization" / "meta" / "llmesh" /
        "typing" / "learning" / "debug").
    description
        Settings モーダル / `:help` 用の 1 行説明.
    default_size
        起動時の推奨サイズ (cols, rows). TUI では文字単位、Qt では px 換算.
    default_pinned
        True の場合、デフォルトで LockedContainer に入る (シナリオが
        必要とする常駐ウィンドウ向け).
    builder
        ``builder(config: dict) -> View`` で Textual / Qt / その他 View
        インスタンスを生成する callable. None でも Registry に置けるが、
        実装が無いウィンドウ種となる (Settings に「未実装」表示).
    """

    id: str
    display_name: str
    category: str
    description: str = ""
    default_size: tuple[int, int] = (60, 20)
    default_pinned: bool = False
    builder: Callable[[dict[str, Any]], Any] | None = None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_REGISTRY: dict[str, WindowType] = {}


def register_window_type(wt: WindowType) -> None:
    """Registry に新規 WindowType を登録 (重複 id は上書き、警告ログなし).

    サードパーティ拡張から呼べる. F19 スクリプトからも同じ API.
    """
    _REGISTRY[wt.id] = wt


def get_window_type(id: str) -> WindowType | None:
    """id で WindowType を引く. 未登録なら ``None`` (fail-closed).

    呼び出し側は None なら「対応 ウィンドウ種なし」案内に降りる.
    """
    return _REGISTRY.get(id)


def list_window_types(category: str | None = None) -> list[WindowType]:
    """Registry の全エントリを返す (任意で category フィルタ).

    Settings モーダル / `View → New Window` メニュー / Command Palette の
    `:window add <type>` 補完で消費される.
    """
    items = list(_REGISTRY.values())
    if category is not None:
        items = [w for w in items if w.category == category]
    return sorted(items, key=lambda w: (w.category, w.id))


def reset_registry_for_test() -> None:
    """テスト専用. ビルトインを再登録するために registry を空にする."""
    _REGISTRY.clear()


# ---------------------------------------------------------------------------
# ビルトイン (既存 4 ペイン互換) — F17(m) ① data カテゴリ
# ---------------------------------------------------------------------------


def _register_builtins() -> None:
    """既存 4 ペイン (LoveApp) に対応する WindowType をビルトイン登録.

    builder=None で置き、実描画は当面 LoveApp 側に任せる. F17 完全実装時に
    builder で View を返すよう順次置換.
    """
    builtins = [
        WindowType(
            id="data.sensor_stream",
            display_name="SensorEvent Stream",
            category="data",
            description="Rolling sensor readings + sparkline (F2).",
            default_size=(60, 20),
        ),
        WindowType(
            id="data.spc_chart",
            display_name="SPC Chart",
            category="data",
            description="CUSUM control chart with alarm log (F2).",
            default_size=(60, 20),
        ),
        WindowType(
            id="data.audit_log",
            display_name="Audit Log",
            category="data",
            description="Append-only audit / LLM call / RAG hit events.",
            default_size=(60, 12),
        ),
        WindowType(
            id="data.narration",
            display_name="Narration",
            category="data",
            description="Scenario commentary in plain words.",
            default_size=(60, 8),
        ),
        # メタ系: Identity panel — 全デモで常時 did:key を見せる候補.
        WindowType(
            id="meta.identity_panel",
            display_name="Identity Panel",
            category="meta",
            description="Always-on did:key + signing status (llmesh).",
            default_size=(40, 4),
            default_pinned=True,
        ),
    ]
    for wt in builtins:
        register_window_type(wt)


_register_builtins()
