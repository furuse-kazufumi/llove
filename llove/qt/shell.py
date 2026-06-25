"""Stage 2 OS-like shell: a dockable QMainWindow hosting Qt panels.

``LoveShell`` is the desktop-shell / window-manager metaphor (design §2): each
``WindowType`` Qt builder is a "desktop app" launched from the View menu into a
dock widget that can be docked / floated / tabbed. It saves and restores a
*perspective* (which panels are open + their dock geometry).

Docking uses Qt's built-in ``QDockWidget`` (zero extra dependency, ships with
PySide6). The design's preferred QtAds "VS Code-class" docking is a drop-in
upgrade for a later stage (PySide6-QtAds is a compiled third-party package
without a guaranteed wheel, so it is kept out of the always-on path).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6 import QtCore, QtWidgets

from llove.qt.registry import register_qt_window_types
from llove.window.types import get_window_type, list_window_types


class LoveShell(QtWidgets.QMainWindow):
    """A dockable shell that launches Qt panels from the WindowType Registry."""

    def __init__(
        self,
        run_dir: str | Path | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        register_qt_window_types()
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.setWindowTitle("llove Shell")
        self.setObjectName("llove_shell")
        self.setDockNestingEnabled(True)
        self._docks: list[QtWidgets.QDockWidget] = []
        self._build_menu()

    # ---- menu ------------------------------------------------------------
    def _build_menu(self) -> None:
        view_menu = self.menuBar().addMenu("&View")
        for wt in list_window_types("visualization"):
            action = view_menu.addAction(f"New: {wt.display_name}")
            action.triggered.connect(
                lambda _checked=False, type_id=wt.id: self.open_window(type_id)
            )

    # ---- window launching ------------------------------------------------
    def _default_config(self, type_id: str) -> dict[str, Any]:
        if self.run_dir is None:
            return {}
        if type_id == "viz.fitness_trajectory":
            return {"metrics_path": str(self.run_dir / "metrics.jsonl")}
        if type_id == "viz.run_monitor":
            return {"run_dir": str(self.run_dir)}
        return {}

    def open_window(
        self, type_id: str, config: dict[str, Any] | None = None
    ) -> QtWidgets.QDockWidget | None:
        """Build the panel for ``type_id`` and dock it; ``None`` if no builder."""
        wt = get_window_type(type_id)
        if wt is None or wt.builder is None:
            return None
        cfg = config if config is not None else self._default_config(type_id)
        widget = wt.builder(cfg)

        dock = QtWidgets.QDockWidget(wt.display_name, self)
        index = sum(1 for d in self._docks if d.property("type_id") == type_id)
        dock.setObjectName(f"{type_id}#{index}")
        dock.setProperty("type_id", type_id)
        dock.setWidget(widget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, dock)
        self._docks.append(dock)
        return dock

    @property
    def dock_count(self) -> int:
        return len(self._docks)

    def open_type_ids(self) -> list[str]:
        ids: list[str] = []
        for d in self._docks:
            tid = d.property("type_id")
            if tid is not None:
                ids.append(str(tid))
        return ids

    # ---- perspective persistence ----------------------------------------
    def save_perspective(self, path: str | Path) -> None:
        """Save open panels + dock geometry as a JSON perspective file."""
        payload = {
            "schema": "llove_perspective/v1",
            "open": [
                {"type_id": d.property("type_id"), "object_name": d.objectName()}
                for d in self._docks
            ],
            "geometry": bytes(self.saveGeometry().toBase64().data()).decode("ascii"),
            "state": bytes(self.saveState().toBase64().data()).decode("ascii"),
        }
        Path(path).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def restore_perspective(self, path: str | Path) -> None:
        """Reopen the saved panels and restore their dock geometry."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for item in data.get("open", []):
            type_id = item.get("type_id")
            if not type_id:
                continue
            dock = self.open_window(str(type_id))
            object_name = item.get("object_name")
            if dock is not None and object_name:
                dock.setObjectName(str(object_name))
        geometry = data.get("geometry")
        state = data.get("state")
        if geometry:
            self.restoreGeometry(QtCore.QByteArray.fromBase64(geometry.encode("ascii")))
        if state:
            self.restoreState(QtCore.QByteArray.fromBase64(state.encode("ascii")))


__all__ = ["LoveShell"]
