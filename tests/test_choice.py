"""Tests for the interactive choice-point primitive (``llove.term.choice``).

Pure data/validation/rendering first, then the Textual ``ChoiceScreen`` modal
wired through ``run_test()`` (mirrors ``test_command_palette_ui.py``).
"""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from llove.term.choice import (
    ChoiceAsker,
    ChoiceOption,
    ChoicePrompt,
    make_prompt,
    render_choice,
)

# --------------------------------------------------------------------------- pure


def test_option_rejects_empty_id_or_label() -> None:
    with pytest.raises(ValueError):
        ChoiceOption(id="", label="x")
    with pytest.raises(ValueError):
        ChoiceOption(id="x", label="")


def test_prompt_requires_options() -> None:
    with pytest.raises(ValueError):
        ChoicePrompt(prompt="q", options=())


def test_prompt_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError):
        ChoicePrompt(prompt="q", options=(ChoiceOption("a", "A"), ChoiceOption("a", "B")))


def test_prompt_rejects_unknown_default() -> None:
    with pytest.raises(ValueError):
        ChoicePrompt(prompt="q", options=(ChoiceOption("a", "A"),), default_id="z")


def test_resolved_default_falls_back_to_first() -> None:
    p = ChoicePrompt(prompt="q", options=(ChoiceOption("a", "A"), ChoiceOption("b", "B")))
    assert p.resolved_default == "a"
    p2 = ChoicePrompt(
        prompt="q",
        options=(ChoiceOption("a", "A"), ChoiceOption("b", "B")),
        default_id="b",
    )
    assert p2.resolved_default == "b"


def test_option_lookup() -> None:
    p = make_prompt("q", [("a", "A"), ("b", "B")])
    found = p.option("b")
    assert found is not None and found.label == "B"
    assert p.option("z") is None


def test_make_prompt_accepts_tuples_and_options() -> None:
    p = make_prompt("q", [ChoiceOption("a", "A"), ("b", "B")], default_id="b")
    assert [o.id for o in p.options] == ["a", "b"]
    assert p.default_id == "b"


def test_render_choice_marks_default_and_numbers() -> None:
    p = make_prompt("どうする?", [("explain", "説明"), ("observe", "観測")], default_id="observe")
    lines = render_choice(p)
    assert lines[0] == "どうする?"
    # Non-selected rows use a space marker (aligns numbers under the ▸ row).
    assert lines[1].lstrip().startswith("1. 説明")
    assert not lines[1].startswith("▸")
    assert lines[2].startswith("▸ 2. 観測")


def test_render_choice_includes_description() -> None:
    p = make_prompt("q", [ChoiceOption("a", "A", "do A")])
    lines = render_choice(p)
    assert "— do A" in lines[1]


def test_callable_satisfies_choice_asker_protocol() -> None:
    class _Fake:
        async def __call__(self, prompt, options, *, default_id=None):  # type: ignore[no-untyped-def]
            return options[0].id

    assert isinstance(_Fake(), ChoiceAsker)


# --------------------------------------------------------------------------- modal


class _Host(App[None]):
    def compose(self) -> ComposeResult:
        yield Static("host")


@pytest.mark.asyncio
async def test_choice_screen_digit_selects_and_dismisses() -> None:
    from llove.term.choice_screen import ChoiceScreen

    captured: dict[str, object] = {}
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        cp = ChoicePrompt(
            prompt="pick",
            options=(ChoiceOption("a", "A"), ChoiceOption("b", "B")),
            default_id="a",
        )
        app.push_screen(ChoiceScreen(cp), lambda r: captured.__setitem__("r", r))
        await pilot.pause(0.05)
        assert isinstance(app.screen, ChoiceScreen)
        await pilot.press("2")
        await pilot.pause(0.05)
        assert captured["r"] == "b"
        assert not isinstance(app.screen, ChoiceScreen)


@pytest.mark.asyncio
async def test_choice_screen_enter_picks_highlighted_default() -> None:
    from llove.term.choice_screen import ChoiceScreen

    captured: dict[str, object] = {}
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        cp = ChoicePrompt(
            prompt="pick",
            options=(ChoiceOption("a", "A"), ChoiceOption("b", "B")),
            default_id="b",
        )
        app.push_screen(ChoiceScreen(cp), lambda r: captured.__setitem__("r", r))
        await pilot.pause(0.05)
        await pilot.press("enter")
        await pilot.pause(0.05)
        assert captured["r"] == "b"


@pytest.mark.asyncio
async def test_choice_screen_escape_dismisses_none() -> None:
    from llove.term.choice_screen import ChoiceScreen

    captured: dict[str, object] = {}
    app = _Host()
    async with app.run_test(size=(120, 40)) as pilot:
        cp = ChoicePrompt(prompt="pick", options=(ChoiceOption("a", "A"),))
        app.push_screen(ChoiceScreen(cp), lambda r: captured.__setitem__("r", r))
        await pilot.pause(0.05)
        await pilot.press("escape")
        await pilot.pause(0.05)
        assert captured["r"] is None
