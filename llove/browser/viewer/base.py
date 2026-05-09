"""Viewer ABC + Camera — 統一視点・ズーム・パン基盤 (F15 (q)).

``Camera`` は描画レイヤー非依存の **状態オブジェクト**。Textual から
Qt へ、あるいは Qt から TUI ASCII 化レイヤーへ camera を渡しても
位置・ズーム・回転が一貫する。

``Viewer`` は ``Camera`` を保持し、キーバインド統一 (F15(q)(vi)) を
デフォルト実装する。サブクラス (``Image2DViewer``, ``Mesh3DViewer``)
は ``render(camera)`` だけ実装すれば良い。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Literal


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Camera:
    """描画パラメータの不変スナップショット.

    すべての操作 (``zoom_in``, ``pan``, ``rotate``, ``reset``) は新しい
    ``Camera`` を返す純関数。 frozen にすることで、状態履歴 (undo/redo,
    アニメーション補間) を簡潔に扱える。

    Fields
    ------
    zoom
        論理ズーム (1.0 = 等倍). 2D / 3D 共通.
    pan_x, pan_y
        画面中心からのオフセット (ピクセル等価). 2D は両軸、3D は
        screen-space pan.
    rot_x, rot_y, rot_z
        3D 回転 (degrees). 2D ビューアは 0 のまま使う。
    flip_x, flip_y
        2D の左右 / 上下反転.
    fit_to_screen
        True の間はパン・ズームを無視して常に画面に合わせる
        (initial state). 1 度でも操作されたら自動で False になる。
    """

    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    rot_x: float = 0.0
    rot_y: float = 0.0
    rot_z: float = 0.0
    flip_x: bool = False
    flip_y: bool = False
    fit_to_screen: bool = True

    # ---- pan ------------------------------------------------------------
    def pan(self, dx: float, dy: float) -> Camera:
        return replace(self, pan_x=self.pan_x + dx, pan_y=self.pan_y + dy, fit_to_screen=False)

    # ---- zoom -----------------------------------------------------------
    def zoom_by(self, factor: float) -> Camera:
        if factor <= 0:
            return self
        new_zoom = max(0.01, min(self.zoom * factor, 100.0))
        return replace(self, zoom=new_zoom, fit_to_screen=False)

    def zoom_in(self) -> Camera:
        return self.zoom_by(1.25)

    def zoom_out(self) -> Camera:
        return self.zoom_by(0.8)

    # ---- rotate (3D 用) ------------------------------------------------
    def rotate(self, dx: float = 0, dy: float = 0, dz: float = 0) -> Camera:
        return replace(
            self,
            rot_x=(self.rot_x + dx) % 360,
            rot_y=(self.rot_y + dy) % 360,
            rot_z=(self.rot_z + dz) % 360,
            fit_to_screen=False,
        )

    # ---- flip (2D 用) --------------------------------------------------
    def flip_horizontal(self) -> Camera:
        return replace(self, flip_x=not self.flip_x, fit_to_screen=False)

    def flip_vertical(self) -> Camera:
        return replace(self, flip_y=not self.flip_y, fit_to_screen=False)

    # ---- reset / fit ---------------------------------------------------
    def reset(self) -> Camera:
        """初期状態 (フィット表示、ズーム等倍、パン 0、回転 0) に戻す."""
        return Camera()

    def fit(self) -> Camera:
        """`fit_to_screen` モードに戻す (ズーム / パンは捨てる)."""
        return Camera()


# ---------------------------------------------------------------------------
# Viewer
# ---------------------------------------------------------------------------


# 統一キーバインド (F15(q)(vi)). サブクラスや TUI/Qt 描画層はこの dict を
# 引いてユーザ操作 → camera 操作に変換する。
DEFAULT_KEYBINDINGS: dict[str, str] = {
    # zoom
    "+": "zoom_in", "=": "zoom_in", "kp_add": "zoom_in",
    "-": "zoom_out", "_": "zoom_out", "kp_subtract": "zoom_out",
    # pan
    "left": "pan_left", "h": "pan_left",
    "right": "pan_right", "l": "pan_right",
    "up": "pan_up", "k": "pan_up",
    "down": "pan_down", "j": "pan_down",
    # rotate (3D)
    "w": "rot_up", "s": "rot_down",
    "a": "rot_left", "d": "rot_right",
    "q": "rot_ccw", "e": "rot_cw",
    # flip
    "x": "flip_horizontal", "y": "flip_vertical",
    # special
    "0": "reset", "f": "fit",
}


ViewerAction = Literal[
    "zoom_in", "zoom_out",
    "pan_left", "pan_right", "pan_up", "pan_down",
    "rot_up", "rot_down", "rot_left", "rot_right", "rot_ccw", "rot_cw",
    "flip_horizontal", "flip_vertical",
    "reset", "fit",
]


@dataclass(frozen=True)
class ViewerEvent:
    """Viewer 操作の通知 — 履歴・ロギング用."""

    action: ViewerAction
    camera_before: Camera
    camera_after: Camera


class Viewer(ABC):
    """全 viewer の基底クラス.

    サブクラスは ``render(camera)`` のみ実装すれば良い。Camera 状態管理と
    キー / マウス操作の dispatch は基底で済んでいる。

    描画レイヤー (Textual ベース TUI / Qt GUI) はこの ABC を **knows** する
    側で、サブクラスではない。Viewer は描画後の bytes / Image / Mesh を返す
    だけで、ペインへの貼り付けは描画レイヤーが行う。
    """

    #: ビューアが扱う URI scheme (``"image"`` / ``"mesh"`` / ...).
    scheme: str = "?"

    def __init__(self) -> None:
        self._camera = Camera()
        self._pan_step = 25.0  # px equivalent
        self._rot_step = 5.0  # degrees

    # ---- camera state --------------------------------------------------
    @property
    def camera(self) -> Camera:
        return self._camera

    def set_camera(self, camera: Camera) -> None:
        self._camera = camera

    def apply_action(self, action: ViewerAction) -> ViewerEvent:
        """``DEFAULT_KEYBINDINGS`` 経由で来たアクションを camera に適用."""
        before = self._camera
        match action:
            case "zoom_in":          after = before.zoom_in()
            case "zoom_out":         after = before.zoom_out()
            case "pan_left":         after = before.pan(-self._pan_step, 0)
            case "pan_right":        after = before.pan(+self._pan_step, 0)
            case "pan_up":           after = before.pan(0, -self._pan_step)
            case "pan_down":         after = before.pan(0, +self._pan_step)
            case "rot_up":           after = before.rotate(dx=-self._rot_step)
            case "rot_down":         after = before.rotate(dx=+self._rot_step)
            case "rot_left":         after = before.rotate(dy=-self._rot_step)
            case "rot_right":        after = before.rotate(dy=+self._rot_step)
            case "rot_ccw":          after = before.rotate(dz=-self._rot_step)
            case "rot_cw":           after = before.rotate(dz=+self._rot_step)
            case "flip_horizontal":  after = before.flip_horizontal()
            case "flip_vertical":    after = before.flip_vertical()
            case "reset":            after = before.reset()
            case "fit":              after = before.fit()
            case _:
                after = before  # 未知アクションは no-op (fail-closed)
        self._camera = after
        return ViewerEvent(action=action, camera_before=before, camera_after=after)

    def handle_key(self, key: str) -> ViewerEvent | None:
        """``DEFAULT_KEYBINDINGS`` を引いてキー → アクション dispatch."""
        action = DEFAULT_KEYBINDINGS.get(key.lower())
        if action is None:
            return None
        return self.apply_action(action)  # type: ignore[arg-type]

    # ---- 描画 (サブクラスで実装) -------------------------------------
    @abstractmethod
    def render(self, *, width: int, height: int, camera: Camera | None = None) -> Any:
        """``camera`` 視点で描画する.

        戻り値は実装依存:
        - ``Image2DViewer``: PIL Image (camera 適用済み)
        - ``Mesh3DViewer``: 一時 PNG パス or PIL Image
        - 描画層はこれを Sixel 化 / Qt QImage 化 / ASCII 化する.

        ``camera=None`` の時は ``self.camera`` を使う。
        """
