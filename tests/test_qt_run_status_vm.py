"""Stage 2 — run-status view-model tests (pure, no Qt).

``RunStatusVM`` reads an evolution run directory's ``run_manifest.json`` (config),
``run_summary.json`` (final state, present only once finished), and the live tail
of ``metrics.jsonl`` (current generation / best score) into one tolerant status
snapshot for the run-monitor panel (P7). File-boundary decoupling: it never
imports the engine (design §0.3 / §4).
"""

from __future__ import annotations

import json
from pathlib import Path

from llove.core.viewmodels.run_status import RunStatusVM

_MANIFEST = {
    "schema": "run_manifest/v1",
    "fitness": "proxy",
    "population": 32,
    "generations": 500,
    "seed": 2,
}
_SUMMARY = {
    "schema": "run_summary/v1",
    "status": "completed",
    "final_generation": 500,
    "best_score": 0.9491,
    "stopped_reason": "max_generations",
    "elapsed_seconds": 6.93,
}
_METRICS = (
    '{"generation":0,"best_score":0.74,"mean_score":0.5}\n'
    '{"generation":7,"best_score":0.81,"mean_score":0.6}\n'
)


def _write(run_dir: Path, *, manifest=True, summary=False, metrics=False) -> None:
    if manifest:
        (run_dir / "run_manifest.json").write_text(json.dumps(_MANIFEST), encoding="utf-8")
    if summary:
        (run_dir / "run_summary.json").write_text(json.dumps(_SUMMARY), encoding="utf-8")
    if metrics:
        (run_dir / "metrics.jsonl").write_text(_METRICS, encoding="utf-8")


def test_unknown_when_empty_dir(tmp_path: Path) -> None:
    st = RunStatusVM(tmp_path).refresh()
    assert st.status == "unknown"
    assert st.current_generation is None
    assert st.best_score is None


def test_running_with_manifest_and_live_metrics(tmp_path: Path) -> None:
    _write(tmp_path, manifest=True, metrics=True)
    st = RunStatusVM(tmp_path).refresh()
    assert st.status == "running"  # manifest present, no summary yet
    assert st.fitness == "proxy"
    assert st.population == 32
    assert st.target_generations == 500
    assert st.current_generation == 7  # from last metrics row
    assert st.best_score == 0.81  # live best, not summary


def test_completed_uses_summary(tmp_path: Path) -> None:
    _write(tmp_path, manifest=True, summary=True, metrics=True)
    st = RunStatusVM(tmp_path).refresh()
    assert st.status == "completed"
    assert st.stopped_reason == "max_generations"
    assert st.elapsed_seconds == 6.93
    # live metrics still drive current generation/best
    assert st.current_generation == 7


def test_completed_without_metrics_falls_back_to_summary(tmp_path: Path) -> None:
    _write(tmp_path, manifest=True, summary=True, metrics=False)
    st = RunStatusVM(tmp_path).refresh()
    assert st.status == "completed"
    assert st.current_generation == 500  # summary final_generation
    assert st.best_score == 0.9491


def test_tolerant_to_malformed_files(tmp_path: Path) -> None:
    (tmp_path / "run_manifest.json").write_text("{bad json", encoding="utf-8")
    (tmp_path / "metrics.jsonl").write_text("garbage\n", encoding="utf-8")
    st = RunStatusVM(tmp_path).refresh()
    # malformed manifest -> treated as absent -> unknown, no crash
    assert st.status == "unknown"
    assert st.current_generation is None
