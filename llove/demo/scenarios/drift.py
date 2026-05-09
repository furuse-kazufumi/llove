"""Model drift scenario — output distribution shifts over time, SPC catches it."""

from __future__ import annotations

import math
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind


def _phase_value(i: int, baseline: float, drift: float, jitter: float) -> float:
    """Tiny deterministic LCG-style jitter so the demo stays seedless but varied."""
    j = ((i * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF
    return round(baseline + drift + (j - 0.5) * 2 * jitter, 3)


class ModelDriftScenario(DemoScenario):
    """Production model's average response length creeps up week over week."""

    name = "drift"
    i18n_key = "drift"
    default_pause = 0.35

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.drift.intro", title_key="scenario.drift.intro_title")

        # Phase A — week 1 baseline (avg ~150 tokens)
        yield narrate_key("scenario.drift.phase_a", title_key="scenario.drift.phase_a_title")
        for i in range(8):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="prod_chat_v1",
                payload={
                    "sensor_id": "avg_response_tokens",
                    "value": _phase_value(i, baseline=150.0, drift=0.0, jitter=8.0),
                    "phase": "week1",
                },
            )

        # Phase B — week 4: slow drift (~+25 tokens)
        yield narrate_key("scenario.drift.phase_b", title_key="scenario.drift.phase_b_title")
        for i in range(8):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="prod_chat_v1",
                payload={
                    "sensor_id": "avg_response_tokens",
                    "value": _phase_value(i + 100, baseline=150.0, drift=25.0, jitter=10.0),
                    "phase": "week4",
                },
            )

        # Phase C — week 6: alarm
        yield narrate_key("scenario.drift.phase_c", title_key="scenario.drift.phase_c_title")
        for i in range(6):
            value = _phase_value(i + 200, baseline=150.0, drift=55.0, jitter=12.0)
            yield Event(
                kind=EventKind.SENSOR,
                source_id="prod_chat_v1",
                payload={
                    "sensor_id": "avg_response_tokens",
                    "value": value,
                    "phase": "week6",
                },
            )

        cusum = round(math.sqrt(8 * 25.0 + 6 * 55.0), 2)
        yield Event(
            kind=EventKind.SPC_ALARM,
            source_id="drift_monitor",
            payload={
                "sensor_id": "avg_response_tokens",
                "cusum": cusum,
                "threshold": 12.0,
                "rule": "cusum_one_sided_upper",
                "estimated_shift_tokens": 55,
            },
        )

        yield narrate_key(
            "scenario.drift.llm",
            title_key="scenario.drift.llm_title",
            cusum=cusum,
        )

        yield Event(
            kind=EventKind.AUDIT,
            source_id="drift_monitor",
            payload={
                "event": "drift.confirmed",
                "metric": "avg_response_tokens",
                "shift_pct": 36.6,
                "remediation": "freeze prompt template; review retrieval quality",
            },
        )

        yield narrate_key("scenario.drift.takeaway", title_key="scenario.drift.takeaway_title")
