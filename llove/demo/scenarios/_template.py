"""Copy this file to add your own scenario in 5 minutes.

Steps:
    1. Copy this file to ``my_thing.py`` (or whatever short name you want).
    2. Rename ``MyThingScenario`` to your class name and update ``name`` /
       ``title`` / ``description`` strings.
    3. Edit ``events()`` to yield your own Event sequence. Use ``narrate(...)``
       for commentary that lands in the bottom narration pane.
    4. Register your class in ``llove/demo/scenarios/__init__.py``: add the
       import and an entry in the ``SCENARIOS`` dict.
    5. ``llove demo --scenario my_thing`` — that's it.

Conventions:
    - Keep scenarios fully offline (no network, no real LLMesh node).
    - Pass ``seed`` for determinism if you use randomness.
    - Default scenario length: about 30-60 seconds (<= 200 events at 0.3 s pause).
    - Open with one ``narrate(intro, title="Scenario: ...")`` so users know
      where they are.

The Event payload is a free-form dict — views look up the keys they care
about (sensor_id, value, cusum, tokens, ...) and ignore the rest, so you can
add extra fields without breaking anything.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind


class MyThingScenario(DemoScenario):
    """One-line summary of what this scenario teaches."""

    # Short identifier used as ``llove demo --scenario <name>``.
    name = "my_thing"

    # Title shown in the menu and help output.
    title = "My thing — 10-word description"

    # Full description shown by ``llove demo --list``.
    description = (
        "Replace this with a 1-2 sentence pitch for your scenario. "
        "Mention which LLMesh feature it covers."
    )

    # Seconds between events. 0.3-0.6 reads naturally; 0.0 is for tests.
    default_pause = 0.4

    async def events(self) -> AsyncIterator[Event]:
        # Open with a brief intro so the bottom pane explains what's happening.
        yield narrate(
            "**Hello!** This is *my_thing* — replace this text with what your "
            "scenario actually demonstrates.",
            title="Scenario: my_thing",
        )

        # Show some sensor readings.
        for i in range(5):
            yield Event(
                kind=EventKind.SENSOR,
                source_id="my_source",
                payload={"sensor_id": "my_sensor", "value": float(i)},
            )

        # Drop a piece of narration mid-scenario.
        yield narrate("Step 2 — say something useful here.", title="Step 2")

        # Show an alarm event.
        yield Event(
            kind=EventKind.SPC_ALARM,
            source_id="my_source",
            payload={"sensor_id": "my_sensor", "cusum": 7.5, "threshold": 5.0},
        )

        # Show an audit entry. Audit entries appear in the audit-log pane.
        yield Event(
            kind=EventKind.AUDIT,
            source_id="my_source",
            payload={"event": "my_thing.fired", "note": "all done"},
        )

        # Close with a take-away.
        yield narrate(
            "Replace this with the **one-line lesson** users should remember.",
            title="Take-away",
        )
