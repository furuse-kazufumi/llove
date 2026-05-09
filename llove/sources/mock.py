"""MockSource — synthesises a believable mix of events for demos and tests.

The data follows a 3-phase scenario inspired by SCADA incidents:
    Phase 1 (0-10s): Normal operation
    Phase 2 (10-25s): Drift / alarm
    Phase 3 (25-40s): Recovery + LLM explanation

The scenario is reproducible (default seed=42) so tests can assert exact event
sequences. Pass ``seed=None`` for non-deterministic demo runs.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from llove.events import Event, EventKind
from llove.sources.base import DataSource

_AUDIT_TEMPLATES: list[dict[str, str]] = [
    {"event": "firewall.allow", "layer": "L2"},
    {"event": "rag.search", "query_id": "q-{n}"},
    {"event": "llm.complete", "tokens": "{tokens}"},
    {"event": "audit.persist", "log_id": "a-{n}"},
]


class MockSource(DataSource):
    """Synthetic event stream for demos, tutorials, and unit tests."""

    name = "mock"

    def __init__(self, *, seed: int | None = 42, tick_seconds: float = 0.1) -> None:
        self._rng = random.Random(seed) if seed is not None else random.Random()
        self._tick = tick_seconds
        self._step = 0

    async def stream(self) -> AsyncIterator[Event]:
        sensor_id = "bearing_temp_07"
        baseline = 70.0
        while True:
            phase = self._phase(self._step)
            value = self._sensor_value(baseline, phase)

            yield Event(
                kind=EventKind.SENSOR,
                ts=datetime.now(tz=UTC),
                source_id=self.name,
                payload={"sensor_id": sensor_id, "value": round(value, 2), "quality": "good"},
            )

            if phase == "alarm" and self._step % 30 == 0:
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id=self.name,
                    payload={
                        "sensor_id": sensor_id,
                        "cusum": round(self._rng.uniform(5.0, 12.0), 1),
                        "threshold": 5.0,
                    },
                )

            if self._step % 20 == 0:
                tpl = self._rng.choice(_AUDIT_TEMPLATES)
                payload = {
                    k: v.format(n=self._step, tokens=self._rng.randint(120, 400))
                    for k, v in tpl.items()
                }
                yield Event(kind=EventKind.AUDIT, source_id=self.name, payload=payload)

            if phase == "recover" and self._step % 50 == 0:
                yield Event(
                    kind=EventKind.LLM_CALL,
                    source_id=self.name,
                    payload={
                        "tokens": self._rng.randint(180, 380),
                        "latency_ms": self._rng.randint(180, 600),
                        "model": "llama3.2",
                        "kind": "incident_explanation",
                    },
                )

            self._step += 1
            await asyncio.sleep(self._tick)

    # Phase boundaries are step-based (not wall-clock) so the scenario stays
    # reproducible regardless of the chosen tick_seconds. With the default
    # tick of 0.1 s, the boundaries map to ~10 s and ~25 s of wall time.
    _PHASE_NORMAL_UNTIL = 100
    _PHASE_ALARM_UNTIL = 250

    def _phase(self, step: int) -> str:
        if step < self._PHASE_NORMAL_UNTIL:
            return "normal"
        if step < self._PHASE_ALARM_UNTIL:
            return "alarm"
        return "recover"

    def _sensor_value(self, baseline: float, phase: str) -> float:
        noise = self._rng.gauss(0.0, 0.5)
        if phase == "normal":
            return baseline + noise
        if phase == "alarm":
            into_phase = self._step - self._PHASE_NORMAL_UNTIL
            drift = into_phase * 0.05  # 5 unit/step → ~7.5 by end of alarm phase
            return baseline + drift + noise
        # recover
        into_recover = self._step - self._PHASE_ALARM_UNTIL
        return baseline + max(0.0, 7.5 - into_recover * 0.06) + noise
