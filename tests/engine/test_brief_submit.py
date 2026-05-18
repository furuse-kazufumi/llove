"""Tests for F25 Phase h.1 — POST /api/v1/brief/submit.

Validates the endpoint shape against docs/design/f25-phase-h-e2e.md 4.6.1
(draft v0.2). The endpoint lazy-imports llive; we stub
``llive.mcp.tools.tool_submit_brief`` via ``sys.modules`` so the tests pass
both with and without llive installed.
"""
from __future__ import annotations

import sys
import types
from typing import Any
from unittest import mock

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def stub_llive(monkeypatch: pytest.MonkeyPatch) -> mock.MagicMock:
    """Install a fake llive.mcp.tools module returning a canned BriefResult."""
    fake_tool = mock.MagicMock(
        return_value={
            "brief": {
                "brief_id": "mcp-stub",
                "goal": "stub goal",
                "constraints": [],
                "source": "engine",
                "priority": 0.5,
                "backend": "",
                "tools": [],
                "success_criteria": [],
                "approval_required": True,
            },
            "result": {
                "brief_id": "mcp-stub",
                "status": "ok",
                "rationale": "stub-rationale",
                "artifacts": [],
                "ledger_entries": [],
                "error": None,
            },
        }
    )

    fake_tools_mod = types.ModuleType("llive.mcp.tools")
    fake_tools_mod.tool_submit_brief = fake_tool  # type: ignore[attr-defined]

    fake_mcp_mod = types.ModuleType("llive.mcp")
    fake_mcp_mod.tools = fake_tools_mod  # type: ignore[attr-defined]

    fake_llive_mod = types.ModuleType("llive")
    fake_llive_mod.mcp = fake_mcp_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "llive", fake_llive_mod)
    monkeypatch.setitem(sys.modules, "llive.mcp", fake_mcp_mod)
    monkeypatch.setitem(sys.modules, "llive.mcp.tools", fake_tools_mod)
    return fake_tool


@pytest.fixture()
def client() -> TestClient:
    from llove.engine import make_http_app

    return TestClient(make_http_app())


def test_submit_brief_success_returns_brief_result_shape(
    client: TestClient,
    stub_llive: mock.MagicMock,
) -> None:
    """Happy path — endpoint returns the {brief, result} envelope."""
    response = client.post(
        "/api/v1/brief/submit",
        json={"goal": "do the thing", "approval_required": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"brief", "result"}
    assert body["result"]["status"] == "ok"
    assert body["result"]["brief_id"] == "mcp-stub"


def test_submit_brief_passes_all_fields_to_llive(
    client: TestClient,
    stub_llive: mock.MagicMock,
) -> None:
    """All schema fields reach tool_submit_brief as kwargs."""
    payload = {
        "goal": "test goal",
        "brief_id": "user-supplied-id",
        "constraints": ["c1", "c2"],
        "source": "vscode",
        "priority": 0.75,
        "backend": "openai",
        "tools": ["tool_a"],
        "success_criteria": ["sc1"],
        "approval_required": False,
    }
    client.post("/api/v1/brief/submit", json=payload)

    stub_llive.assert_called_once()
    kwargs = stub_llive.call_args.kwargs
    assert kwargs["goal"] == "test goal"
    assert kwargs["brief_id"] == "user-supplied-id"
    assert kwargs["constraints"] == ["c1", "c2"]
    assert kwargs["source"] == "vscode"
    assert kwargs["priority"] == 0.75
    assert kwargs["backend"] == "openai"
    assert kwargs["tools"] == ["tool_a"]
    assert kwargs["success_criteria"] == ["sc1"]
    assert kwargs["approval_required"] is False


def test_submit_brief_defaults_applied_when_optional_fields_omitted(
    client: TestClient,
    stub_llive: mock.MagicMock,
) -> None:
    """Only ``goal`` is mandatory; everything else has the documented defaults."""
    client.post("/api/v1/brief/submit", json={"goal": "minimal"})

    kwargs = stub_llive.call_args.kwargs
    assert kwargs["constraints"] == []
    assert kwargs["source"] == "engine"
    assert kwargs["priority"] == 0.5
    assert kwargs["backend"] == ""
    assert kwargs["tools"] == []
    assert kwargs["success_criteria"] == []
    assert kwargs["approval_required"] is True


def test_submit_brief_empty_goal_returns_422(
    client: TestClient,
    stub_llive: mock.MagicMock,
) -> None:
    """Empty goal is rejected by Pydantic (min_length=1) → 422.

    Note: the spec lists 400 for "invalid_goal"; FastAPI/Pydantic emit 422
    for schema validation. Both signal client error; the body distinguishes
    the cause. We accept 422 here as the canonical empty-goal signal and
    document it; a future revision can normalise to 400 if needed.
    """
    response = client.post("/api/v1/brief/submit", json={"goal": ""})
    assert response.status_code == 422
    stub_llive.assert_not_called()


def test_submit_brief_missing_goal_returns_422(
    client: TestClient,
    stub_llive: mock.MagicMock,
) -> None:
    """Missing ``goal`` → 422 from Pydantic."""
    response = client.post("/api/v1/brief/submit", json={})
    assert response.status_code == 422
    stub_llive.assert_not_called()


def test_submit_brief_503_when_llive_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``llive.mcp.tools`` cannot be imported → 503 backend_unavailable.

    Achieved by NOT installing the stub_llive fixture and forcing
    ``import llive.mcp.tools`` to raise ModuleNotFoundError.
    """
    # Remove any cached llive modules so the lazy import raises.
    for mod_name in ("llive", "llive.mcp", "llive.mcp.tools"):
        monkeypatch.delitem(sys.modules, mod_name, raising=False)

    # Sabotage the import path: any attempt to import llive.* must fail.
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "llive.mcp.tools" or name.startswith("llive."):
            raise ModuleNotFoundError(f"No module named {name!r}", name=name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    response = client.post("/api/v1/brief/submit", json={"goal": "x"})
    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["error"] == "backend_unavailable"
    assert "llive" in body["detail"]["reason"]
