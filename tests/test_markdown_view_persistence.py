"""F15 (u3) — MarkdownView ↔ folding_persistence integration.

Once a document has a `doc_id`, MarkdownView should:

    1. Load the persisted FoldState on construction (so folds survive a
       relaunch of the app).
    2. Save the FoldState after every mutating fold operation
       (toggle / close-all / open-all).
    3. Fail-closed: I/O errors during save MUST NOT raise into the UI; we
       only need an empty render and a benign return.

This test file uses tmp_path as the persistence base, never the real
~/.config — every test is hermetic.
"""

from __future__ import annotations

from pathlib import Path


def _make_event(text: str):
    from llove.events import Event, EventKind

    return Event(kind=EventKind.NARRATION, payload={"text": text})


def test_view_with_doc_id_writes_state_on_close_all(tmp_path: Path) -> None:
    from llove.views.folding_persistence import (
        default_fold_state_path,
        load_fold_state,
    )
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(doc_id="docA", fold_persist_dir=tmp_path)
    v.feed(_make_event("# A\nbody A\n"))
    v.close_all_folds()

    expected_path = default_fold_state_path("docA", base_dir=tmp_path)
    assert expected_path.exists()

    loaded = load_fold_state(expected_path)
    # The "# A" heading lives at line 0 of last_source.
    assert 0 in loaded.closed_starts


def test_view_with_doc_id_loads_state_on_construction(tmp_path: Path) -> None:
    """A second view with the same doc_id picks up where the first left off."""
    from llove.views.folding import FoldState
    from llove.views.folding_persistence import save_fold_state
    from llove.views.markdown_view import MarkdownView

    # Pre-seed a state file with line 0 closed.
    base = tmp_path
    from llove.views.folding_persistence import default_fold_state_path

    path = default_fold_state_path("docB", base_dir=base)
    save_fold_state(FoldState(closed_starts={0}), path, doc_id="docB")

    v = MarkdownView(doc_id="docB", fold_persist_dir=base)
    assert v.fold_state.closed_starts == {0}
    # And feeding the matching document collapses the section automatically.
    v.feed(_make_event("# Pre-closed\nbody\n"))
    assert "body" not in v.last_render


def test_view_without_doc_id_does_not_write_anywhere(tmp_path: Path) -> None:
    """No doc_id ⇒ persistence is fully disabled (legacy behaviour)."""
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(fold_persist_dir=tmp_path)
    v.feed(_make_event("# A\nbody\n"))
    v.close_all_folds()
    # The directory is allowed not to exist, but if it does, it must be empty.
    if tmp_path.exists():
        assert list(tmp_path.iterdir()) == []


def test_view_toggle_fold_persists(tmp_path: Path) -> None:
    from llove.views.folding_persistence import (
        default_fold_state_path,
        load_fold_state,
    )
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(doc_id="docC", fold_persist_dir=tmp_path)
    v.feed(_make_event("# A\nbody\n"))
    v.toggle_fold(0)

    path = default_fold_state_path("docC", base_dir=tmp_path)
    assert load_fold_state(path).closed_starts == {0}

    v.toggle_fold(0)  # opening it again must persist the empty state too.
    assert load_fold_state(path).closed_starts == set()


def test_save_failure_does_not_raise(tmp_path: Path, monkeypatch) -> None:
    """If the underlying save raises, the view must shrug and continue."""
    from llove.views import markdown_view as mv_module
    from llove.views.markdown_view import MarkdownView

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(mv_module, "save_fold_state", boom)

    v = MarkdownView(doc_id="docD", fold_persist_dir=tmp_path)
    v.feed(_make_event("# A\nbody\n"))
    # Must NOT raise.
    v.close_all_folds()
    # And the in-memory state still updates correctly.
    assert v.fold_state.closed_starts == {0}


def test_save_folds_explicit_method(tmp_path: Path) -> None:
    """`view.save_folds()` is a no-arg public hook for callers that want
    to flush state at e.g. app shutdown."""
    from llove.views.folding_persistence import (
        default_fold_state_path,
        load_fold_state,
    )
    from llove.views.markdown_view import MarkdownView

    v = MarkdownView(doc_id="docE", fold_persist_dir=tmp_path)
    v.feed(_make_event("# A\nbody\n"))
    v.fold_state.close(0)  # mutate state directly (bypass auto-save)
    path = default_fold_state_path("docE", base_dir=tmp_path)
    # Direct mutation didn't trigger a save.
    assert not path.exists()
    v.save_folds()
    assert path.exists()
    assert load_fold_state(path).closed_starts == {0}
