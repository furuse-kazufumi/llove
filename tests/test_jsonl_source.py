"""Tests for JSONLSource."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llove.events import EventKind
from llove.sources.jsonl import JSONLSource


@pytest.mark.asyncio
async def test_jsonl_reads_finite_file(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    lines = [
        {"kind": "sensor", "source_id": "t", "payload": {"sensor_id": "s1", "value": 10.0}},
        {"kind": "audit", "source_id": "t", "payload": {"event": "ok"}},
        {"kind": "llm_call", "payload": {"tokens": 100, "latency_ms": 200}},
    ]
    p.write_text("\n".join(json.dumps(o) for o in lines), encoding="utf-8")

    seen = []
    async for ev in JSONLSource(p).stream():
        seen.append(ev.kind)

    assert seen == [EventKind.SENSOR, EventKind.AUDIT, EventKind.LLM_CALL]


@pytest.mark.asyncio
async def test_jsonl_skips_invalid_lines(tmp_path: Path) -> None:
    p = tmp_path / "broken.jsonl"
    p.write_text(
        "\n".join(
            [
                "not json",
                json.dumps({"kind": "audit", "payload": {"event": "ok"}}),
                "{not closed",
                json.dumps({"kind": "??unknown??", "payload": {}}),
                json.dumps({"payload": {"missing": "kind"}}),
                json.dumps({"kind": "sensor", "payload": {"sensor_id": "s", "value": 1}}),
            ]
        ),
        encoding="utf-8",
    )
    seen = []
    async for ev in JSONLSource(p).stream():
        seen.append(ev.kind)
    assert seen == [EventKind.AUDIT, EventKind.SENSOR]


@pytest.mark.asyncio
async def test_jsonl_missing_file_yields_nothing(tmp_path: Path) -> None:
    p = tmp_path / "absent.jsonl"
    seen = [ev async for ev in JSONLSource(p).stream()]
    assert seen == []
