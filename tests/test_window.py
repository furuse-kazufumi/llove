"""F17 WindowManager 最小骨組みのテスト.

types / iconset / containers / manager / layout.toml を一括検証.
Pillow / PySide6 不在でも通る (純 Python).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from llove.window import (
    FreeContainer,
    LockedContainer,
    Window,
    WindowLayout,
    WindowManager,
    WindowSpec,
    WindowType,
    get_iconset,
    get_window_type,
    list_window_types,
    register_window_type,
)
from llove.window.iconset import _detect_kind

# ---------------------------------------------------------------------------
# WindowType + Registry
# ---------------------------------------------------------------------------


def test_builtins_registered_with_data_category() -> None:
    """ビルトインの 4 ペイン互換 + identity_panel が data / meta カテゴリ
    で登録されている."""
    types = list_window_types()
    ids = {w.id for w in types}
    assert "data.sensor_stream" in ids
    assert "data.spc_chart" in ids
    assert "data.audit_log" in ids
    assert "data.narration" in ids
    assert "meta.identity_panel" in ids


def test_list_window_types_filters_by_category() -> None:
    data_only = list_window_types(category="data")
    assert all(w.category == "data" for w in data_only)
    assert len(data_only) >= 4


def test_register_and_get_third_party_type() -> None:
    new_wt = WindowType(
        id="test.foo",
        display_name="Foo",
        category="debug",
        description="for tests",
    )
    register_window_type(new_wt)
    assert get_window_type("test.foo") is new_wt
    assert get_window_type("test.foo").display_name == "Foo"


def test_get_window_type_unknown_returns_none() -> None:
    assert get_window_type("nonexistent.x") is None


def test_window_type_is_frozen() -> None:
    wt = WindowType(id="x", display_name="X", category="debug")
    with pytest.raises(Exception):
        wt.id = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# IconSet
# ---------------------------------------------------------------------------


def test_iconset_ascii_returns_bracket_letters() -> None:
    s = get_iconset("ascii")
    assert s.kind == "ascii"
    assert s.for_window_type("data.sensor_stream") == "[~]"
    assert s.for_window_type("game.board") == "[B]"


def test_iconset_emoji_returns_unicode() -> None:
    s = get_iconset("emoji")
    assert s.kind == "emoji"
    assert s.for_window_type("data.sensor_stream") == "📡"


def test_iconset_nerd_returns_pua_glyphs() -> None:
    s = get_iconset("nerd")
    assert s.kind == "nerd"
    out = s.for_window_type("data.sensor_stream")
    # PUA / 高位コードポイント (U+E000+) を期待
    assert any(ord(c) >= 0xE000 for c in out)


def test_iconset_unknown_id_does_not_crash() -> None:
    """fail-closed: 未知 type_id でもクラッシュせず fallback 文字列を返す."""
    for kind in ("ascii", "emoji", "nerd"):
        s = get_iconset(kind)  # type: ignore[arg-type]
        out = s.for_window_type("totally.unknown")
        assert isinstance(out, str)
        assert out  # 非空


def test_iconset_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLOVE_ICONS", "ascii")
    assert _detect_kind() == "ascii"
    monkeypatch.setenv("LLOVE_ICONS", "nerd")
    assert _detect_kind() == "nerd"


# ---------------------------------------------------------------------------
# Containers — Free vs Locked
# ---------------------------------------------------------------------------


def test_free_container_add_remove() -> None:
    fc = FreeContainer()
    w = Window(type_id="data.audit_log")
    fc.add(w)
    assert len(fc) == 1
    fc.remove(w)
    assert len(fc) == 0


def test_locked_container_remove_is_forbidden() -> None:
    lc = LockedContainer()
    w = Window(type_id="data.sensor_stream", pinned=True)
    lc.add(w)
    with pytest.raises(PermissionError, match="cannot remove"):
        lc.remove(w)


def test_locked_container_clear_is_forbidden() -> None:
    lc = LockedContainer()
    lc.add(Window(type_id="data.sensor_stream", pinned=True))
    with pytest.raises(PermissionError, match="cannot clear"):
        lc.clear()


def test_window_group_find_by_type_id() -> None:
    fc = FreeContainer()
    fc.add(Window(type_id="a"))
    fc.add(Window(type_id="b"))
    found = fc.find("b")
    assert found is not None
    assert found.type_id == "b"
    assert fc.find("z") is None


# ---------------------------------------------------------------------------
# WindowManager + WindowLayout
# ---------------------------------------------------------------------------


def test_manager_register_view_uses_default_size_from_type() -> None:
    mgr = WindowManager()
    w = mgr.register_view("data.sensor_stream")
    # ビルトインのデフォルトサイズと一致
    assert w.size == (60, 20)
    assert w.title == "SensorEvent Stream"


def test_manager_register_view_unknown_falls_back_to_audit_log() -> None:
    """fail-closed: 未知 type_id は audit_log に置換 (UI を止めない)."""
    mgr = WindowManager()
    w = mgr.register_view("totally.unknown.type")
    assert w.type_id == "data.audit_log"


def test_manager_apply_layout_sets_locked_and_free() -> None:
    mgr = WindowManager()
    layout = WindowLayout(
        locked=(WindowSpec(type_id="data.sensor_stream", title="S"),
                WindowSpec(type_id="data.spc_chart", title="P")),
        free=(WindowSpec(type_id="data.audit_log"),),
        initial_mode="Tabbed",
    )
    mgr.apply_layout(layout)
    assert [w.title for w in mgr.locked] == ["S", "P"]
    assert len(mgr.free) == 1
    assert mgr.mode == "Tabbed"


def test_manager_apply_layout_resets_locked_each_time() -> None:
    """シナリオ切替で locked が clear されること (privileged)."""
    mgr = WindowManager()
    mgr.apply_layout(WindowLayout(locked=(WindowSpec(type_id="data.sensor_stream"),)))
    mgr.apply_layout(WindowLayout(locked=(WindowSpec(type_id="data.audit_log"),)))
    # 1 つ目の sensor_stream は消え、新しい audit_log だけ
    assert [w.type_id for w in mgr.locked] == ["data.audit_log"]


def test_manager_to_toml_round_trip(tmp_path: Path) -> None:
    mgr = WindowManager(mode="MDI")
    mgr.register_view("data.sensor_stream", group="locked", title="Sensors")
    mgr.register_view("data.audit_log", group="free", title="Audit")
    p = tmp_path / "layout.toml"
    mgr.save(p)
    mgr2 = WindowManager.load(p)
    assert mgr2.mode == "MDI"
    assert [w.title for w in mgr2.locked] == ["Sensors"]
    assert [w.title for w in mgr2.free] == ["Audit"]
    assert mgr2.locked.windows[0].pinned is True
    assert mgr2.free.windows[0].pinned is False


def test_manager_toml_unknown_type_id_falls_back_during_load() -> None:
    """壊れた layout.toml でも UI を止めない."""
    bad = """
[meta]
mode = "MDI"

[[window]]
group = "free"
type_id = "totally.unknown.type"
title = "lost"
size = [40, 10]
position = [0, 0]
state = "normal"
pinned = false
"""
    mgr = WindowManager.from_toml(bad)
    # type_id は unknown のまま保持されるが、title はそのまま
    # (load 時点では fallback せず、register_view 時の fallback ロジック
    # と分けている。ここでは「壊れた id でもクラッシュしない」のみ確認)
    assert len(mgr.free) == 1
    assert mgr.free.windows[0].type_id == "totally.unknown.type"
