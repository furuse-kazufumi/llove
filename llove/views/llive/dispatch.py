"""F25 (e) — TimelineEvent dispatcher for the 3 llive viewers.

Polling driver の核。`TimelineClient.fetch_recent()` の結果を
`event_type` で振り分け、対応する viewer に `feed_events` する小さな
オーケストレータ。

設計判断:

- **viewers は optional**: BWTDashboard だけ表示したい / RouteTraceViewer
  と MemoryLinkVizPanel の 2 つだけ並べたい、いずれも対応可。``None``
  を渡された viewer はその event_type をスキップする。
- **副作用は dispatcher の外**: ``dispatch_events`` は純粋に振り分けて
  ``feed_events`` を呼ぶだけ。polling 周期や Textual `Timer` などの
  時間軸は ``TimelinePollDriver`` が扱う。pure function と driver を
  別レイヤに分離することで、polling は手動 (CLI) でも自動 (TUI) でも
  同じ dispatcher を使える。
- **戻り値で観測性**: 各 event_type で何件追加したかを返す。caller は
  ステータスバーや log に「Added: bwt=3 trace=1 link=0」のように出せる。
"""

from __future__ import annotations

from dataclasses import dataclass

from llove.mcp.client import TimelineClient, TimelineEvent
from llove.views.llive.bwt_dashboard import BWTDashboard
from llove.views.llive.cognitive_mesh_panel import (
    COG_EVENT_TYPES,
    CognitiveMeshPanel,
)
from llove.views.llive.memory_link_panel import MemoryLinkVizPanel
from llove.views.llive.route_trace_viewer import RouteTraceViewer

# 既知 event_type の集合 — 未知の event_type が来たときに "unrouted" として
# カウントするための区別。
KNOWN_EVENT_TYPES: frozenset[str] = frozenset(
    {"bwt_summary", "route_trace", "concept_update"}
) | COG_EVENT_TYPES


@dataclass(frozen=True)
class DispatchResult:
    """One polling round の集計結果. すべて非負整数."""

    bwt_added: int = 0
    trace_added: int = 0
    link_added: int = 0
    cog_added: int = 0  # M8.1 cog mesh events
    unrouted: int = 0  # 既知 event_type だが viewer=None の数
    unknown: int = 0   # KNOWN_EVENT_TYPES に無い event_type の数

    @property
    def total_added(self) -> int:
        return self.bwt_added + self.trace_added + self.link_added + self.cog_added

    def status_line(self) -> str:
        """ステータスバー向けの 1 行サマリ.

        ``unrouted`` (既知 event_type だが viewer=None) や ``unknown``
        (未知 event_type) も 0 以外なら events は届いているので、
        "no new events" は **全カウンタが 0 のときだけ**返す。
        """
        if (
            self.total_added == 0
            and self.unrouted == 0
            and self.unknown == 0
        ):
            return "no new events"
        parts: list[str] = []
        if self.bwt_added:
            parts.append(f"bwt+{self.bwt_added}")
        if self.trace_added:
            parts.append(f"trace+{self.trace_added}")
        if self.link_added:
            parts.append(f"link+{self.link_added}")
        if self.cog_added:
            parts.append(f"cog+{self.cog_added}")
        if self.unrouted:
            parts.append(f"unrouted={self.unrouted}")
        if self.unknown:
            parts.append(f"unknown={self.unknown}")
        return " ".join(parts) if parts else "no new events"


def dispatch_events(
    events: list[TimelineEvent],
    *,
    bwt: BWTDashboard | None = None,
    trace: RouteTraceViewer | None = None,
    link: MemoryLinkVizPanel | None = None,
    cog: CognitiveMeshPanel | None = None,
) -> DispatchResult:
    """Split ``events`` by ``event_type`` and feed each viewer.

    Each viewer is optional — passing ``None`` skips that event_type
    entirely (counted as ``unrouted``). Returns a structured count so
    callers can render a status line.
    """
    # group by event_type 1 パスでバケット化
    bwt_evs: list[TimelineEvent] = []
    trace_evs: list[TimelineEvent] = []
    link_evs: list[TimelineEvent] = []
    cog_evs: list[TimelineEvent] = []
    unknown = 0
    for ev in events:
        if ev.event_type == "bwt_summary":
            bwt_evs.append(ev)
        elif ev.event_type == "route_trace":
            trace_evs.append(ev)
        elif ev.event_type == "concept_update":
            link_evs.append(ev)
        elif ev.event_type in COG_EVENT_TYPES:
            cog_evs.append(ev)
        else:
            unknown += 1

    unrouted = 0
    bwt_added = 0
    trace_added = 0
    link_added = 0
    cog_added = 0

    if bwt is not None and bwt_evs:
        bwt_added = bwt.feed_events(bwt_evs)
    elif bwt is None:
        unrouted += len(bwt_evs)

    if trace is not None and trace_evs:
        trace_added = trace.feed_events(trace_evs)
    elif trace is None:
        unrouted += len(trace_evs)

    if link is not None and link_evs:
        link_added = link.feed_events(link_evs)
    elif link is None:
        unrouted += len(link_evs)

    if cog is not None and cog_evs:
        cog_added = cog.feed_events(cog_evs)
    elif cog is None:
        unrouted += len(cog_evs)

    return DispatchResult(
        bwt_added=bwt_added,
        trace_added=trace_added,
        link_added=link_added,
        cog_added=cog_added,
        unrouted=unrouted,
        unknown=unknown,
    )


# ---------------------------------------------------------------------------
# Poll driver — synchronous, time-axis agnostic
# ---------------------------------------------------------------------------


@dataclass
class TimelinePollDriver:
    """`TimelineClient.fetch_recent` を 1 回呼んで 3 viewer に流す薄い周回器.

    Textual の ``Timer`` から ``poll_once()`` を呼ぶ前提。ループそのもの
    は持たない (caller が周期を制御)。これにより:

    - CLI から手動 ``driver.poll_once()`` 1 発で確認可能
    - 単体テストで時間軸を制御する必要なし
    - 別の polling 周期実装 (asyncio Timer / threading Timer) と入れ替え可

    ``last_result`` で直近の polling 結果を保持。``status_line()`` で
    ステータスバー向けの文字列を取り出せる。
    """

    client: TimelineClient
    bwt: BWTDashboard | None = None
    trace: RouteTraceViewer | None = None
    link: MemoryLinkVizPanel | None = None
    limit: int = 50
    node_id: str = ""
    last_result: DispatchResult = DispatchResult()

    def poll_once(self) -> DispatchResult:
        """1 回だけ ``fetch_recent`` → ``dispatch_events`` を実行."""
        events = self.client.fetch_recent(
            limit=self.limit, node_id=self.node_id
        )
        result = dispatch_events(
            events, bwt=self.bwt, trace=self.trace, link=self.link
        )
        self.last_result = result
        return result

    def status_line(self) -> str:
        """Last polling round の summary + client.last_error も併記."""
        base = self.last_result.status_line()
        if self.client.last_error:
            return f"{base}  (err: {self.client.last_error})"
        return base


__all__ = [
    "KNOWN_EVENT_TYPES",
    "DispatchResult",
    "TimelinePollDriver",
    "dispatch_events",
]
