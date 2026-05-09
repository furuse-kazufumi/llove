"""Point-cloud scenario — LiDAR top-view of a parts-tray, missing-slot detection.

Renders the cloud as an ASCII top-view so the scenario stays terminal-native.
The Event payload also carries the raw ``points_xyz`` list, so an external Qt
viewer (tools/qt_viewer/pointcloud_viewer.py) can spin the cloud in 3D.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from llove.demo.scenarios.base import DemoScenario, narrate, narrate_key
from llove.events import Event, EventKind

# A 4x3 tray. Each slot nominally has ~24 LiDAR returns. We synthesize:
#  - frame 1: full tray
#  - frame 2: same
#  - frame 3: slot (1, 2) missing  ← top-right empty
#  - frame 4: missing slot persists
_GRID_W = 24
_GRID_H = 7


def _render_topview(missing: tuple[int, int] | None) -> str:
    """Build a 24x7 ASCII top-view of the 4x3 tray."""
    rows = ["." * _GRID_W for _ in range(_GRID_H)]
    grid = [list(r) for r in rows]
    # Tray frame.
    for x in range(_GRID_W):
        grid[0][x] = "-"
        grid[_GRID_H - 1][x] = "-"
    for y in range(_GRID_H):
        grid[y][0] = "|"
        grid[y][_GRID_W - 1] = "|"
    # Slots: 4 columns by 3 rows. Slot (col, row) -> centre cell.
    for col in range(4):
        for row in range(3):
            cx = 3 + col * 5
            cy = 1 + row * 2
            if missing == (col, row):
                # Empty slot.
                grid[cy][cx] = " "
                grid[cy][cx + 1] = " "
            else:
                # Filled slot — dense LiDAR returns.
                grid[cy][cx] = "#"
                grid[cy][cx + 1] = "#"
    return "\n".join("".join(r) for r in grid)


def _synth_points(missing: tuple[int, int] | None) -> list[tuple[float, float, float]]:
    """Generate an XYZ list — 24 returns per filled slot, 0 for missing."""
    pts: list[tuple[float, float, float]] = []
    for col in range(4):
        for row in range(3):
            if missing == (col, row):
                continue
            cx = float(col) * 0.10 + 0.05
            cy = float(row) * 0.10 + 0.05
            for k in range(24):
                # Deterministic jitter via LCG-style hash.
                j = ((k * 1103515245 + 12345) & 0xFF) / 255.0 - 0.5
                pts.append((cx + j * 0.02, cy + (j * 0.7) * 0.02, 0.30 + j * 0.01))
    return pts


_FRAMES: list[dict[str, Any]] = [
    {"id": 1, "missing": None},
    {"id": 2, "missing": None},
    {"id": 3, "missing": (3, 0)},  # top-right slot
    {"id": 4, "missing": (3, 0)},
]


class PointCloudScenario(DemoScenario):
    """LiDAR scan of a parts tray, detect a missing slot."""

    name = "pointcloud"
    i18n_key = "pointcloud"
    default_pause = 0.6

    async def events(self) -> AsyncIterator[Event]:
        yield narrate_key("scenario.pointcloud.intro", title_key="scenario.pointcloud.intro_title")

        alarms = 0
        for frame in _FRAMES:
            missing = frame["missing"]
            topview = _render_topview(missing)
            pts = _synth_points(missing)
            density = len(pts)

            yield narrate(
                f"```\n{topview}\n```\n**LiDAR returns**: {density} points "
                f"({'tray full' if missing is None else f'slot {missing} empty'})",
                title=f"Scan #{frame['id']}",
            )

            yield Event(
                kind=EventKind.SENSOR,
                source_id="lidar_topview",
                payload={
                    "sensor_id": "tray_density",
                    "value": density,
                    "frame_id": frame["id"],
                    "topview_ascii": topview,
                    # External 3D viewers consume this; TUI ignores it.
                    "points_xyz": pts,
                    "missing_slot": list(missing) if missing else None,
                },
            )

            if missing is not None:
                alarms += 1
                yield Event(
                    kind=EventKind.SPC_ALARM,
                    source_id="lidar_topview",
                    payload={
                        "sensor_id": "tray_density",
                        "value": density,
                        "threshold": 240,
                        "cusum": 288 - density,
                        "rule": "density_drop",
                        "missing_slot": list(missing),
                    },
                )

        yield Event(
            kind=EventKind.AUDIT,
            source_id="lidar_topview",
            payload={
                "event": "pointcloud.scan_summary",
                "frames": len(_FRAMES),
                "alarms": alarms,
                "verdict": "missing slot at column 3, row 0 confirmed across 2 frames",
            },
        )

        yield narrate_key(
            "scenario.pointcloud.takeaway",
            title_key="scenario.pointcloud.takeaway_title",
            alarms=alarms,
        )
