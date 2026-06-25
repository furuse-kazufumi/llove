"""Stage 2 — run-control writer tests (pure, no Qt).

``RunControl`` lets the GUI request pause/resume/stop by atomically writing
``control.json`` into the run directory. The run process polls that file and
honours it (that engine-side poll is a llive contract, not part of llove). The
writer is fail-closed: only the known commands are accepted, and a monotonic
``seq`` lets the run detect a new request even if the command text repeats.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llove.core.drivers.run_control import RunControl


def test_request_writes_known_command(tmp_path: Path) -> None:
    rc = RunControl(tmp_path)
    rc.pause()
    data = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert data["command"] == "pause"
    assert data["seq"] == 1


def test_seq_increments_across_requests(tmp_path: Path) -> None:
    rc = RunControl(tmp_path)
    rc.pause()
    rc.resume()
    rc.pause()
    data = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert data["command"] == "pause"
    assert data["seq"] == 3


def test_seq_continues_from_existing_file(tmp_path: Path) -> None:
    (tmp_path / "control.json").write_text(
        json.dumps({"command": "resume", "seq": 41}), encoding="utf-8"
    )
    rc = RunControl(tmp_path)
    rc.stop()
    data = json.loads((tmp_path / "control.json").read_text(encoding="utf-8"))
    assert data["seq"] == 42
    assert data["command"] == "stop"


def test_unknown_command_rejected_fail_closed(tmp_path: Path) -> None:
    rc = RunControl(tmp_path)
    with pytest.raises(ValueError):
        rc.request("self-destruct")
    assert not (tmp_path / "control.json").exists()  # nothing written


def test_read_returns_none_when_absent(tmp_path: Path) -> None:
    assert RunControl(tmp_path).read() is None


def test_read_roundtrip(tmp_path: Path) -> None:
    rc = RunControl(tmp_path)
    rc.resume()
    got = rc.read()
    assert got is not None
    assert got["command"] == "resume"
