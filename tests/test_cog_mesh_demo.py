"""M8.1 stand-alone CogMeshDemoApp smoke test."""

from __future__ import annotations

import pytest

from llove.demo.cog_mesh_demo import CogMeshDemoApp


def test_demo_app_constructs() -> None:
    app = CogMeshDemoApp()
    assert app.panel is not None
    assert app.panel.entry_count() == 0


def test_demo_app_panel_accepts_mock_events() -> None:
    from llove.views.llive.cognitive_mesh_panel import make_mock_cog_events

    app = CogMeshDemoApp()
    app.panel.feed_events(make_mock_cog_events(3))
    assert app.panel.entry_count() == 3


def test_demo_app_action_clear() -> None:
    from llove.views.llive.cognitive_mesh_panel import make_mock_cog_events

    app = CogMeshDemoApp()
    app.panel.feed_events(make_mock_cog_events(3))
    app.action_clear_panel()
    assert app.panel.entry_count() == 0


def test_demo_app_action_refresh_increments_counter() -> None:
    app = CogMeshDemoApp()
    initial = app._tick_counter
    app.action_refresh()
    assert app._tick_counter == initial + 1
    # 3 件追加されている
    assert app.panel.entry_count() == 3


def test_demo_app_auto_tick_flag_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLOVE_DEMO_AUTO_TICK", "1")
    monkeypatch.setenv("LLOVE_DEMO_TICK_INTERVAL", "0.5")
    app = CogMeshDemoApp()
    assert app._auto_tick is True
    assert app._tick_interval == 0.5
