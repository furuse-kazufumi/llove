"""Cost budget scenario — token spend, daily budget, alarm + LLM root-cause."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind

# (backend, model, tokens, latency_ms, cost_usd, note)
_CALLS: list[dict[str, Any]] = [
    {"backend": "ollama", "model": "llama3.2", "tokens": 120, "latency_ms": 2100, "cost_usd": 0.0},
    {
        "backend": "openai",
        "model": "gpt-4o-mini",
        "tokens": 92,
        "latency_ms": 540,
        "cost_usd": 0.00074,
    },
    {
        "backend": "openai",
        "model": "gpt-4o-mini",
        "tokens": 110,
        "latency_ms": 600,
        "cost_usd": 0.00088,
    },
    {
        "backend": "anthropic",
        "model": "claude-haiku-4-5",
        "tokens": 220,
        "latency_ms": 720,
        "cost_usd": 0.00220,
    },
    {
        "backend": "openai",
        "model": "gpt-4o",
        "tokens": 1480,
        "latency_ms": 1900,
        "cost_usd": 0.04440,
    },
    {
        "backend": "openai",
        "model": "gpt-4o",
        "tokens": 1820,
        "latency_ms": 2050,
        "cost_usd": 0.05460,
    },
    {
        "backend": "openai",
        "model": "gpt-4o",
        "tokens": 2200,
        "latency_ms": 2200,
        "cost_usd": 0.06600,
    },
]

_DAILY_BUDGET_USD = 0.10


class CostBudgetScenario(DemoScenario):
    """Token cost accumulates across LLM calls; SPC alarms when budget breached."""

    name = "cost"
    i18n_key = "cost"
    default_pause = 0.45

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.cost.intro",
            title_key="scenario.cost.intro_title",
            budget=f"${_DAILY_BUDGET_USD:.2f}",
        )

        running_total = 0.0
        breached = False
        for i, call in enumerate(_CALLS, start=1):
            running_total += float(call["cost_usd"])
            yield Event(
                kind=EventKind.LLM_CALL,
                source_id=str(call["backend"]),
                payload={
                    "backend": call["backend"],
                    "model": call["model"],
                    "tokens": call["tokens"],
                    "latency_ms": call["latency_ms"],
                    "cost_usd": call["cost_usd"],
                    "running_total_usd": round(running_total, 5),
                },
            )

            # Mirror running cost as a SENSOR so the SensorStream pane shows
            # a clear right-rising sparkline of daily spend instead of staying
            # blank. The SPC alarm below targets the same `daily_cost_usd`.
            yield Event(
                kind=EventKind.SENSOR,
                source_id="cost_meter",
                payload={
                    "sensor_id": "daily_cost_usd",
                    "value": round(running_total, 5),
                    "call_seq": i,
                    "model": call["model"],
                },
            )

            if not breached and running_total > _DAILY_BUDGET_USD:
                breached = True
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id="cost_meter",
                    payload={
                        "sensor_id": "daily_cost_usd",
                        "value": round(running_total, 4),
                        "threshold": _DAILY_BUDGET_USD,
                        "cusum": round(running_total / _DAILY_BUDGET_USD, 2),
                        "rule": "budget_exceeded",
                    },
                )
                yield narrate_key(
                    "scenario.cost.breached",
                    title_key="scenario.cost.breached_title",
                    total=f"${running_total:.4f}",
                    n=i,
                )

        yield narrate_key(
            "scenario.cost.llm_explain",
            title_key="scenario.cost.llm_explain_title",
        )

        yield Event(
            kind=EventKind.AUDIT,
            source_id="cost_meter",
            payload={
                "event": "budget.alert",
                "total_usd": round(running_total, 4),
                "budget_usd": _DAILY_BUDGET_USD,
                "biggest_offender": "gpt-4o",
                "recommendation": "route long prompts to claude-haiku or local llama3.2",
            },
        )

        yield narrate_key(
            "scenario.cost.takeaway",
            title_key="scenario.cost.takeaway_title",
            total=f"${running_total:.4f}",
        )
