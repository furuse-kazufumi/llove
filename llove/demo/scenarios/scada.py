"""SCADA scenario — ExplainedCUSUM in action.

Drives a bearing temperature sensor through 3 phases (normal → drift → recover)
and shows how `ExplainedCUSUM` reacts: when the cumulative sum crosses
threshold, an LLM is invoked to produce a Markdown incident report.

All user-facing copy lives in the i18n catalog. The numerical scenario is
deterministic with the default seed so SVG snapshots and tests reproduce.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind
from llove.i18n import t


class SCADAScenario(DemoScenario):
    name = "scada"
    i18n_key = "scada"
    default_pause = 0.15

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.scada.intro", title_key="scenario.scada.intro_title")
        sensor_id = "bearing_temp_07"
        baseline = 70.0

        # Phase 1: normal
        yield narrate_key("scenario.scada.phase1", title_key="scenario.scada.phase1_title")
        for _ in range(20):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="scada",
                payload={
                    "sensor_id": sensor_id,
                    "value": round(baseline + self._rng.gauss(0.0, 0.4), 2),
                    "quality": "good",
                },
            )

        # Phase 2: drift
        yield narrate_key("scenario.scada.phase2", title_key="scenario.scada.phase2_title")
        cusum = 0.0
        for i in range(40):
            value = baseline + i * 0.25 + self._rng.gauss(0.0, 0.4)
            cusum += max(0.0, value - baseline - 0.5)
            yield Event(
                kind=EventKind.SENSOR,
                source_id="scada",
                payload={"sensor_id": sensor_id, "value": round(value, 2), "quality": "good"},
            )
            if cusum >= 5.0 and i % 12 == 0:
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id="scada",
                    payload={
                        "sensor_id": sensor_id,
                        "cusum": round(cusum, 1),
                        "threshold": 5.0,
                    },
                )
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id="scada",
                    payload={
                        "event": "cusum.alarm",
                        "sensor_id": sensor_id,
                        "cusum": round(cusum, 1),
                    },
                )

        # LLM explanation
        yield narrate_key("scenario.scada.llm_triggered", title_key="scenario.scada.llm_title")
        yield Event(
            kind=EventKind.LLM_CALL,
            source_id="scada",
            payload={
                "kind": "incident_explanation",
                "tokens": 237,
                "latency_ms": 412,
                "model": "llama3.2",
                "hypothesis": t("scenario.scada.hypothesis"),
            },
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="scada",
            payload={"event": "llm.complete", "tokens": 237, "latency_ms": 412},
        )

        # Phase 3: recovery
        yield narrate_key("scenario.scada.phase3", title_key="scenario.scada.phase3_title")
        for i in range(20):
            value = baseline + max(0.0, 8.0 - i * 0.4) + self._rng.gauss(0.0, 0.4)
            yield Event(
                kind=EventKind.SENSOR,
                source_id="scada",
                payload={"sensor_id": sensor_id, "value": round(value, 2), "quality": "good"},
            )
        yield narrate_key("scenario.scada.takeaway", title_key="scenario.scada.takeaway_title")
