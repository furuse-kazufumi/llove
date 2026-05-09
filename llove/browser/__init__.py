"""llove.browser — F15 ブラウザ並みデータ表示の共通基盤.

llove を「ターミナル版 Artifact」から「ターミナル版ブラウザ」に拡張するための
共通レイヤー。各モーダル (画像 / PDF / 表 / グラフ / 3D / 動画 / HTML) は
ここに集約された URI ルーティング + Viewer ABC + Camera + 外部ツール
カタログの上に乗る。

公開 API は意図的に小さい:

    from llove.browser import (
        Camera, Viewer,                  # 統一ビューア基盤 (F15(q))
        URIRef, parse_uri,               # URI ルーティング (F15(l))
        ResolvedRenderer, resolve_renderer,
        ExternalTool, available_tools,   # 外部ツール検出 (F15(o))
    )

サブモジュールはすべて遅延 import で、コア依存 (Pillow / trimesh /
PySide6) は使う時にだけ pull される。``llmesh-llove`` 既定インストールでは
``import llove.browser`` してもコア依存の追加は無い。
"""

from __future__ import annotations

from llove.browser.external import ExternalTool, available_tools
from llove.browser.registry import ResolvedRenderer, resolve_renderer
from llove.browser.uri import URIRef, parse_uri
from llove.browser.viewer.base import Camera, Viewer

__all__ = [
    "Camera",
    "ExternalTool",
    "ResolvedRenderer",
    "URIRef",
    "Viewer",
    "available_tools",
    "parse_uri",
    "resolve_renderer",
]
