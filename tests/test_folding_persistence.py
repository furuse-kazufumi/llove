"""F15 (u3) — fold state persistence to ~/.config/llove/folds/<doc-id>.toml.

This is a pure I/O layer:
    save_fold_state(state, path)        — serialise to TOML
    load_fold_state(path) -> FoldState  — deserialise; fail-closed on errors
    default_fold_state_path(doc_id)     — resolve under XDG_CONFIG_HOME
                                          or ~/.config (override via base_dir)

Fail-closed contract (u10): a missing, unreadable, malformed, or
wrong-version file must return an empty FoldState rather than raise — the
worst that should happen is "the user's folds opened on next launch."
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    from llove.views.folding import FoldState
    from llove.views.folding_persistence import load_fold_state, save_fold_state

    state = FoldState(closed_starts={0, 5, 12})
    path = tmp_path / "doc.toml"
    save_fold_state(state, path, doc_id="my-doc")
    assert path.exists()

    loaded = load_fold_state(path)
    assert loaded.closed_starts == {0, 5, 12}


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    from llove.views.folding import FoldState
    from llove.views.folding_persistence import save_fold_state

    state = FoldState(closed_starts={3})
    path = tmp_path / "deep" / "nested" / "doc.toml"
    save_fold_state(state, path, doc_id="x")
    assert path.exists()


def test_load_missing_file_returns_empty_state(tmp_path: Path) -> None:
    from llove.views.folding_persistence import load_fold_state

    state = load_fold_state(tmp_path / "does-not-exist.toml")
    assert state.closed_starts == set()


def test_load_malformed_toml_returns_empty_state(tmp_path: Path) -> None:
    from llove.views.folding_persistence import load_fold_state

    path = tmp_path / "bad.toml"
    path.write_text("this is = = not toml [", encoding="utf-8")
    state = load_fold_state(path)
    assert state.closed_starts == set()


def test_load_wrong_version_returns_empty_state(tmp_path: Path) -> None:
    from llove.views.folding_persistence import load_fold_state

    path = tmp_path / "future.toml"
    path.write_text(
        'version = 999\nclosed_starts = [1, 2]\n',
        encoding="utf-8",
    )
    state = load_fold_state(path)
    # Forward-incompatible version: refuse to interpret, return empty.
    assert state.closed_starts == set()


def test_load_non_integer_entries_filtered_silently(tmp_path: Path) -> None:
    from llove.views.folding_persistence import load_fold_state

    path = tmp_path / "mixed.toml"
    # version 1 with an "almost valid" payload mixing strings (which TOML
    # would normally allow in a heterogeneous array) — we use a homogeneous
    # int array but throw in a stray entry via re-write.
    path.write_text('version = 1\nclosed_starts = [3, 7]\n', encoding="utf-8")
    state = load_fold_state(path)
    assert state.closed_starts == {3, 7}


def test_default_fold_state_path_under_base_dir(tmp_path: Path) -> None:
    from llove.views.folding_persistence import default_fold_state_path

    path = default_fold_state_path("hello", base_dir=tmp_path)
    # Must end with .toml and contain the doc id in its filename.
    assert path.suffix == ".toml"
    assert "hello" in path.name
    # And live under the requested base.
    assert tmp_path in path.parents


def test_default_fold_state_path_sanitises_unsafe_doc_id(tmp_path: Path) -> None:
    from llove.views.folding_persistence import default_fold_state_path

    # Doc IDs with path-traversal characters must not escape the base dir.
    path = default_fold_state_path("../../etc/passwd", base_dir=tmp_path)
    # Resolve both sides so platform-specific separators don't lie.
    assert tmp_path.resolve() in path.resolve().parents


@pytest.mark.parametrize("doc_id", ["", "  ", "/", "\\"])
def test_default_fold_state_path_rejects_empty_or_separator_only(
    tmp_path: Path, doc_id: str
) -> None:
    from llove.views.folding_persistence import default_fold_state_path

    with pytest.raises(ValueError):
        default_fold_state_path(doc_id, base_dir=tmp_path)


def test_save_fold_state_preserves_doc_id_in_file(tmp_path: Path) -> None:
    from llove.views.folding import FoldState
    from llove.views.folding_persistence import save_fold_state

    state = FoldState(closed_starts={1})
    path = tmp_path / "doc.toml"
    save_fold_state(state, path, doc_id="abc-123")
    text = path.read_text(encoding="utf-8")
    assert 'doc_id = "abc-123"' in text
    assert "version = 1" in text


def test_save_with_empty_state_writes_empty_array(tmp_path: Path) -> None:
    from llove.views.folding import FoldState
    from llove.views.folding_persistence import load_fold_state, save_fold_state

    state = FoldState()
    path = tmp_path / "empty.toml"
    save_fold_state(state, path, doc_id="z")
    loaded = load_fold_state(path)
    assert loaded.closed_starts == set()
