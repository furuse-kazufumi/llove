"""Vision scenario — VLM analyses belt-conveyor frames, flags defects.

Image is rendered as ASCII art so the scenario stays fully terminal-native and
dependency-free. The Event payload also carries an optional ``image_b64`` field
so a richer external viewer (e.g. tools/qt_viewer/vision_viewer.py) can render
the same frame in pixels.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind

# ASCII art frames — 22 cols x 8 rows. The defect frame replaces the cylinder
# at column 13 with a misshapen blob. No Pillow / no graphics deps.
_FRAME_OK = """
......................
.[ o ][ o ][ o ][ o ].
.[ o ][ o ][ o ][ o ].
.>>>>>>>>>>>>>>>>>>>>.
.belt: 0.42 m/s ......
......................
""".strip("\n")

_FRAME_DEFECT = """
......................
.[ o ][ o ][###][ o ].
.[ o ][ o ][###][ o ].
.>>>>>>>>>>>>>>>>>>>>.
.belt: 0.42 m/s ......
.       ^bbox(13,1)..
""".strip("\n")

# (frame_id, ascii_art, vlm_caption, defect_score, is_defect)
_FRAMES: list[dict[str, Any]] = [
    {"id": 1, "art": _FRAME_OK, "caption": "4 cylinders aligned on belt, no surface anomaly", "score": 0.04, "defect": False},
    {"id": 2, "art": _FRAME_OK, "caption": "4 cylinders aligned on belt, no surface anomaly", "score": 0.06, "defect": False},
    {"id": 3, "art": _FRAME_OK, "caption": "4 cylinders aligned on belt, no surface anomaly", "score": 0.05, "defect": False},
    {"id": 4, "art": _FRAME_DEFECT, "caption": "Cylinder #3 surface blackened — possible burr or contamination", "score": 0.83, "defect": True},
    {"id": 5, "art": _FRAME_OK, "caption": "4 cylinders aligned on belt, no surface anomaly", "score": 0.07, "defect": False},
    {"id": 6, "art": _FRAME_DEFECT, "caption": "Cylinder #3 surface blackened — same defect class as frame #4", "score": 0.79, "defect": True},
    {"id": 7, "art": _FRAME_OK, "caption": "4 cylinders aligned on belt, no surface anomaly", "score": 0.05, "defect": False},
]


class VisionScenario(DemoScenario):
    """Belt-conveyor inspection — VLM tags defects across 7 frames."""

    name = "vision"
    i18n_key = "vision"
    default_pause = 0.55

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.vision.intro", title_key="scenario.vision.intro_title")

        defects = 0
        for frame in _FRAMES:
            # Show the ASCII frame in the narration pane so the user "sees" it
            # without needing a graphics-capable terminal.
            yield narrate(
                f"```\n{frame['art']}\n```\n**VLM**: {frame['caption']}",
                title=f"Frame #{frame['id']}",
            )

            yield Event(
                kind=EventKind.SENSOR,
                source_id="vlm_inspector",
                payload={
                    "sensor_id": "defect_score",
                    "value": frame["score"],
                    "frame_id": frame["id"],
                    "image_ascii": frame["art"],
                    # External viewers can use this; TUI ignores it.
                    "image_b64": None,
                    "vlm_caption": frame["caption"],
                },
            )

            if frame["defect"]:
                defects += 1
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id="vlm_inspector",
                    payload={
                        "sensor_id": "defect_score",
                        "value": frame["score"],
                        "threshold": 0.5,
                        "cusum": frame["score"],
                        "frame_id": frame["id"],
                        "bbox": [13, 1, 16, 2],  # x1, y1, x2, y2 in ASCII grid
                        "rule": "vlm_defect_threshold",
                    },
                )
                yield Event(
                    kind=EventKind.AUDIT,
                    source_id="vlm_inspector",
                    payload={
                        "event": "vision.defect_logged",
                        "frame_id": frame["id"],
                        "defect_class": "surface_contamination",
                        "score": frame["score"],
                    },
                )

        yield narrate_key(
            "scenario.vision.takeaway",
            title_key="scenario.vision.takeaway_title",
            defects=defects,
            total=len(_FRAMES),
        )
