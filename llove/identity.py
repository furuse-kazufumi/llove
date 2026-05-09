"""Local node identity for llove — Ed25519 + did:key.

llmesh ships every node with an Ed25519 keypair the moment it boots: a
``node_identity.json`` that holds the public surface (``did:key``, ``node_id``,
``public_key_hex``, ``fingerprint``) and a ``node.key.bin`` that holds the
raw 32-byte private key. llove reuses that identity wherever possible so
*every* demo (and every JSONL log it writes) starts with a verifiable
"this run came from peer:…" line.

Discovery order (first match wins; all silent on failure):

1. ``LLOVE_NODE_IDENTITY_FILE`` env var → path to a ``node_identity.json``
   (and an optional sibling ``node.key.bin`` for signing).
2. ``D:/projects/llmesh/config/node_identity.json`` — the canonical PoC
   path on the maintainer's box.
3. ``~/.llmesh/node_identity.json``                 — the standard install path.
4. ``$XDG_CONFIG_HOME/llmesh/node_identity.json``   — XDG fallback.
5. ``llmesh.identity.NodeIdentity`` if the ``llmesh-mcp`` SDK is installed
   and a ``node.key.bin`` is reachable.
6. ``None`` — llove still works, just without an embedded identity.

The identity is always **read**-only here: llove never generates or rotates
keys. Key creation belongs to llmesh.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Public type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoveIdentity:
    """Read-only view of the local node's Ed25519 identity.

    The public-key surface (``did_key`` / ``node_id`` / ``public_key_hex`` /
    ``fingerprint``) is always populated. ``can_sign`` is True only when we
    were able to load the private key bytes too.
    """

    did_key: str
    node_id: str
    public_key_hex: str
    fingerprint: str
    source: str  # diagnostic — which discovery branch hit
    _private_key_bytes: bytes | None = None

    @property
    def can_sign(self) -> bool:
        return self._private_key_bytes is not None

    def to_audit_payload(self) -> dict[str, str | bool]:
        """Compact dict for the opening AUDIT event — safe to log verbatim."""
        return {
            "event": "llove.identity",
            "did": self.did_key,
            "node_id": self.node_id,
            "public_key_hex": self.public_key_hex,
            "fingerprint": self.fingerprint,
            "source": self.source,
            "can_sign": self.can_sign,
            "display": (
                f"🔑 identity: {self.did_key}  "
                f"(fp {self.fingerprint}, src {self.source}"
                + (", sign✓" if self.can_sign else "")
                + ")"
            ),
        }

    def sign(self, message: bytes) -> bytes | None:
        """Sign ``message`` with the local private key, if available.

        Returns ``None`` when the identity is read-only (only the public
        side was loaded). We deliberately do *not* raise — most callers are
        OK going unsigned, and the audit pane will already have shown
        ``can_sign=False``.
        """
        if self._private_key_bytes is None:
            return None
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                Ed25519PrivateKey,
            )
        except ImportError:
            # cryptography is a transitive dep we expect to have; if it
            # genuinely isn't there, downgrade gracefully.
            return None
        return Ed25519PrivateKey.from_private_bytes(self._private_key_bytes).sign(message)


# ---------------------------------------------------------------------------
# Discovery / loading
# ---------------------------------------------------------------------------

_DEFAULT_LOCATIONS: tuple[Path, ...] = (
    # Maintainer's PoC checkout — useful during development.
    Path("D:/projects/llmesh/config/node_identity.json"),
    # Standard llmesh install path.
    Path.home() / ".llmesh" / "node_identity.json",
)


def _xdg_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "llmesh" / "node_identity.json"
    return Path.home() / ".config" / "llmesh" / "node_identity.json"


def _read_identity_file(path: Path, *, source_label: str) -> LoveIdentity | None:
    """Parse ``node_identity.json`` and try to grab a sibling ``node.key.bin``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    did = data.get("did") or data.get("did_key")
    node_id = data.get("node_id")
    pub_hex = data.get("public_key_hex")
    fingerprint = data.get("fingerprint", "")
    if not (did and node_id and pub_hex):
        return None

    # The private key file is conventionally next to the JSON. We try a few
    # well-known names but never *require* it — read-only identity is fine.
    private_bytes: bytes | None = None
    for candidate in ("node.key.bin", "node.key", "private.bin"):
        kp = path.with_name(candidate)
        if kp.is_file():
            try:
                raw = kp.read_bytes()
            except OSError:
                raw = b""
            if len(raw) == 32:
                private_bytes = raw
                break

    return LoveIdentity(
        did_key=did,
        node_id=node_id,
        public_key_hex=pub_hex,
        fingerprint=fingerprint,
        source=source_label,
        _private_key_bytes=private_bytes,
    )


def _try_llmesh_sdk() -> LoveIdentity | None:
    """If ``llmesh-mcp`` is installed and there's a private key on disk we
    haven't seen yet, build a LoveIdentity from its ``NodeIdentity``."""
    try:
        from llmesh.identity.node_id import NodeIdentity  # type: ignore[import-not-found]
    except ImportError:
        return None

    # Same default locations, but this branch reaches for the *.key.bin* file
    # because the SDK can derive every public field from the private key.
    candidates = (
        Path("D:/projects/llmesh/config/node.key.bin"),
        Path.home() / ".llmesh" / "node.key.bin",
        Path(_xdg_path().parent) / "node.key.bin",
    )
    for kp in candidates:
        if not kp.is_file():
            continue
        try:
            raw = kp.read_bytes()
        except OSError:
            continue
        if len(raw) != 32:
            continue
        try:
            ni = NodeIdentity.from_private_bytes(raw)
        except Exception:  # nosec B112 — fail-closed: bad key file → next candidate.
            continue
        return LoveIdentity(
            did_key=ni.did_key,
            node_id=ni.node_id,
            public_key_hex=ni.public_key_hex,
            fingerprint="",  # SDK doesn't surface a fingerprint; OK.
            source="llmesh.sdk",
            _private_key_bytes=raw,
        )
    return None


def load_local_identity() -> LoveIdentity | None:
    """Resolve the local node identity using llmesh's discovery order.

    Returns ``None`` if nothing usable was found. Callers must treat that as
    "run anonymously" rather than as an error.
    """
    # 1. Explicit override.
    env = os.environ.get("LLOVE_NODE_IDENTITY_FILE")
    if env:
        ident = _read_identity_file(Path(env), source_label="env")
        if ident is not None:
            return ident

    # 2/3/4. Default file locations.
    for path in (*_DEFAULT_LOCATIONS, _xdg_path()):
        if path.is_file():
            ident = _read_identity_file(path, source_label=str(path))
            if ident is not None:
                return ident

    # 5. llmesh SDK as last resort (uses raw private key on disk).
    return _try_llmesh_sdk()
