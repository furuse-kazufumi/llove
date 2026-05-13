"""F25 (b) — llive データ専用 viewer サブパッケージ.

`llove/mcp/client.py` から取得した `TimelineEvent` を消費し、llive の
3 種データ (bwt_summary / route_trace / concept_update) を TUI で
可視化する viewer 群。`docs/llove_llive_bridge.md` 仕様 v1 に従う。

現状実装:
- ``BWTDashboard`` — bwt_summary event の TUI dashboard

未実装 (将来):
- ``RouteTraceViewer`` — route_trace event
- ``MemoryLinkVizPanel`` — concept_update event
"""

from llove.views.llive.bwt_dashboard import BWTDashboard

__all__ = ["BWTDashboard"]
