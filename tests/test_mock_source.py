"""Tests for the synthetic MockSource."""

from __future__ import annotations

import pytest

from llove.events import EventKind
from llove.sources.mock import MockSource


@pytest.mark.asyncio
async def test_mock_source_emits_sensor_events(mock_source: MockSource) -> None:
    seen: list[EventKind] = []
    async for ev in mock_source.stream():
        seen.append(ev.kind)
        if len(seen) >= 30:
            break
    assert EventKind.SENSOR in seen


@pytest.mark.asyncio
async def test_mock_source_emits_alarms_during_drift_phase() -> None:
    src = MockSource(seed=42, tick_seconds=0.001)
    seen: list[EventKind] = []
    async for ev in mock_source_collect(src, count=400):
        seen.append(ev.kind)
    assert EventKind.SPC_ALARM in seen


@pytest.mark.asyncio
async def test_mock_source_is_deterministic_with_seed() -> None:
    a = await _first_n(MockSource(seed=99, tick_seconds=0.001), 50)
    b = await _first_n(MockSource(seed=99, tick_seconds=0.001), 50)
    a_keys = [(e.kind.value, e.payload.get("value")) for e in a if e.kind == EventKind.SENSOR]
    b_keys = [(e.kind.value, e.payload.get("value")) for e in b if e.kind == EventKind.SENSOR]
    assert a_keys == b_keys


async def mock_source_collect(src: MockSource, *, count: int):
    yielded = 0
    async for ev in src.stream():
        yield ev
        yielded += 1
        if yielded >= count:
            break


async def _first_n(src: MockSource, n: int):
    out = []
    async for ev in src.stream():
        out.append(ev)
        if len(out) >= n:
            break
    return out
