"""F15 (u3) — fold state persistence to TOML.

Companion to `folding.py`. We split the I/O layer out so the pure data tier
stays free of filesystem concerns.

Storage path defaults to ``~/.config/llove/folds/<sanitised-doc-id>.toml``
(or the equivalent under ``$XDG_CONFIG_HOME``); callers may override via
``base_dir`` for tests or sandboxed runs.

Format::

    version = 1
    doc_id = "..."
    closed_starts = [0, 5, 12]

Fail-closed contract (u10): a missing, unreadable, malformed, or
wrong-version file produces an empty FoldState — never an exception. The
worst-case symptom for a corrupted state file is "folds open on next
launch", which is recoverable; an exception bubble would block the UI.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

from llove.views.folding import FoldState

FOLD_STATE_VERSION = 1
"""On-disk format version. Bumped when the schema changes incompatibly."""

# Path component sanitiser: keep alphanumerics, dot, hyphen, underscore.
# Anything else collapses to '_'. Conservative on purpose — fold doc ids
# can come from URLs, file paths, even user input.
_RE_UNSAFE_CHAR = re.compile(r"[^A-Za-z0-9._-]")


def _sanitise_doc_id(doc_id: str) -> str:
    """Map a free-form doc id into a single, safe path component."""
    if not isinstance(doc_id, str):
        raise ValueError("doc_id must be a string")
    stripped = doc_id.strip()
    if not stripped:
        raise ValueError("doc_id must be non-empty")
    safe = _RE_UNSAFE_CHAR.sub("_", stripped)
    # After sanitisation, separator-only inputs (e.g. "/", "\\") collapse to
    # an empty / underscore-only string. Reject those too — they have no
    # information content as a filename.
    if not safe.strip("._"):
        raise ValueError(f"doc_id {doc_id!r} reduces to an empty filename")
    return safe


def _default_base_dir() -> Path:
    """Resolve the OS-appropriate default config location."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "llove" / "folds"
    return Path.home() / ".config" / "llove" / "folds"


def default_fold_state_path(doc_id: str, *, base_dir: Path | None = None) -> Path:
    """Compute the canonical storage path for `doc_id`.

    Override `base_dir` for tests or sandboxed runs. The returned path is
    guaranteed to live under `base_dir` (resolved) — `doc_id` is sanitised
    so a hostile value like ``../../etc/passwd`` collapses into a single
    safe filename.
    """
    safe = _sanitise_doc_id(doc_id)
    base = base_dir if base_dir is not None else _default_base_dir()
    return base / f"{safe}.toml"


def _format_toml(state: FoldState, *, doc_id: str) -> str:
    """Render `state` as a small hand-written TOML document.

    We don't pull in tomli-w to keep the dependency surface minimal — our
    payload is just a version int, a doc_id string, and an int list, which
    are all trivially expressible. Arrays serialise sorted for stable
    diffs across runs.
    """
    closed_sorted = sorted(int(x) for x in state.closed_starts)
    array_body = ", ".join(str(n) for n in closed_sorted)
    # Escape any double-quote in doc_id; backslashes get the same treatment
    # so we don't accidentally emit invalid TOML for an unusual id.
    escaped_id = doc_id.replace("\\", "\\\\").replace('"', '\\"')
    return (
        f"version = {FOLD_STATE_VERSION}\n"
        f'doc_id = "{escaped_id}"\n'
        f"closed_starts = [{array_body}]\n"
    )


def save_fold_state(state: FoldState, path: Path, *, doc_id: str) -> None:
    """Write `state` to `path` in TOML form, creating parents as needed.

    Atomic-ish write: we serialise to a temp sibling then rename, so a
    crash mid-write doesn't leave a half-corrupted state file.
    """
    if not isinstance(state, FoldState):
        raise TypeError("state must be a FoldState")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _format_toml(state, doc_id=doc_id)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def load_fold_state(path: Path) -> FoldState:
    """Read a fold-state TOML file; return empty FoldState on any failure."""
    path = Path(path)
    try:
        text = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return FoldState()
    try:
        data = tomllib.loads(text.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return FoldState()
    version = data.get("version")
    if version != FOLD_STATE_VERSION:
        return FoldState()
    raw = data.get("closed_starts", [])
    if not isinstance(raw, list):
        return FoldState()
    cleaned = {int(x) for x in raw if isinstance(x, int) and not isinstance(x, bool)}
    return FoldState(closed_starts=cleaned)


__all__ = [
    "FOLD_STATE_VERSION",
    "default_fold_state_path",
    "load_fold_state",
    "save_fold_state",
]
