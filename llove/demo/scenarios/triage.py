"""triage — an interactive support / RAG triage cartridge (branching).

A user question arrives with three knowledge-base matches. *You* choose how to
answer — return the top KB hit, ask the LLM to synthesise one, or escalate to a
human — and the run branches, exercising a different capability per path
(retrieval / generation / human hand-off). Like every demo it is synthetic and
offline; the new part is that you steer it. Launch from the palette with
``:demo triage`` (or ``llove demo --scenario triage``).

With no asker wired (CI / --list), the deterministic default path is
``llm -> send``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import narrate, narrate_key
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.events import Event, EventKind
from llove.i18n import t
from llove.term.choice import ChoiceOption


class TriageScenario(InteractiveScenario):
    name = "triage"
    i18n_key = "triage"
    default_pause = 0.12

    def _chose(self, options: list[ChoiceOption], chosen_id: str) -> Event:
        label = next((o.label for o in options if o.id == chosen_id), chosen_id)
        return narrate(
            t("scenario.triage.chose", label=label),
            title=t("scenario.triage.chose_title"),
        )

    def _rag(self, score: float, text_key: str) -> Event:
        return Event(
            kind=EventKind.RAG_HIT,
            source_id="triage",
            payload={"score": score, "text": t(text_key)},
        )

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.triage.intro", title_key="scenario.triage.intro_title")
        yield narrate_key("scenario.triage.question", title_key="scenario.triage.question_title")
        yield self._rag(0.91, "scenario.triage.hit1")
        yield self._rag(0.74, "scenario.triage.hit2")
        yield self._rag(0.55, "scenario.triage.hit3")
        yield Event(
            kind=EventKind.AUDIT,
            source_id="triage",
            payload={"event": "rag.retrieved", "hits": 3, "best": 0.91},
        )

        opts1 = [
            ChoiceOption(
                "kb", t("scenario.triage.q1_kb_label"), t("scenario.triage.q1_kb_desc")
            ),
            ChoiceOption(
                "llm", t("scenario.triage.q1_llm_label"), t("scenario.triage.q1_llm_desc")
            ),
            ChoiceOption(
                "escalate",
                t("scenario.triage.q1_escalate_label"),
                t("scenario.triage.q1_escalate_desc"),
            ),
        ]
        choice = await self.ask(t("scenario.triage.q1_prompt"), opts1, default_id="llm")
        yield self._chose(opts1, choice)

        if choice == "kb":
            async for ev in self._branch_kb():
                yield ev
        elif choice == "escalate":
            async for ev in self._branch_escalate():
                yield ev
        else:  # llm (default)
            async for ev in self._branch_llm():
                yield ev

    async def _branch_kb(self) -> AsyncIterator[Event]:
        yield Event(
            kind=EventKind.AUDIT,
            source_id="triage",
            payload={"event": "answer.from_kb", "score": 0.91, "display": t("scenario.triage.kb")},
        )
        yield narrate_key("scenario.triage.kb", title_key="scenario.triage.kb_title")
        yield narrate_key("scenario.triage.takeaway_kb", title_key="scenario.triage.takeaway_title")

    async def _branch_llm(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.triage.llm", title_key="scenario.triage.llm_title")
        yield Event(
            kind=EventKind.LLM_CALL,
            source_id="triage",
            payload={
                "kind": "rag_synthesis",
                "tokens": 184,
                "latency_ms": 322,
                "model": "llama3.2",
                "answer": t("scenario.triage.answer"),
            },
        )
        yield Event(
            kind=EventKind.AUDIT,
            source_id="triage",
            payload={"event": "llm.complete", "tokens": 184, "latency_ms": 322},
        )
        opts2 = [
            ChoiceOption(
                "send", t("scenario.triage.q2_send_label"), t("scenario.triage.q2_send_desc")
            ),
            ChoiceOption(
                "cite", t("scenario.triage.q2_cite_label"), t("scenario.triage.q2_cite_desc")
            ),
            ChoiceOption(
                "escalate",
                t("scenario.triage.q2_escalate_label"),
                t("scenario.triage.q2_escalate_desc"),
            ),
        ]
        choice = await self.ask(t("scenario.triage.q2_prompt"), opts2, default_id="send")
        yield self._chose(opts2, choice)
        if choice == "cite":
            yield Event(
                kind=EventKind.AUDIT,
                source_id="triage",
                payload={"event": "answer.with_citation", "display": t("scenario.triage.cite")},
            )
            yield narrate_key("scenario.triage.cite", title_key="scenario.triage.cite_title")
        elif choice == "escalate":
            yield Event(
                kind=EventKind.AUDIT,
                source_id="triage",
                payload={"event": "answer.escalate", "display": t("scenario.triage.q2esc")},
            )
            yield narrate_key("scenario.triage.q2esc", title_key="scenario.triage.q2esc_title")
        else:  # send (default)
            yield Event(
                kind=EventKind.AUDIT,
                source_id="triage",
                payload={"event": "answer.sent", "display": t("scenario.triage.send")},
            )
            yield narrate_key("scenario.triage.send", title_key="scenario.triage.send_title")
        yield narrate_key("scenario.triage.takeaway_llm", title_key="scenario.triage.takeaway_title")

    async def _branch_escalate(self) -> AsyncIterator[Event]:
        yield Event(
            kind=EventKind.AUDIT,
            source_id="triage",
            payload={"event": "ticket.escalate", "display": t("scenario.triage.esc")},
        )
        yield narrate_key("scenario.triage.esc", title_key="scenario.triage.esc_title")
        yield narrate_key(
            "scenario.triage.takeaway_escalate", title_key="scenario.triage.takeaway_title"
        )


__all__ = ["TriageScenario"]
