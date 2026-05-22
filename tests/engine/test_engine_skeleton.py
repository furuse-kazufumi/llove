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


def test_audit_deps_shape(client: TestClient) -> None:
    """Phase 1 (stub) or Phase 2 (proxy) — both must expose the same shape.

    The endpoint dynamically picks Phase 2 when llmesh is importable in
    the same environment (2026-05-23 wiring). The skeleton shape — keys
    and value types — stays identical so UIs render either mode.
    """
    response = client.get("/api/v1/audit/deps")
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["phase"] in ("1-skeleton", "2-proxy")
    # Same envelope for both modes
    assert isinstance(body["summary"]["total"], int)
    assert isinstance(body["summary"]["origin_breakdown"], dict)
    assert isinstance(body["summary"]["supply_risk"], dict)
    for key in ("high", "medium", "low", "unknown"):
        assert key in body["summary"]["supply_risk"]
    assert isinstance(body["dependencies"], list)
    if body["metadata"]["phase"] == "1-skeleton":
        # Phase-1 fallback must reveal why proxy fell back.
        assert body["summary"]["total"] == 0
        assert "reason" in body["metadata"]
    else:
        # Phase-2 proxy must expose at least one dep in the test env.
        assert body["summary"]["total"] >= 1
        assert any(
            d.get("name") for d in body["dependencies"]
        ), "proxy returned empty dependencies — broken upstream"


def test_audit_deps_phase1_fallback_when_llmesh_missing(
    client: TestClient, monkeypatch
) -> None:
    """Force Phase-1 fallback by hiding llmesh in sys.modules."""
    import sys
    # Remove every cached llmesh.* entry; freshly importing will see the
    # ImportError we inject below.
    cached = [k for k in sys.modules if k == "llmesh" or k.startswith("llmesh.")]
    for k in cached:
        monkeypatch.delitem(sys.modules, k, raising=False)

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "llmesh" or name.startswith("llmesh."):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name.split(".")[0])
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    response = client.get("/api/v1/audit/deps")
    assert response.status_code == 200
    body = response.json()
    assert body["metadata"]["phase"] == "1-skeleton"
    assert body["metadata"]["missing_module"] == "llmesh"
    assert body["summary"]["total"] == 0


def test_offline_check_reports_clean(client: TestClient) -> None:
    response = client.get("/api/v1/audit/offline-check")
    assert response.status_code == 200
    body = response.json()
    assert body["outbound_calls_detected"] is False
    assert body["phase"] == "1-skeleton"
