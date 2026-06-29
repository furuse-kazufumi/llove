"""Interactive choice-points — data model + pure rendering (Textual-free).

A *choice-point* is where llove stops a scripted flow and asks the user to pick
one of several options, then branches on the answer. This turns a fixed-playback
demo into an interactive harness for **verifying how the AI behaves under each
branch** — the reason llove exists ("AI としての機能検証用のもの").

This module holds only the pure core (dataclasses, validation, rendering, and
the :class:`ChoiceAsker` protocol). The Textual modal lives in
``choice_screen.py`` so pure logic can be imported and tested without pulling in
the UI stack — mirroring the ``completion.py`` (pure) / ``palette.py`` (UI) split.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ChoiceOption:
    """One selectable option at a choice-point.

    ``id`` is the stable machine key a scenario branches on, ``label`` is the
    short human-facing text, and ``description`` is an optional one-liner shown
    next to the label.
    """

    id: str
    label: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("ChoiceOption.id must be non-empty")
        if not self.label:
            raise ValueError("ChoiceOption.label must be non-empty")


@dataclass(frozen=True)
class ChoicePrompt:
    """A question plus the options the user may pick from.

    ``default_id`` is the option chosen when no human answers (headless / CI /
    a dismissed modal) — it keeps every flow deterministic. ``None`` resolves to
    the first option.
    """

    prompt: str
    options: tuple[ChoiceOption, ...]
    default_id: str | None = None

    def __post_init__(self) -> None:
        if not self.options:
            raise ValueError("ChoicePrompt requires at least one option")
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate option ids: {ids}")
        if self.default_id is not None and self.default_id not in ids:
            raise ValueError(f"default_id {self.default_id!r} is not one of {ids!r}")

    @property
    def resolved_default(self) -> str:
        """The option id used when nobody picks (``default_id`` or first option)."""
        return self.default_id if self.default_id is not None else self.options[0].id

    def option(self, option_id: str) -> ChoiceOption | None:
        """Look up an option by id (``None`` when absent)."""
        for o in self.options:
            if o.id == option_id:
                return o
        return None


def make_prompt(
    prompt: str,
    options: Sequence[ChoiceOption | tuple[str, str]],
    *,
    default_id: str | None = None,
) -> ChoicePrompt:
    """Build a :class:`ChoicePrompt` from ChoiceOptions or ``(id, label)`` tuples."""
    built: list[ChoiceOption] = []
    for o in options:
        if isinstance(o, ChoiceOption):
            built.append(o)
        else:
            oid, label = o
            built.append(ChoiceOption(id=oid, label=label))
    return ChoicePrompt(prompt=prompt, options=tuple(built), default_id=default_id)


def render_choice(prompt: ChoicePrompt, *, selected_id: str | None = None) -> list[str]:
    """Render a choice-point to plain-text lines (Textual-free, for tests / logs).

    The line whose option id matches ``selected_id`` — or the resolved default
    when ``selected_id`` is ``None`` — is marked with ``▸``.
    """
    marker_id = selected_id if selected_id is not None else prompt.resolved_default
    lines = [prompt.prompt]
    for i, o in enumerate(prompt.options, start=1):
        marker = "▸" if o.id == marker_id else " "
        line = f"{marker} {i}. {o.label}"
        if o.description:
            line += f"  — {o.description}"
        lines.append(line)
    return lines


@runtime_checkable
class ChoiceAsker(Protocol):
    """Something that can present a choice-point and return the chosen id.

    :meth:`llove.app.LoveApp.ask_choice` implements this.
    :class:`llove.demo.scenarios.interactive.InteractiveScenario` depends on the
    protocol, never on the app — so the app can inject any asker (the real modal,
    or a scripted fake in tests).
    """

    async def __call__(
        self,
        prompt: str,
        options: list[ChoiceOption],
        *,
        default_id: str | None = None,
    ) -> str: ...


__all__ = [
    "ChoiceAsker",
    "ChoiceOption",
    "ChoicePrompt",
    "make_prompt",
    "render_choice",
]
