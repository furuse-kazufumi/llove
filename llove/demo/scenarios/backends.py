"""LLM backends scenario — Ollama / OpenAI / Anthropic side-by-side.

We don't actually call any backend (offline, deterministic). The point is to
show the unified ABC: same prompt, same code path, different cost/latency.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind

_INTRO = (
    "**llmesh.llm** lets you swap backends with one constructor change. "
    "Same prompt → 3 different backends, no other code changes."
)

_PROMPT = "Explain CUSUM control charts in 2 sentences."

_RESULTS = [
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
    title = "LLM backends — Ollama / OpenAI / Anthropic"
    description = (
        "Same prompt across local + 2 cloud backends. Compare tokens / latency / cost "
        "with the unified ABC."
    )
    default_pause = 0.6

    async def events(self) -> AsyncIterator[Event]:
        yield narrate(_INTRO, title="Scenario: LLM backends")
        yield narrate(f"prompt: `{_PROMPT}`", title="Prompt")
        for r in _RESULTS:
            yield narrate(
                f"calling **{r['backend']}** — model `{r['model']}`  ({r['note']})",
                title=r["backend"],
            )
            yield Event(
                kind=EventKind.LLM_CALL,
                source_id=r["backend"],
                payload={
                    "backend": r["backend"],
                    "model": r["model"],
                    "tokens": r["tokens"],
                    "latency_ms": r["latency_ms"],
                    "cost_usd": r["cost_usd"],
                    "kind": "completion",
                },
            )
        total_local = sum(r["latency_ms"] for r in _RESULTS if r["cost_usd"] == 0)
        total_cloud = sum(r["latency_ms"] for r in _RESULTS if r["cost_usd"] > 0)
        yield narrate(
            f"local total = {total_local} ms (free) · cloud total = {total_cloud} ms "
            "(low cost). **Use local for dev, cloud for hard prompts.**",
            title="Take-away",
        )
