"""Multimodal SPC scenario — UnifiedSPC + VLMFeatureExtractor."""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind

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
    i18n_key = "multimodal"
    default_pause = 0.25

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.multimodal.intro", title_key="scenario.multimodal.intro_title")

        yield narrate_key(
            "scenario.multimodal.phase_a", title_key="scenario.multimodal.phase_a_title"
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

        yield narrate_key(
            "scenario.multimodal.phase_b", title_key="scenario.multimodal.phase_b_title"
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

        yield narrate_key(
            "scenario.multimodal.phase_c", title_key="scenario.multimodal.phase_c_title"
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
        yield narrate_key(
            "scenario.multimodal.takeaway", title_key="scenario.multimodal.takeaway_title"
        )
