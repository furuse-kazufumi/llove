"""Renderer Registry — URI → 実際のレンダラ候補を解決する.

F15 (l)(p) のディスパッチ層. Each ``URIRef`` は複数の候補レンダラを持ち、
優先度順に試行する:

1. **Pure Python ビューア** (Pillow + Image2DViewer 等) — 最も移植性高い
2. **外部 CLI ツール** (chafa / viu / w3m / mpv / ...) — TUI で本物感
3. **Qt fallback** (PySide6 ベース) — sixel / kitty 非対応端末向け
4. **ASCII フォールバック** — どれも無い時の最後の砦

このモジュールは候補の **解決のみ** を行う; 実描画は呼び出し側で
``ResolvedRenderer.kind`` を見て分岐する。

設計の柱として:

- 同じ URI から複数候補を返す → Settings モーダルでユーザに選ばせる土台
- 拡張子 → scheme は ``uri.parse_uri`` に集約済 → このモジュールでは
  scheme → renderer のレベルだけ扱う
- カタログは差し替え可能 → サードパーティは ``register_handler`` で
  新ハンドラを足せる
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from llove.browser.external import ExternalTool, available_tools
from llove.browser.uri import URIRef

RendererKind = Literal[
    "pure_python",
    "external_cli",
    "qt_fallback",
    "ascii_fallback",
    "missing",
]


@dataclass(frozen=True)
class ResolvedRenderer:
    """1 つのレンダラ候補.

    ``kind`` は呼び出し側 (BrowserView 等) の分岐タグ。
    ``handler`` は ``pure_python`` / ``qt_fallback`` の時の callable、
    ``external_tool`` は ``external_cli`` の時に埋まる。
    """

    kind: RendererKind
    label: str
    priority: int = 100
    handler: Callable[..., object] | None = None
    external_tool: ExternalTool | None = None
    install_hint: str = ""


# ---------------------------------------------------------------------------
# Pure Python / Qt ハンドラのレジストリ
# ---------------------------------------------------------------------------


@dataclass
class _SchemeHandlers:
    """1 scheme に対する Pure Python / Qt ハンドラのリスト."""

    pure_python: list[ResolvedRenderer] = field(default_factory=list)
    qt_fallback: list[ResolvedRenderer] = field(default_factory=list)


_SCHEME_HANDLERS: dict[str, _SchemeHandlers] = {}


def register_handler(
    scheme: str,
    *,
    kind: Literal["pure_python", "qt_fallback"],
    label: str,
    handler: Callable[..., object],
    priority: int = 100,
) -> None:
    """Pure Python / Qt ハンドラを scheme に登録する."""
    bucket = _SCHEME_HANDLERS.setdefault(scheme, _SchemeHandlers())
    rec = ResolvedRenderer(kind=kind, label=label, priority=priority, handler=handler)
    if kind == "pure_python":
        bucket.pure_python.append(rec)
    else:
        bucket.qt_fallback.append(rec)


# ---------------------------------------------------------------------------
# 解決
# ---------------------------------------------------------------------------


def resolve_renderer(uri: URIRef) -> list[ResolvedRenderer]:
    """``uri`` で使えるレンダラ候補を、優先度の高い順に返す.

    候補が空 (``[]``) なら呼び出し側は ASCII フォールバック / インストール
    案内に降りる。F15 (l)(p) の「複数選択肢 + 設定メニュー」はこのリストを
    Settings モーダルに渡して描画する。
    """
    if uri.scheme == "unknown":
        return []

    candidates: list[ResolvedRenderer] = []

    # 1. Pure Python ハンドラ
    bucket = _SCHEME_HANDLERS.get(uri.scheme)
    if bucket is not None:
        candidates.extend(bucket.pure_python)

    # 2. 外部 CLI (実際にインストール済のものだけ)
    for tool in available_tools(uri.scheme):
        candidates.append(ResolvedRenderer(
            kind="external_cli",
            label=f"{tool.name}  — {tool.notes}" if tool.notes else tool.name,
            priority=tool.priority,
            external_tool=tool,
        ))

    # 3. Qt fallback
    if bucket is not None:
        candidates.extend(bucket.qt_fallback)

    # 4. 何も無ければ「missing」エントリ 1 件 — Settings に「インストールして」案内を出すための材料
    if not candidates:
        from llove.browser.external import all_catalogued_tools

        catalogued = all_catalogued_tools(uri.scheme)
        hint = " / ".join(t.install_hint for t in catalogued if t.install_hint)
        candidates.append(ResolvedRenderer(
            kind="missing",
            label=f"no renderer for scheme '{uri.scheme}'",
            install_hint=hint,
        ))
        return candidates

    candidates.sort(key=lambda r: r.priority)
    return candidates
