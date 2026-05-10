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
from .image_render_pane import (
    DiagramRenderResult,
    ImageRenderPane,
    SubprocessRunner,
    WorkerDispatcher,
    make_image_render_callback,
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
from .svg_render import (
    SVGRender,
    ascii_fallback_for_svg,
    render_svg,
    render_svg_to_png,
    rsvg_convert_available,
)

__all__ = [
    "FOLD_STATE_VERSION",
    "AuditLogView",
    "FoldRegion",
    "FoldState",
    "DiagramRenderResult",
    "ImageRenderPane",
    "MarkdownView",
    "MermaidRender",
    "NarrationView",
    "SPCChartView",
    "SVGRender",
    "SensorStreamView",
    "SubprocessRunner",
    "View",
    "apply_folds",
    "ascii_fallback",
    "ascii_fallback_for_svg",
    "default_fold_state_path",
    "find_code_block_regions",
    "find_heading_regions",
    "find_image_tool",
    "find_table_regions",
    "load_fold_state",
    "make_mermaid_image_callback",
    "mmdc_available",
    "render_mermaid",
    "render_mermaid_to_svg",
    "render_svg",
    "render_svg_to_png",
    "rsvg_convert_available",
    "run_image_render",
    "save_fold_state",
]
