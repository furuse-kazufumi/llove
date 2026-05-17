"""Tests for llove.engine Phase-1 skeleton."""
from __future__ import annotations

import pytest

from llove.engine import EngineInfo, engine_info


def test_engine_info_is_populated() -> None:
    """engine_info() returns a usable EngineInfo."""
    info = engine_info()
    assert isinstance(info, EngineInfo)
    assert info.name == "llove-engine"
    assert info.phase == "1-skeleton"
    # version may be "dev" when not installed; both forms are acceptable.
    assert info.version
    assert info.python  # python version string non-empty
    assert info.platform  # platform string non-empty


def test_engine_info_capabilities_include_phase1_layers() -> None:
    """Phase 1 advertises only the engine-shaped layers."""
    info = engine_info()
    caps = set(info.capabilities)
    # These four are explicitly listed in dogfooding-day0-gap.md as
    # "TUI coupling 1-2" — the Phase-1 candidates.
    assert {"sources", "export", "mcp", "events"} <= caps
    # views / widgets / window / term must NOT appear (Phase 2+).
    assert "views" not in caps
    assert "widgets" not in caps
    assert "window" not in caps
    assert "term" not in caps


def test_engine_info_to_dict_round_trip() -> None:
    info = engine_info()
    payload = info.to_dict()
    assert payload["name"] == "llove-engine"
    assert payload["phase"] == "1-skeleton"
    assert isinstance(payload["capabilities"], list)


# HTTP layer tests are gated on fastapi availability.
fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    from llove.engine import make_http_app
    return TestClient(make_http_app())


def test_healthz(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_engine_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/engine")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "llove-engine"
    assert body["phase"] == "1-skeleton"
    assert "sources" in body["capabilities"]


def test_audit_deps_stub_shape(client: TestClient) -> None:
    """Phase-1 stub: returns the expected JSON shape with zero deps."""
    response = client.get("/api/v1/audit/deps")
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["phase"] == "1-skeleton"
    assert body["summary"]["total"] == 0
    assert isinstance(body["dependencies"], list)


def test_offline_check_reports_clean(client: TestClient) -> None:
    response = client.get("/api/v1/audit/offline-check")
    assert response.status_code == 200
    body = response.json()
    assert body["outbound_calls_detected"] is False
    assert body["phase"] == "1-skeleton"
