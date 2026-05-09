"""Benchmark scenario — same prompt across 3 models, latency / cost / quality."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate_key
from llove.events import Event, EventKind

_PROMPT = "Summarise the SCADA incident in one sentence."

# (model, tokens, latency_ms, cost_usd, quality_score, note)
_RUNS: list[dict[str, Any]] = [
    {
        "model": "llama3.2:8b",
        "tokens": 64,
        "latency_ms": 1820,
        "cost_usd": 0.0,
        "quality": 0.71,
        "note": "local; misses lubricant root cause",
    },
    {
        "model": "gpt-4o-mini",
        "tokens": 58,
        "latency_ms": 510,
        "cost_usd": 0.00046,
        "quality": 0.84,
        "note": "fast cloud; correct root cause",
    },
    {
        "model": "claude-haiku-4-5",
        "tokens": 62,
        "latency_ms": 620,
        "cost_usd": 0.00062,
        "quality": 0.90,
        "note": "best summary; cites timestamps",
    },
]


class BenchmarkScenario(DemoScenario):
    """Three-axis benchmark: latency, cost, LLM-as-judge quality."""

    name = "bench"
    i18n_key = "bench"
    default_pause = 0.5

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.bench.intro", title_key="scenario.bench.intro_title")
        yield narrate_key(
            "scenario.bench.prompt",
            title_key="scenario.bench.prompt_title",
            q=_PROMPT,
        )

        for run in _RUNS:
            yield Event(
                kind=EventKind.LLM_CALL,
                source_id=str(run["model"]),
                payload={
                    "model": run["model"],
                    "tokens": run["tokens"],
                    "latency_ms": run["latency_ms"],
                    "cost_usd": run["cost_usd"],
                    "quality": run["quality"],
                    "note": run["note"],
                    "kind": "completion",
                },
            )

        # Judge step — pick winner by latency, cost, quality independently.
        winner_latency = min(_RUNS, key=lambda r: float(r["latency_ms"]))
        winner_cost = min(
            _RUNS, key=lambda r: float(r["cost_usd"]) if float(r["cost_usd"]) > 0 else float("inf")
        )
        winner_quality = max(_RUNS, key=lambda r: float(r["quality"]))

        yield Event(
            kind=EventKind.AUDIT,
            source_id="judge",
            payload={
                "event": "bench.verdict",
                "winner_latency": winner_latency["model"],
                "winner_cost": winner_cost["model"],
                "winner_quality": winner_quality["model"],
            },
        )

        yield narrate_key(
            "scenario.bench.verdict",
            title_key="scenario.bench.verdict_title",
            latency_winner=str(winner_latency["model"]),
            cost_winner=str(winner_cost["model"]),
            quality_winner=str(winner_quality["model"]),
        )

        yield narrate_key("scenario.bench.takeaway", title_key="scenario.bench.takeaway_title")
