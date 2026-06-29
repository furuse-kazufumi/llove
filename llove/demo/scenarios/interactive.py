"""InteractiveScenario — a DemoScenario that can stop and ask the user.

This is the base that turns fixed-playback demos into branching ones. The
scenario depends only on the :class:`~llove.term.choice.ChoiceAsker` protocol,
never on the app. :class:`~llove.app.LoveApp` injects its ``ask_choice`` as the
asker at mount time.

With no asker wired (a headless run, CI, ``llove demo --list``, or a unit test),
:meth:`ask` returns the deterministic default branch so every flow still
completes — keeping playback reproducible.
"""

from __future__ import annotations

from llove.demo.scenarios.base import DemoScenario
from llove.term.choice import ChoiceAsker, ChoiceOption, ChoicePrompt


class InteractiveScenario(DemoScenario):
    """A scripted scenario with decision-points the user steers.

    Subclasses ``await self.ask(prompt, options, default_id=...)`` inside their
    ``events()`` generator and branch on the returned option id.
    """

    # Injected by LoveApp when the source is interactive. The class-level
    # default keeps non-app runs (tests, --list) headless-deterministic.
    _asker: ChoiceAsker | None = None

    async def ask(
        self,
        prompt: str,
        options: list[ChoiceOption],
        *,
        default_id: str | None = None,
    ) -> str:
        """Present a choice-point and return the chosen option id.

        Validates the prompt shape up-front (so a malformed choice fails loudly
        in tests rather than silently picking option 0 at runtime), then either
        delegates to the injected asker or — when none is wired — returns the
        deterministic default (``default_id`` or the first option).
        """
        resolved_default = ChoicePrompt(
            prompt=prompt,
            options=tuple(options),
            default_id=default_id,
        ).resolved_default
        if self._asker is None:
            return resolved_default
        return await self._asker(prompt, options, default_id=default_id)


__all__ = ["InteractiveScenario"]
