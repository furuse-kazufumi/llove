"""F25 (b/c/d/e) — llive データ専用 viewer サブパッケージ.

`llove/mcp/client.py` から取得した `TimelineEvent` を消費し、llive の
3 種データ (bwt_summary / route_trace / concept_update) を TUI で
可視化する viewer 群。`docs/llove_llive_bridge.md` 仕様 v1 に従う。

実装済:
- ``BWTDashboard`` — bwt_summary event の TUI dashboard
- ``RouteTraceViewer`` — route_trace event の TUI viewer
- ``MemoryLinkVizPanel`` — concept_update event の TUI panel
- ``TimelinePollDriver`` / ``dispatch_events`` — 3 viewer への自動振り分け
  + 周期 polling driver (F25 e)

Mock fixtures (オフラインデモ / CI 用):
- ``make_mock_bwt_events(n)``
- ``make_mock_route_trace_events(n)``
- ``make_mock_concept_events(n)``
"""

from llove.views.llive.bwt_dashboard import (
    BWTDashboard,
    make_mock_bwt_events,
)
from llove.views.llive.dispatch import (
    DispatchResult,
    TimelinePollDriver,
    dispatch_events,
)
from llove.views.llive.memory_link_panel import (
    MemoryLinkVizPanel,
    make_mock_concept_events,
)
from llove.views.llive.route_trace_viewer import (
    RouteTraceViewer,
    make_mock_route_trace_events,
)

__all__ = [
    "BWTDashboard",
    "DispatchResult",
    "MemoryLinkVizPanel",
    "RouteTraceViewer",
    "TimelinePollDriver",
    "dispatch_events",
    "make_mock_bwt_events",
    "make_mock_concept_events",
    "make_mock_route_trace_events",
]
