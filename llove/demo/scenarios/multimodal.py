"""Multimodal SPC scenario — UnifiedSPC + VLMFeatureExtractor.

Shows how llmesh.industrial.UnifiedSPC pairs a numerical sensor with image
captions (via VLMFeatureExtractor) and applies a combined SPC rule.
"""
from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind

_INTRO = (
    "**UnifiedSPC** combines two streams (numerical sensor + image caption) "
    "with a configurable AND / OR / Weighted rule. We use AND here: alarm only when "
    "**both** streams cross their limits."
)

_CAPTIONS_NORMAL = [
    "smooth surface, no defect",
    "uniform colour, glossy",
    "well-aligned components",
]
_CAPTIONS_ANOMALOUS = [
    "rough surface, possible scratch",
    "discolouration along edge",
    "misalignment visible",
]


class MultimodalSPCScenario(DemoScenario):
    name = "multimodal"
    title = "Multimodal SPC — sensor + VLM caption fused"
    description = (
        "Two streams (vibration + camera caption) flow side-by-side. UnifiedSPC's "
        "AND rule fires only when both indicate trouble."
    )
    default_pause = 0.25

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    async def events(self) -> AsyncIterator[Event]:
        yield narrate(_INTRO, title="Scenario: Multimodal SPC")

        # Phase A: both streams nominal — no alarm
        yield narrate(
            "Phase A — sensor nominal, image nominal → **no alarm** (AND not satisfied)",
            title="Phase A",
        )
        for _ in range(8):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="vibration",
                payload={"sensor_id": "vib_01", "value": round(0.5 + self._rng.gauss(0, 0.05), 3)},
            )
            yield Event(
                kind=EventKind.AUDIT,
                source_id="vlm",
                payload={
                    "event": "vlm.caption",
                    "caption": self._rng.choice(_CAPTIONS_NORMAL),
                    "verdict": "nominal",
                },
            )

        # Phase B: image anomalous, sensor nominal — single side alarm, AND blocks
        yield narrate(
            "Phase B — image suspicious, sensor still fine → AND rule **suppresses** alarm",
            title="Phase B",
        )
        for _ in range(4):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="vibration",
                payload={"sensor_id": "vib_01", "value": round(0.5 + self._rng.gauss(0, 0.05), 3)},
            )
            yield Event(
                kind=EventKind.AUDIT,
                source_id="vlm",
                payload={
                    "event": "vlm.caption",
                    "caption": self._rng.choice(_CAPTIONS_ANOMALOUS),
                    "verdict": "suspicious",
                },
            )

        # Phase C: both anomalous — AND fires
        yield narrate(
            "Phase C — vibration also rises **and** image still suspicious → "
            "**alarm**: bothstreams agree",
            title="Phase C",
        )
        for i in range(6):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="vibration",
                payload={
                    "sensor_id": "vib_01",
                    "value": round(0.7 + i * 0.05 + self._rng.gauss(0, 0.05), 3),
                },
            )
            yield Event(
                kind=EventKind.AUDIT,
                source_id="vlm",
                payload={
                    "event": "vlm.caption",
                    "caption": self._rng.choice(_CAPTIONS_ANOMALOUS),
                    "verdict": "suspicious",
                },
            )
        yield Event(
            kind=EventKind.SPC_ALARM,
            source_id="unified_spc",
            payload={
                "rule": "AND(vibration>0.9, vlm=suspicious)",
                "cusum": 8.4,
                "threshold": 5.0,
                "sensor_id": "unified",
            },
        )
        yield narrate(
            "UnifiedSPC reduces false alarms by **requiring agreement across modalities**. "
            "Choose AND for high-precision (process control), OR for high-recall (safety).",
            title="Take-away",
        )
