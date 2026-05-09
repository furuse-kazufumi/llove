"""SCADA scenario — ExplainedCUSUM in action.

Drives a bearing temperature sensor through 3 phases (normal → drift → recover)
and shows how `ExplainedCUSUM` would react: when the cumulative sum crosses
threshold, an LLM is invoked to produce a Markdown incident report.
"""
from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind

_INTRO = (
    "**SCADA + ExplainedCUSUM**: a bearing temperature sensor will drift past its "
    "control limit. CUSUM detects the cumulative shift; the LLM explainer then attaches "
    "a likely cause."
)

_HYPOTHESIS = (
    "The cumulative drift began ~12 minutes ago, coinciding with a viscosity drop in "
    "lubricant_flow_03. Bearing wear or lubricant degradation is plausible. Recommend "
    "checking lubricant pressure and vibration spectrum."
)


class SCADAScenario(DemoScenario):
    name = "scada"
    title = "SCADA — ExplainedCUSUM with LLM hypothesis"
    description = (
        "A bearing temperature sensor drifts past its control limit. ExplainedCUSUM "
        "detects the alarm and the LLM emits a hypothesis."
    )
    default_pause = 0.15

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    async def events(self) -> AsyncIterator[Event]:
        yield narrate(_INTRO, title="Scenario: SCADA")
        sensor_id = "bearing_temp_07"
        baseline = 70.0

        # Phase 1: normal
        yield narrate("Phase 1 — **normal**: reading hovers around 70 °C", title="Phase 1")
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
        yield narrate(
            "Phase 2 — **drift**: viscosity drops in `lubricant_flow_03`, bearing temp rises",
            title="Phase 2",
        )
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

        # LLM explanation
        yield narrate("**LLM explainer** triggered — building incident report", title="LLM")
        yield Event(
            kind=EventKind.LLM_CALL,
            source_id="scada",
            payload={
                "kind": "incident_explanation",
                "tokens": 237,
                "latency_ms": 412,
                "model": "llama3.2",
                "hypothesis": _HYPOTHESIS,
            },
        )

        # Phase 3: recovery
        yield narrate("Phase 3 — **recovery** after maintenance action", title="Phase 3")
        for i in range(20):
            value = baseline + max(0.0, 8.0 - i * 0.4) + self._rng.gauss(0.0, 0.4)
            yield Event(
                kind=EventKind.SENSOR,
                source_id="scada",
                payload={"sensor_id": sensor_id, "value": round(value, 2), "quality": "good"},
            )
        yield narrate(
            "ExplainedCUSUM = **CUSUMChart + LLMExplainer** glued together. "
            "Alarms fire on numerical drift; the LLM attaches a natural-language cause.",
            title="Take-away",
        )
