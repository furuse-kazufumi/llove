"""LLM backends scenario — Ollama / OpenAI / Anthropic side-by-side."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind
from llove.i18n import t

_PROMPT = "Explain CUSUM control charts in 2 sentences."

_RESULTS: list[dict[str, Any]] = [
    {
        "backend": "OllamaBackend",
        "model": "llama3.2",
        "tokens": 92,
        "latency_ms": 1840,
        "cost_usd": 0.0,
        "note": "local, free, no network",
    },
    {
        "backend": "openai_backend",
        "model": "gpt-4o-mini",
        "tokens": 88,
        "latency_ms": 540,
        "cost_usd": 0.0006,
        "note": "cheap cloud, good baseline",
    },
    {
        "backend": "anthropic_backend",
        "model": "claude-haiku-4-5",
        "tokens": 90,
        "latency_ms": 720,
        "cost_usd": 0.0009,
        "note": "claude family",
    },
]


class LLMBackendsScenario(DemoScenario):
    name = "backends"
    i18n_key = "backends"
    default_pause = 0.6

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.backends.intro", title_key="scenario.backends.intro_title")
        yield narrate(
            t("scenario.backends.prompt", q=_PROMPT),
            title=t("scenario.backends.prompt_title"),
        )
        for r in _RESULTS:
            yield narrate(
                t(
                    "scenario.backends.calling",
                    backend=r["backend"],
                    model=r["model"],
                    note=r["note"],
                ),
                title=str(r["backend"]),
            )
            yield Event(
                kind=EventKind.LLM_CALL,
                source_id=str(r["backend"]),
                payload={
                    "backend": r["backend"],
                    "model": r["model"],
                    "tokens": r["tokens"],
                    "latency_ms": r["latency_ms"],
                    "cost_usd": r["cost_usd"],
                    "kind": "completion",
                },
            )
        total_local = sum(int(r["latency_ms"]) for r in _RESULTS if float(r["cost_usd"]) == 0)
        total_cloud = sum(int(r["latency_ms"]) for r in _RESULTS if float(r["cost_usd"]) > 0)
        yield narrate(
            t("scenario.backends.takeaway", local_ms=total_local, cloud_ms=total_cloud),
            title=t("scenario.backends.takeaway_title"),
        )
