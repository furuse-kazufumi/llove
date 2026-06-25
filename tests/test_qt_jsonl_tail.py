"""Stage 3 — generic JSONL tail reader tests (pure, no Qt).

``JsonlTailReader`` returns any complete line that parses to a JSON object, used
for run artifacts that are not metrics rows (e.g. ``founder_lineage.jsonl``). It
shares the offset mechanics with the metrics reader (partial-line safe, skips
malformed, resets on truncation).
"""

from __future__ import annotations

from pathlib import Path

from llove.core.drivers.jsonl_tail import JsonlTailReader

_A = '{"generation":0,"founder_counts":{"a":2}}\n'
_B = '{"generation":1,"founder_counts":{"a":1,"b":1}}\n'


def test_missing_file_returns_empty(tmp_path: Path) -> None:
    assert JsonlTailReader(tmp_path / "nope.jsonl").poll() == []


def test_reads_existing_then_only_new(tmp_path: Path) -> None:
    p = tmp_path / "founder_lineage.jsonl"
    p.write_text(_A + _B, encoding="utf-8")
    reader = JsonlTailReader(p)
    rows = reader.poll()
    assert [r["generation"] for r in rows] == [0, 1]
    assert reader.poll() == []
    with p.open("a", encoding="utf-8") as fh:
        fh.write('{"generation":2,"founder_counts":{"a":3}}\n')
    assert [r["generation"] for r in reader.poll()] == [2]


def test_skips_malformed_and_non_objects(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text("not json\n[1,2,3]\n" + _A, encoding="utf-8")
    rows = JsonlTailReader(p).poll()
    assert [r["generation"] for r in rows] == [0]


def test_partial_last_line_not_consumed(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    p.write_text(_A + '{"generation":1', encoding="utf-8")
    reader = JsonlTailReader(p)
    assert [r["generation"] for r in reader.poll()] == [0]
    with p.open("a", encoding="utf-8") as fh:
        fh.write(',"founder_counts":{"a":1}}\n')
    assert [r["generation"] for r in reader.poll()] == [1]
