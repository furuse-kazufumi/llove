"""llove.browser.viewer — 統一 Viewer / Camera 基盤 (F15 (q)).

2D / 3D / 動画など、視点・ズーム・パンが必要な全てのモーダルが共有する
インタラクション層。``Viewer`` ABC + ``Camera`` dataclass を中心に置き、
具体ビューア (``Image2DViewer``, ``Mesh3DViewer``, ...) はこの上に乗る。

設計の柱:

- **Camera は描画レイヤー (TUI / Qt) から独立** — 同じ camera state を
  Textual 側で再描画しても Qt 側に渡しても、画面上で同じパン・ズーム位置
  になる。
- **キーバインドの統一** (F15(q)(vi)) — `+/-` ズーム、矢印 / hjkl パン、
  `wasd` 回転、`0` リセット、`f` フィット、`F11` フルスクリーン。Viewer 側
  でこれらキーをハンドルするデフォルト実装を持ち、サブクラスは override
  だけで済む。
- **F16 ゲーム表示への転用** — 駒画像・盤面・3D 駒・カードスプライトを
  すべて Image2DViewer / Mesh3DViewer に集約すれば、ゲーム特殊な描画コード
  を書かずに済む (要件 F15 (q)(ix))。
"""

from __future__ import annotations

from llove.browser.viewer.base import Camera, Viewer, ViewerEvent

__all__ = ["Camera", "Viewer", "ViewerEvent"]
