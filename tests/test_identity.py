"""Tests for llove.identity — local node identity discovery.

Goal: every llove run starts with a verifiable did:key (when an llmesh
identity is reachable) or a friendly install hint (when it isn't). These
tests exercise both branches without depending on the maintainer's local
``D:/projects/llmesh/config`` checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llove.identity import LoveIdentity, load_local_identity


# ---------------------------------------------------------------------------
# Fixture: a self-contained llmesh-flavoured identity directory
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_identity_dir(tmp_path: Path) -> Path:
    """Create a dir with both ``node_identity.json`` and a 32-byte key."""
    pub_hex = "a5b2d38c32831e9f23f90074f30d31611d5982c0c23101eade77f54f3f463bec"
    payload = {
        "did": "did:key:z6MktestDIDtestDIDtestDIDtest",
        "node_id": "peer:CtestNodeIDtestNodeIDtest",
        "public_key_hex": pub_hex,
        "fingerprint": "00:11:22:33:44:55:66:77",
    }
    (tmp_path / "node_identity.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    # 32 zero bytes — not a real Ed25519 secret, but it is the right *length*,
    # which is what _read_identity_file's loader cares about.
    (tmp_path / "node.key.bin").write_bytes(b"\x00" * 32)
    return tmp_path


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_load_local_identity_uses_env_override_when_set(
    fake_identity_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "LLOVE_NODE_IDENTITY_FILE", str(fake_identity_dir / "node_identity.json")
    )
    ident = load_local_identity()
    assert ident is not None
    assert ident.did_key.startswith("did:key:")
    assert ident.node_id.startswith("peer:")
    assert ident.source == "env"
    # Sibling node.key.bin was 32 bytes → can_sign should be True even though
    # the bytes aren't a real Ed25519 secret. Signing itself may fail; the
    # discovery contract is purely "did we see a 32-byte private file".
    assert ident.can_sign is True


def test_load_local_identity_returns_none_when_nothing_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No env var, no canonical files → ``None`` (so the caller can fall
    through to the friendly "install llmesh-mcp" hint)."""
    # Point HOME and XDG into an empty tmp dir so the home-based lookups
    # all miss. The maintainer's D:/projects/llmesh path may exist on the
    # local box, so we patch ``_DEFAULT_LOCATIONS`` to ignore it.
    monkeypatch.delenv("LLOVE_NODE_IDENTITY_FILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    import llove.identity as ident_mod

    monkeypatch.setattr(ident_mod, "_DEFAULT_LOCATIONS", ())
    monkeypatch.setattr(ident_mod, "_try_llmesh_sdk", lambda: None)

    assert load_local_identity() is None


def test_load_local_identity_skips_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = tmp_path / "node_identity.json"
    bad.write_text("not valid json", encoding="utf-8")
    monkeypatch.setenv("LLOVE_NODE_IDENTITY_FILE", str(bad))

    import llove.identity as ident_mod

    monkeypatch.setattr(ident_mod, "_DEFAULT_LOCATIONS", ())
    monkeypatch.setattr(ident_mod, "_try_llmesh_sdk", lambda: None)

    # bad JSON in env → fall through, eventually return None.
    assert load_local_identity() is None


def test_load_local_identity_skips_partial_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A JSON file missing required fields must not produce a half-formed
    identity — we'd rather show the install hint than ship a broken did:key."""
    partial = tmp_path / "node_identity.json"
    partial.write_text(json.dumps({"did": "did:key:abc"}), encoding="utf-8")
    monkeypatch.setenv("LLOVE_NODE_IDENTITY_FILE", str(partial))

    import llove.identity as ident_mod

    monkeypatch.setattr(ident_mod, "_DEFAULT_LOCATIONS", ())
    monkeypatch.setattr(ident_mod, "_try_llmesh_sdk", lambda: None)

    assert load_local_identity() is None


# ---------------------------------------------------------------------------
# Audit payload shape — every run must carry these keys for downstream tools
# ---------------------------------------------------------------------------


def test_to_audit_payload_includes_required_keys() -> None:
    ident = LoveIdentity(
        did_key="did:key:z6Mkabc",
        node_id="peer:Cabc",
        public_key_hex="00" * 32,
        fingerprint="11:22:33",
        source="test",
    )
    payload = ident.to_audit_payload()
    assert payload["event"] == "llove.identity"
    assert payload["did"] == "did:key:z6Mkabc"
    assert payload["node_id"] == "peer:Cabc"
    assert payload["public_key_hex"] == "00" * 32
    assert payload["source"] == "test"
    # ``can_sign`` always present — downstream tools branch on it.
    assert payload["can_sign"] is False
    # ``display`` is what the audit pane shows; must mention the did at least.
    assert "did:key:z6Mkabc" in payload["display"]


def test_sign_returns_none_when_read_only() -> None:
    ident = LoveIdentity(
        did_key="did:key:abc",
        node_id="peer:abc",
        public_key_hex="00" * 32,
        fingerprint="",
        source="test",
    )
    assert ident.can_sign is False
    assert ident.sign(b"hello") is None


# ---------------------------------------------------------------------------
# End-to-end: real llmesh PoC checkout signs cleanly (skips elsewhere)
# ---------------------------------------------------------------------------


def test_real_llmesh_poc_checkout_loads_and_signs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Soft test: when the maintainer's PoC checkout is available at the
    canonical path, the identity must round-trip through Ed25519 sign/verify.
    Skipped on machines without the checkout so CI stays green."""
    poc = Path("D:/projects/llmesh/config/node_identity.json")
    if not poc.is_file():
        pytest.skip("no llmesh PoC checkout on this host")
    monkeypatch.delenv("LLOVE_NODE_IDENTITY_FILE", raising=False)
    ident = load_local_identity()
    assert ident is not None
    if not ident.can_sign:
        pytest.skip("identity reachable but private key unavailable")
    sig = ident.sign(b"verify-me")
    assert sig is not None
    assert len(sig) == 64

    # And verify with cryptography directly to prove it's a real Ed25519 sig.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(ident.public_key_hex))
    pub.verify(sig, b"verify-me")  # raises on bad sig
