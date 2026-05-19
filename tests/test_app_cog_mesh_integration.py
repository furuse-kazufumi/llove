"""M8.1 — LoveApp に CognitiveMeshPanel が env でオプション attach されるか."""

from __future__ import annotations

import pytest

from llove.app import ENV_ENABLE_COG_MESH, LoveApp


class _FakeSource:
    """LoveApp(source=...) に渡すだけのスタブ."""

    async def __aiter__(self):  # pragma: no cover — async iter は使わない
        return
        yield


def test_loveapp_default_no_cog_mesh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_ENABLE_COG_MESH, raising=False)
    app = LoveApp(source=_FakeSource())
    assert app._cog_mesh_enabled is False
    assert app._cog_mesh_panel is None


def test_loveapp_env_enables_cog_mesh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ENABLE_COG_MESH, "1")
    app = LoveApp(source=_FakeSource())
    assert app._cog_mesh_enabled is True
    # panel は compose() で初期化されるため、ここで is None は OK
    # 重要: enabled フラグが立っている


def test_loveapp_env_zero_keeps_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ENABLE_COG_MESH, "0")
    app = LoveApp(source=_FakeSource())
    assert app._cog_mesh_enabled is False


def test_loveapp_env_empty_keeps_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ENABLE_COG_MESH, "")
    app = LoveApp(source=_FakeSource())
    assert app._cog_mesh_enabled is False


def test_loveapp_env_arbitrary_value_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLOVE_ENABLE_COG_MESH=true は無視 — 厳密に '1' のみ."""
    monkeypatch.setenv(ENV_ENABLE_COG_MESH, "true")
    app = LoveApp(source=_FakeSource())
    assert app._cog_mesh_enabled is False
