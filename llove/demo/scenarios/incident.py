"""incident — the flagship *interactive* scenario (choice-points / branching).

A bearing-temperature sensor drifts past its control limit and CUSUM fires an
alarm. Then llove **stops and asks the operator how to respond** — and the run
branches on the answer:

    explain     → invoke the LLM for a root-cause hypothesis  (verifies LLM generation)
        ├ apply_fix / rollback / escalate  (a second decision-point)
    observe     → keep watching; the drift escalates to a 2nd alarm  (verifies SPC)
    quarantine  → isolate the line and confirm via the audit chain  (verifies audit)

Each branch exercises a *different* AI / LLMesh capability, so the same demo is
also a tiny harness for verifying how the system behaves under each decision —
which is what llove is for ("AI としての機能検証用のもの"). Choices are recorded
as AUDIT events, so a ``--log`` JSONL replays the exact path taken.

Runs fully offline. With no asker wired (CI / ``--list``), the deterministic
default path is ``explain → apply_fix``.
"""

from __future__ import annotations

import random
from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption

_SENSOR_ID = "bearing_temp_07"
_BASELINE = 70.0
_THRESHOLD = 5.0


class IncidentScenario(InteractiveScenario):
    name = "incident"
    i18n_key = "incident"
    default_pause = 0.12

    def __init__(self, *, seed: int = 42) -> None:
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------ helpers
    def _sensor(self, value: float) -> Event:
        return Event(
            kind=EventKind.SENSOR,
            source_id="incident",
            payload={"sensor_id": _SENSOR_ID, "value": round(value, 2), "quality": "good"},
        )

    def _alarm(self, cusum: float, *, event: str = "cusum.alarm") -> tuple[Event, Event]:
        spc = Event(
            kind=EventKind.SPC_ALARM,
            source_id="incident",
            payload={"sensor_id": _SENSOR_ID, "cusum": round(cusum, 1), "threshold": _THRESHOLD},
        )
        audit = Event(
            kind=EventKind.AUDIT,
            source_id="incident",
            payload={"event": event, "sensor_id": _SENSOR_ID, "cusum": round(cusum, 1)},
        )
        return spc, audit

    def _chose(self, options: list[ChoiceOption], chosen_id: str) -> Event:
        label = next((o.label for o in options if o.id == chosen_id), chosen_id)
        return narrate(
            t("scenario.incident.chose", label=label),
            title=t("scenario.incident.chose_title"),
        )

    # ------------------------------------------------------------------ script
    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.incident.intro", title_key="scenario.incident.intro_title")

        # Phase 1 — normal.
        yield narrate_key("scenario.incident.normal", title_key="scenario.incident.normal_title")
        for _ in range(8):
            yield self._sensor(_BASELINE + self._rng.gauss(0.0, 0.4))

        # Phase 2 — drift until CUSUM crosses the control limit.
        cusum = 0.0
        for i in range(24):
            value = _BASELINE + i * 0.5 + self._rng.gauss(0.0, 0.4)
            cusum += max(0.0, value - _BASELINE - 0.5)
            yield self._sensor(value)
            if cusum >= _THRESHOLD:
                break
        spc, audit = self._alarm(cusum)
        yield spc
        yield audit
        yield narrate_key("scenario.incident.alarm", title_key="scenario.incident.alarm_title")

        # Decision 1 — how does the operator respond?
        opts1 = [
            ChoiceOption(
                "explain",
                t("scenario.incident.q1_explain_label"),
                t("scenario.incident.q1_explain_desc"),
            ),
            ChoiceOption(
                "observe",
                t("scenario.incident.q1_observe_label"),
                t("scenario.incident.q1_observe_desc"),
            ),
            ChoiceOption(
                "quarantine",
                t("scenario.incident.q1_quarantine_label"),
                t("scenario.incident.q1_quarantine_desc"),
            ),
        ]
        choice = await self.ask(t("scenario.incident.q1_prompt"), opts1, default_id="explain")
        yield self._chose(opts1, choice)

        if choice == "observe":
            async for ev in self._branch_observe(cusum):
                yield ev
        elif choice == "quarantine":
            async for ev in self._branch_quarantine():
                yield ev
        else:  # "explain" (also the default branch)
            async for ev in self._branch_explain():
                yield ev

    # ------------------------------------------------------------------ branches
    async def _branch_explain(self) -> AsyncIterator[Event]:
        """Verify LLM generation: ask the model for a root-cause hypothesis."""
        yield narrate_key("scenario.incident.explain", title_key="scenario.incident.explain_title")
        yield Event(
            kind=EventKind.LLM_CALL,
            source_id="incident",
            payload={
                "kind": "incident_explanation",
                "tokens": 237,
                "latency_ms": 412,
                "model": "llama3.2",
                "hypothesis": t("scenario.incident.hypothesis"),
            },
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="incident",
            payload={"event": "llm.complete", "tokens": 237, "latency_ms": 412},
        )

        # Decision 2 — now that we have a hypothesis, what next?
        opts2 = [
            ChoiceOption(
                "apply_fix",
                t("scenario.incident.q2_fix_label"),
                t("scenario.incident.q2_fix_desc"),
            ),
            ChoiceOption(
                "rollback",
                t("scenario.incident.q2_rollback_label"),
                t("scenario.incident.q2_rollback_desc"),
            ),
            ChoiceOption(
                "escalate",
                t("scenario.incident.q2_escalate_label"),
                t("scenario.incident.q2_escalate_desc"),
            ),
        ]
        choice = await self.ask(t("scenario.incident.q2_prompt"), opts2, default_id="apply_fix")
        yield self._chose(opts2, choice)

        if choice == "rollback":
            yield Event(
                kind=EventKind.AUDIT,
                source_id="incident",
                payload={"event": "incident.rollback", "display": t("scenario.incident.rollback")},
            )
            yield narrate_key(
                "scenario.incident.rollback", title_key="scenario.incident.rollback_title"
            )
        elif choice == "escalate":
            yield Event(
                kind=EventKind.AUDIT,
                source_id="incident",
                payload={
                    "event": "incident.escalate_human",
                    "display": t("scenario.incident.escalate"),
                },
            )
            yield narrate_key(
                "scenario.incident.escalate", title_key="scenario.incident.escalate_title"
            )
        else:  # apply_fix (default)
            yield Event(
                kind=EventKind.AUDIT,
                source_id="incident",
                payload={"event": "incident.fix_applied", "display": t("scenario.incident.fix")},
            )
            yield narrate_key("scenario.incident.fix", title_key="scenario.incident.fix_title")
        yield narrate_key(
            "scenario.incident.takeaway_explain", title_key="scenario.incident.takeaway_title"
        )

    async def _branch_observe(self, cusum: float) -> AsyncIterator[Event]:
        """Verify SPC continuation: keep watching; the drift gets worse."""
        yield narrate_key("scenario.incident.observe", title_key="scenario.incident.observe_title")
        for i in range(12):
            value = _BASELINE + 10.0 + i * 0.6 + self._rng.gauss(0.0, 0.4)
            cusum += max(0.0, value - _BASELINE - 0.5)
            yield self._sensor(value)
        spc, audit = self._alarm(cusum, event="cusum.alarm.escalated")
        yield spc
        yield audit
        yield narrate_key(
            "scenario.incident.observe_escalate",
            title_key="scenario.incident.observe_escalate_title",
        )
        yield narrate_key(
            "scenario.incident.takeaway_observe", title_key="scenario.incident.takeaway_title"
        )

    async def _branch_quarantine(self) -> AsyncIterator[Event]:
        """Verify the audit chain: isolate the line and confirm tamper-evidently."""
        yield Event(
            kind=EventKind.AUDIT,
            source_id="incident",
            payload={
                "event": "line.quarantine",
                "sensor_id": _SENSOR_ID,
                "display": t("scenario.incident.quarantine"),
            },
        )
        yield narrate_key(
            "scenario.incident.quarantine", title_key="scenario.incident.quarantine_title"
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="incident",
            payload={
                "event": "line.quarantine_confirmed",
                "sensor_id": _SENSOR_ID,
                "display": t("scenario.incident.quarantine_done"),
            },
        )
        yield narrate_key(
            "scenario.incident.quarantine_done",
            title_key="scenario.incident.quarantine_done_title",
        )
        yield narrate_key(
            "scenario.incident.takeaway_quarantine", title_key="scenario.incident.takeaway_title"
        )


__all__ = ["IncidentScenario"]
