"""Coin-toss scenario — 50 tosses, watch the heads ratio approach 0.5.

Beginner-friendly demo: no LLMesh knowledge required. Designed so a student
can launch it and immediately see "every pane shows something".

  SensorStream: running heads_ratio (0..1). Sparkline drifts toward 0.5.
  SPC alarm   : fires when |ratio - 0.5| > 0.25 *and* we have >= 8 tosses
                (i.e. an actually-suspicious early streak, not a 1-toss blip).
  Audit       : every individual toss with running totals.
  Narration   : casual mile-marker comments at 5 / 15 / 30 / 50 tosses.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind

_TOSS_COUNT = 50
_SUSPICIOUS_DEVIATION = 0.25
_MIN_TOSSES_FOR_ALARM = 8


def _coin_outcomes(n: int, seed: int = 42) -> list[int]:
    """Deterministic LCG → 0/1 outcomes. The first 10 tosses are heavily
    heads-biased (80/20) so the SPC alarm fires early and gives the scenario
    a clear "wait, this looks suspicious!" beat. After that the bias goes
    away and the ratio settles back near 0.5."""
    state = seed & 0xFFFFFFFF
    out: list[int] = []
    for i in range(n):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        threshold = 0.80 if i < 10 else 0.50
        out.append(1 if (state / 0x7FFFFFFF) < threshold else 0)
    return out


_FACE_HEADS = """
  ╭───╮
  │ H │
  ╰───╯
""".strip("\n")

_FACE_TAILS = """
  ╭───╮
  │ T │
  ╰───╯
""".strip("\n")


class CoinTossScenario(DemoScenario):
    """Toss a coin 50 times — watch the heads ratio settle near 1/2."""

    name = "coin_toss"
    i18n_key = "coin_toss"
    default_pause = 0.18  # snappy — students lose patience
    # Override the SensorStream pane title — "SensorEvent stream" feels
    # off-key for a coin-toss demo. Audit / SPC / Narration keep their
    # generic titles since "audit log" / "SPC chart" / "narration" make
    # sense for any scenario.
    sensor_pane_title_key = "scenario.coin_toss.sensor_pane_title"

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key(
            "scenario.coin_toss.intro",
            title_key="scenario.coin_toss.intro_title",
            n=_TOSS_COUNT,
        )

        outcomes = _coin_outcomes(_TOSS_COUNT)
        heads = 0
        alarm_fired = False

        for i, x in enumerate(outcomes, start=1):
            heads += x
            ratio = heads / i

            yield Event(
                kind=EventKind.SENSOR,
                source_id="coin",
                payload={
                    "sensor_id": "heads_ratio",
                    "value": round(ratio, 4),
                    "toss": i,
                    "result": "H" if x else "T",
                    "heads": heads,
                    "tails": i - heads,
                },
            )

            yield Event(
                kind=EventKind.AUDIT,
                source_id="coin",
                payload={
                    "event": "coin.toss",
                    "n": i,
                    "result": "H" if x else "T",
                    "heads": heads,
                    "tails": i - heads,
                    "ratio": round(ratio, 4),
                },
            )

            if (
                not alarm_fired
                and i >= _MIN_TOSSES_FOR_ALARM
                and abs(ratio - 0.5) > _SUSPICIOUS_DEVIATION
            ):
                alarm_fired = True
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id="coin",
                    payload={
                        "sensor_id": "heads_ratio",
                        "value": round(ratio, 4),
                        "threshold": 0.5 + _SUSPICIOUS_DEVIATION,
                        "cusum": round(abs(ratio - 0.5) - _SUSPICIOUS_DEVIATION, 4),
                        "rule": "fair_coin_deviation",
                        "n": i,
                    },
                )
                yield narrate_key(
                    "scenario.coin_toss.alarm",
                    title_key="scenario.coin_toss.alarm_title",
                    n=i,
                    heads=heads,
                    tails=i - heads,
                    ratio=f"{ratio:.2f}",
                )

            # Mile-marker narration at 5 / 15 / 30 tosses.
            if i in {5, 15, 30}:
                face = _FACE_HEADS if x else _FACE_TAILS
                yield narrate(
                    f"```\n{face}\n```\n"
                    f"After **{i}** tosses: **{heads}** heads / **{i - heads}** tails.  "
                    f"Running ratio = **{ratio:.2f}** (target: 0.50).",
                    title=f"Mile {i}",
                )

        final_ratio = heads / _TOSS_COUNT
        yield narrate_key(
            "scenario.coin_toss.takeaway",
            title_key="scenario.coin_toss.takeaway_title",
            heads=heads,
            tails=_TOSS_COUNT - heads,
            ratio=f"{final_ratio:.2f}",
        )
