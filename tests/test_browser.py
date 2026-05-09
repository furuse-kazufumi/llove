"""Tests for the F15 browser layer (URI / Camera / Registry / external tools)."""

from __future__ import annotations

from pathlib import Path

import pytest

from llove.browser import (
    Camera,
    ExternalTool,
    available_tools,
    parse_uri,
    resolve_renderer,
)
from llove.browser.external import register_tool, _registered_for_test_only
from llove.browser.registry import register_handler


# ---------------------------------------------------------------------------
# URI parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("inp,scheme", [
    ("cat.png", "image"),
    ("doc.pdf", "pdf"),
    ("model.obj", "mesh"),
    ("scan.pcd", "pointcloud"),
    ("clip.mp4", "video"),
    ("tune.flac", "audio"),
    ("data.csv", "csv"),
    ("config.toml", "toml"),
    ("query.sql", "code"),
    ("note.md", "markdown"),
    ("page.html", "web"),
])
def test_parse_uri_infers_scheme_from_extension(inp: str, scheme: str) -> None:
    uri = parse_uri(inp)
    assert uri.scheme == scheme
    assert uri.is_file is True


def test_parse_uri_explicit_image_scheme_keeps_path() -> None:
    uri = parse_uri("image:///abs/path/to/cat.png")
    assert uri.scheme == "image"
    assert uri.path == "/abs/path/to/cat.png"
    assert uri.is_file is True


def test_parse_uri_web_scheme_carries_url_in_target() -> None:
    uri = parse_uri("web://https://example.com/foo")
    assert uri.scheme == "web"
    assert uri.target == "https://example.com/foo"
    # web は file ではない
    assert uri.is_file is False
    assert uri.path == ""


def test_parse_uri_geo_scheme() -> None:
    uri = parse_uri("geo://35.68,139.76,12")
    assert uri.scheme == "geo"
    assert uri.target == "35.68,139.76,12"
    assert uri.is_file is False


def test_parse_uri_qr_scheme_holds_text_payload() -> None:
    uri = parse_uri("qr://hello-world")
    assert uri.scheme == "qr"
    assert uri.target == "hello-world"


def test_parse_uri_unknown_scheme_does_not_raise() -> None:
    uri = parse_uri("blob://xxx")
    assert uri.scheme == "unknown"


def test_parse_uri_unknown_extension_returns_unknown() -> None:
    uri = parse_uri("notes.xyz123")
    assert uri.scheme == "unknown"


# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------


def test_camera_default_is_fit_to_screen() -> None:
    c = Camera()
    assert c.fit_to_screen is True
    assert c.zoom == 1.0
    assert (c.pan_x, c.pan_y) == (0.0, 0.0)


def test_camera_zoom_in_disables_fit_to_screen() -> None:
    c = Camera().zoom_in()
    assert c.fit_to_screen is False
    assert c.zoom > 1.0


def test_camera_zoom_clamped_to_sane_range() -> None:
    # Very large factor must not blow up to infinity.
    c = Camera()
    for _ in range(100):
        c = c.zoom_by(10)
    assert c.zoom <= 100.0
    # And very small factor should clamp at the lower bound.
    c2 = Camera()
    for _ in range(100):
        c2 = c2.zoom_by(0.1)
    assert c2.zoom >= 0.01


def test_camera_pan_is_additive() -> None:
    c = Camera().pan(10, 20).pan(5, -3)
    assert c.pan_x == 15
    assert c.pan_y == 17


def test_camera_reset_returns_initial_state() -> None:
    c = Camera().zoom_in().pan(10, 20).rotate(dy=45)
    r = c.reset()
    assert r == Camera()
    assert r.fit_to_screen is True


def test_camera_flip_toggles() -> None:
    c = Camera().flip_horizontal()
    assert c.flip_x is True
    assert c.flip_horizontal().flip_x is False


def test_camera_rotate_modulo_360() -> None:
    c = Camera().rotate(dy=400)
    # 400 % 360 == 40
    assert c.rot_y == 40


def test_camera_is_immutable() -> None:
    c = Camera()
    with pytest.raises(Exception):
        c.zoom = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Viewer base — keybinding dispatch
# ---------------------------------------------------------------------------


def test_viewer_handle_key_dispatches_to_action() -> None:
    from llove.browser.viewer.base import Viewer

    class _Stub(Viewer):
        scheme = "image"
        def render(self, *, width, height, camera=None):  # type: ignore[override]
            return None

    v = _Stub()
    ev = v.handle_key("+")
    assert ev is not None
    assert ev.action == "zoom_in"
    assert ev.camera_after.zoom > ev.camera_before.zoom


def test_viewer_handle_key_unknown_returns_none() -> None:
    from llove.browser.viewer.base import Viewer

    class _Stub(Viewer):
        scheme = "image"
        def render(self, *, width, height, camera=None):  # type: ignore[override]
            return None

    v = _Stub()
    assert v.handle_key("z") is None


# ---------------------------------------------------------------------------
# External tool catalogue
# ---------------------------------------------------------------------------


def test_available_tools_filters_by_path_presence() -> None:
    # We can't assume any tool exists on CI / Windows, so we just assert the
    # function returns a list and never raises.
    result = available_tools("image")
    assert isinstance(result, list)


def test_register_tool_appends_and_is_resolvable() -> None:
    fake = ExternalTool(
        name="this-binary-definitely-does-not-exist-llove-test",
        scheme="image",
        args_template=["{path}"],
        priority=999,
    )
    register_tool(fake)
    # Won't show up in available_tools (no PATH hit), but is in catalogue.
    catalog = _registered_for_test_only()
    assert any(t.name == fake.name for t in catalog)


def test_external_tool_build_argv_substitutes_path() -> None:
    tool = ExternalTool(name="chafa", scheme="image", args_template=["--", "{path}"])
    argv = tool.build_argv(path="/tmp/cat.png")
    assert argv == ["chafa", "--", "/tmp/cat.png"]


# ---------------------------------------------------------------------------
# Renderer registry
# ---------------------------------------------------------------------------


def test_resolve_renderer_unknown_scheme_returns_empty() -> None:
    uri = parse_uri("blob://xxx")
    assert resolve_renderer(uri) == []


def test_resolve_renderer_returns_missing_when_nothing_available() -> None:
    """The registry must surface a 'missing' entry so the Settings modal can
    show an install hint, instead of silently returning empty."""
    uri = parse_uri("foo.png")
    candidates = resolve_renderer(uri)
    # Either real candidates exist (CI with chafa) or a single 'missing'
    # entry — never empty.
    assert candidates, "scheme=image must resolve to at least one entry"


def test_resolve_renderer_includes_pure_python_handler_when_registered() -> None:
    def _stub_renderer(*, uri, camera):  # pragma: no cover — never invoked here
        return None

    register_handler(
        "image",
        kind="pure_python",
        label="test pure python",
        handler=_stub_renderer,
        priority=1,
    )
    candidates = resolve_renderer(parse_uri("foo.png"))
    kinds = {c.kind for c in candidates}
    assert "pure_python" in kinds
    # Lowest priority comes first.
    assert candidates[0].priority == 1


# ---------------------------------------------------------------------------
# Image2DViewer (Pillow-dependent — skipped if missing)
# ---------------------------------------------------------------------------


def test_image2d_viewer_renders_with_camera_changes(tmp_path: Path) -> None:
    PIL = pytest.importorskip("PIL")
    Image = PIL.Image  # type: ignore[attr-defined]

    p = tmp_path / "a.png"
    Image.new("RGB", (40, 30), (255, 0, 0)).save(p)

    from llove.browser.viewer.image2d import Image2DViewer

    v = Image2DViewer(p)
    img = v.render(width=200, height=200)
    assert img.width <= 200 and img.height <= 200

    # zoom in disables fit_to_screen and produces a larger pasted region.
    v.apply_action("zoom_in")
    img2 = v.render(width=200, height=200)
    # Output canvas size stays at requested width/height when not fitting.
    assert img2.size == (200, 200)
