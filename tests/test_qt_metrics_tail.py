"""Stage 1 Qt PoC — metrics tail reader tests (no Qt import).

``MetricsTailReader`` is the time-axis-agnostic, offset-based poller the Qt
worker drives (mirrors the ``TimelinePollDriver`` pattern in
``views/llive/dispatch.py``: the caller controls the polling cadence, the reader
just returns whatever is new since the last call). Tailing a live
``metrics.jsonl`` lets the GUI follow an evolution run without importing the
engine (file-boundary decoupling, design §0.3 / §4).
"""

from __future__ import annotations

from pathlib import Path

from llove.core.drivers.metrics_tail import MetricsTailReader

_ROW0 = '{"generation":0,"best_score":0.5,"mean_score":0.4}\n'
_ROW1 = '{"generation":1,"best_score":0.6,"mean_score":0.5}\n'
_ROW2 = '{"generation":2,"best_score":0.7,"mean_score":0.6}\n'


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    reader = MetricsTailReader(tmp_path / "nope.jsonl")
    assert reader.poll() == []


def test_reads_existing_then_only_new(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    p.write_text(_ROW0 + _ROW1, encoding="utf-8")
    reader = MetricsTailReader(p)
    first = reader.poll()
    assert [r["generation"] for r in first] == [0, 1]
    assert reader.poll() == []  # nothing new
    with p.open("a", encoding="utf-8") as fh:
        fh.write(_ROW2)
    assert [r["generation"] for r in reader.poll()] == [2]


def test_partial_last_line_not_consumed_until_complete(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    # second line has no trailing newline yet (writer mid-flush)
    p.write_text(_ROW0 + '{"generation":1,"best_score":0.6', encoding="utf-8")
    reader = MetricsTailReader(p)
    assert [r["generation"] for r in reader.poll()] == [0]
    with p.open("a", encoding="utf-8") as fh:
        fh.write(',"mean_score":0.5}\n')
    assert [r["generation"] for r in reader.poll()] == [1]


def test_malformed_lines_skipped_but_offset_advances(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    p.write_text("not json\n" + _ROW0 + "{bad}\n", encoding="utf-8")
    reader = MetricsTailReader(p)
    assert [r["generation"] for r in reader.poll()] == [0]
    assert reader.poll() == []  # offset advanced past the malformed lines


def test_truncation_resets_offset(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    p.write_text(_ROW0 + _ROW1 + _ROW2, encoding="utf-8")  # 3 rows
    reader = MetricsTailReader(p)
    assert len(reader.poll()) == 3
    # simulate a fresh run that rewrites a strictly shorter file (size shrinks
    # below the consumed offset -> detected as a rewrite, offset resets)
    p.write_text(_ROW0, encoding="utf-8")
    assert [r["generation"] for r in reader.poll()] == [0]


def test_reset_rereads_from_start(tmp_path: Path) -> None:
    p = tmp_path / "metrics.jsonl"
    p.write_text(_ROW0 + _ROW1, encoding="utf-8")
    reader = MetricsTailReader(p)
    assert len(reader.poll()) == 2
    reader.reset()
    assert [r["generation"] for r in reader.poll()] == [0, 1]
