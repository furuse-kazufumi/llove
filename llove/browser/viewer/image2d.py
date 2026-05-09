"""Image2DViewer — Pillow ベースの 2D 画像ビューア (F15 (q)(ii)).

``camera`` を ``zoom`` / ``pan`` / ``flip`` に解釈して PIL Image を返す。
描画レイヤー (TUI: chafa pipe / Sixel / ASCII art、Qt: QImage) はこの
PIL Image を受け取って端末に貼るだけで、視点処理を再実装しなくて良い。

依存方針:
- Pillow は ``[browser-image]`` extras。コア依存ではない。
- 未インストール時は ``ImageBackendUnavailable`` を投げ、上位の Registry
  が「`pip install llmesh-llove[browser-image]`」案内に降りる。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from llove.browser.viewer.base import Camera, Viewer

if TYPE_CHECKING:  # pragma: no cover
    from PIL import Image  # type: ignore[import-not-found]


class ImageBackendUnavailable(RuntimeError):
    """Pillow が無いときに投げる. 呼び出し側はインストール案内に降りる."""


def _import_pillow() -> Any:
    try:
        from PIL import Image  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover — guarded by extras
        raise ImageBackendUnavailable(
            "Pillow not installed. Install with: pip install 'llmesh-llove[browser-image]'"
        ) from exc
    return Image


class Image2DViewer(Viewer):
    """ローカルファイルを Pillow で開き、camera 適用後の画像を返す."""

    scheme = "image"

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self._path = Path(path)
        self._original: Image.Image | None = None

    def _load(self) -> Image.Image:
        if self._original is None:
            Image = _import_pillow()
            # ``with`` を使うと外側からのアクセスで close される。lazy load に。
            self._original = Image.open(self._path)
            self._original.load()  # ファイル handle 早期 close
        return self._original

    def render(
        self, *, width: int, height: int, camera: Camera | None = None
    ) -> Image.Image:
        Image = _import_pillow()
        cam = camera if camera is not None else self.camera
        img = self._load().copy()

        # flip
        if cam.flip_x:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        if cam.flip_y:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)

        if cam.fit_to_screen:
            # 画面に収まるよう縮小 (アスペクト維持)
            img.thumbnail((width, height))
            return img

        # zoom + pan
        new_w = max(1, int(img.width * cam.zoom))
        new_h = max(1, int(img.height * cam.zoom))
        img = img.resize((new_w, new_h))

        # pan は画面中心からのオフセット — 出力 canvas に貼る
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        cx = (width - img.width) // 2 + int(cam.pan_x)
        cy = (height - img.height) // 2 + int(cam.pan_y)
        canvas.paste(img, (cx, cy))
        return canvas
