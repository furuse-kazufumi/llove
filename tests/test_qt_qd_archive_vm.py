"""Stage 3 — QD-archive view-model tests (pure, no Qt).

The QD metrics file (``metrics_*_qd.jsonl``) carries ``archive_cells`` (cumulative
niche coverage, non-decreasing) and ``occupied_cells`` (live occupancy). Acceptance
signal (design P6): the archive keeps growing while live occupancy can fall as the
run converges, so the panel must surface both — and tolerate a missing
``occupied_cells`` field.
"""

from __future__ import annotations

import math

from llove.core.viewmodels.qd_archive import QdArchiveVM


def test_feed_picks_archive_and_occupied() -> None:
    vm = QdArchiveVM()
    assert vm.feed({"generation": 0, "archive_cells": 29, "occupied_cells": 29})
    assert vm.feed({"generation": 1, "archive_cells": 30, "occupied_cells": 26})
    assert vm.count == 2
    assert vm.generations == [0, 1]
    assert vm.archive_cells == [29.0, 30.0]
    assert vm.occupied_cells == [29.0, 26.0]


def test_feed_rejects_row_without_archive() -> None:
    vm = QdArchiveVM()
    assert vm.feed({"generation": 0, "diversity": 0.3}) is False
    assert vm.count == 0


def test_occupied_is_optional() -> None:
    vm = QdArchiveVM()
    assert vm.feed({"generation": 2, "archive_cells": 40})
    assert vm.count == 1
    assert math.isnan(vm.occupied_cells[0])


def test_feed_line_parses_qd_row() -> None:
    vm = QdArchiveVM()
    assert vm.feed_line(
        '{"generation":9999,"archive_cells":70,"occupied_cells":9,"monoculture":0.4375}'
    )
    assert vm.feed_line("not json") is False
    assert vm.count == 1
    assert vm.archive_cells == [70.0]
    assert vm.occupied_cells == [9.0]


def test_series_aligned() -> None:
    vm = QdArchiveVM()
    vm.feed({"generation": 0, "archive_cells": 5, "occupied_cells": 5})
    s = vm.series()
    assert set(s) >= {"generation", "archive_cells", "occupied_cells"}
    assert len(s["generation"]) == len(s["archive_cells"]) == len(s["occupied_cells"]) == 1
