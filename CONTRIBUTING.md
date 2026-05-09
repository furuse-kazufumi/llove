# Contributing to llove

Thanks for caring enough to help. This document covers the basics.

## Getting set up

```bash
git clone git@github.com:furuse-kazufumi/llove.git
cd llove
python -m venv .venv && source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -e ".[dev,all]"
pytest
```

Or open the repository in VS Code and click **Reopen in Container** — the
`.devcontainer/` config installs everything for you.

## Quality bar

Before opening a PR, please make sure:

- `ruff check llove/ tests/` is clean (the CI uses the strict ruleset in `pyproject.toml`).
- `pytest --cov=llove --cov-fail-under=80 -q` passes.
- `bandit -r llove/ -c pyproject.toml` reports zero issues. If you must
  suppress, use `# nosec BXXX - reason` on the exact line and explain.
- Public-facing changes (CLI flag, view, source kind, scenario) get a
  test alongside the change.

We mirror LLMesh's approach: tests, coverage, static analysis, and
robustness are first-class.

## Adding a demo scenario

Five-minute task — see [`docs/contributing-scenarios.md`](docs/contributing-scenarios.md).

```bash
cp llove/demo/scenarios/_template.py llove/demo/scenarios/my_thing.py
# edit, then add an entry to llove/demo/scenarios/__init__.py
llove demo --scenario my_thing
```

## Adding a data source

1. Create `llove/sources/<name>.py` and inherit from `DataSource`.
2. Implement `async def stream(self) -> AsyncIterator[Event]:` — yield Events.
3. Re-export from `llove/sources/__init__.py`.
4. Add tests under `tests/test_<name>_source.py`.

The same robustness rules apply: malformed input must produce empty / partial
output rather than a crash.

## Adding a view

1. Create `llove/views/<name>.py` inheriting from `Static, View`
   (the order matters — Textual's metaclass first).
2. Implement `feed(event: Event) -> None:`. Filter by `event.kind`.
3. Re-export from `llove/views/__init__.py`.
4. Add tests under `tests/test_views.py` or a dedicated `tests/test_<name>_view.py`.

Views should never raise; if they do, the App's dispatcher catches but logs
nothing — that hides bugs. Make your view fail-closed by validating payload
fields explicitly.

## Coding style

- **Type-annotate** function signatures and class attributes.
- **Pathlib** instead of `os.path`. (CI enforces via `PTH` lint rules.)
- **Pydantic v2** models for any wire-format struct.
- **Docstrings** at the top of every module describing the role.
- **Minimal comments** — only when the *why* is non-obvious; the code itself
  should explain the *what*.

## Commits & PRs

- Commit messages follow Conventional Commits where possible:
  `feat: …`, `fix: …`, `test: …`, `docs: …`, `refactor: …`.
- One PR = one change. If you find unrelated cleanup along the way, split it.
- Link the issue you're closing.

## Release checklist (maintainers)

1. Update `CHANGELOG.md` with the new version.
2. Bump `version` in `pyproject.toml`.
3. Tag: `git tag v0.X.Y && git push --tags`.
4. Build & upload: `python -m build && twine upload dist/*` (TestPyPI first).
5. Publish a GitHub Release with the changelog excerpt.

## Where to ask

- Issues: <https://github.com/furuse-kazufumi/llove/issues>
- PRs welcome — small, focused additions are easiest to merge.

Made with **llove**. 💗
