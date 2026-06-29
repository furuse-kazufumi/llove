"""``ChoiceScreen`` — the Textual modal for an interactive choice-point.

Pure data + rendering live in ``choice.py``; this is the thin Textual binding
(mirrors ``palette.py`` over ``completion.py``). The screen shows a prompt and a
navigable list of options:

    ↑ / ↓      move the highlight
    Enter      pick the highlighted option
    1 … 9      pick the Nth option directly
    Escape     dismiss with ``None`` → the caller falls back to the default branch
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from llove.term.choice import ChoiceOption, ChoicePrompt


class ChoiceScreen(ModalScreen[str | None]):
    """Modal that asks the user to pick one option; dismisses with its id.

    Dismissing with ``None`` (Escape) signals "no explicit choice"; the caller
    (``LoveApp.ask_choice``) maps that to the prompt's resolved default so the
    flow always continues.
    """

    DEFAULT_CSS = """
    ChoiceScreen {
        align: center middle;
        background: rgba(0,0,0,0.5);
    }
    ChoiceScreen > #choice-box {
        width: 72;
        max-width: 90%;
        max-height: 80%;
        background: $boost;
        border: heavy $primary;
        padding: 1 2;
    }
    ChoiceScreen #choice-prompt {
        margin-bottom: 1;
    }
    ChoiceScreen #choice-options {
        height: auto;
        max-height: 16;
    }
    """

    BINDINGS = [  # noqa: RUF012 — Textual reads BINDINGS as a class-level list.
        Binding("escape", "cancel", "Default", show=True),
    ]

    def __init__(self, prompt: ChoicePrompt) -> None:
        super().__init__()
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="choice-box"):
            yield Static(self._prompt.prompt, id="choice-prompt")
            options = [
                Option(self._option_text(i, o), id=o.id)
                for i, o in enumerate(self._prompt.options, start=1)
            ]
            yield OptionList(*options, id="choice-options")

    @staticmethod
    def _option_text(index: int, option: ChoiceOption) -> str:
        text = f"{index}. {option.label}"
        if option.description:
            text += f"  — {option.description}"
        return text

    def on_mount(self) -> None:
        ol = self.query_one("#choice-options", OptionList)
        ol.focus()
        # Highlight the resolved default so a bare Enter picks it.
        default_index = self._index_of(self._prompt.resolved_default)
        if default_index is not None:
            ol.highlighted = default_index

    def _index_of(self, option_id: str) -> int | None:
        for i, o in enumerate(self._prompt.options):
            if o.id == option_id:
                return i
        return None

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # ``option_id`` is the ChoiceOption.id we attached in compose().
        self.dismiss(event.option_id)

    def on_key(self, event: events.Key) -> None:
        # Digit shortcut: 1..9 selects the Nth option directly.
        if event.key.isdigit() and event.key != "0":
            idx = int(event.key) - 1
            if 0 <= idx < len(self._prompt.options):
                event.stop()
                self.dismiss(self._prompt.options[idx].id)

    def action_cancel(self) -> None:
        # Escape → None; the caller maps this to the default branch.
        self.dismiss(None)


__all__ = ["ChoiceScreen"]
