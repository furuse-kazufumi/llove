"""Views — Textual widgets that consume Events and render them."""

from __future__ import annotations

from .audit_log import AuditLogView
from .base import View
from .folding import (
    FoldRegion,
    FoldState,
    apply_folds,
    find_code_block_regions,
    find_heading_regions,
    find_table_regions,
)
from .folding_persistence import (
    FOLD_STATE_VERSION,
    default_fold_state_path,
    load_fold_state,
    save_fold_state,
)
from .markdown_view import MarkdownView
from .narration import NarrationView
from .sensor_stream import SensorStreamView
from .spc_chart import SPCChartView

__all__ = [
    "FOLD_STATE_VERSION",
    "AuditLogView",
    "FoldRegion",
    "FoldState",
    "MarkdownView",
    "NarrationView",
    "SPCChartView",
    "SensorStreamView",
    "View",
    "apply_folds",
    "default_fold_state_path",
    "find_code_block_regions",
    "find_heading_regions",
    "find_table_regions",
    "load_fold_state",
    "save_fold_state",
]
