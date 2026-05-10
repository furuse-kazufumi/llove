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
from .mermaid_pane import (
    MermaidImagePane,
    SubprocessRunner,
    make_mermaid_image_callback,
    run_image_render,
)
from .mermaid_render import (
    MermaidRender,
    ascii_fallback,
    find_image_tool,
    mmdc_available,
    render_mermaid,
    render_mermaid_to_svg,
)
from .narration import NarrationView
from .sensor_stream import SensorStreamView
from .spc_chart import SPCChartView

__all__ = [
    "FOLD_STATE_VERSION",
    "AuditLogView",
    "FoldRegion",
    "FoldState",
    "MarkdownView",
    "MermaidRender",
    "NarrationView",
    "SPCChartView",
    "SensorStreamView",
    "View",
    "apply_folds",
    "ascii_fallback",
    "default_fold_state_path",
    "find_code_block_regions",
    "find_heading_regions",
    "find_image_tool",
    "find_table_regions",
    "load_fold_state",
    "mmdc_available",
    "render_mermaid",
    "render_mermaid_to_svg",
    "save_fold_state",
]
