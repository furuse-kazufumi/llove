"""F25 (b) — BWT (Backward Transfer) Dashboard.

llive `bwt_summary` event を TUI dashboard として可視化する viewer。
`docs/llove_llive_bridge.md` 仕様 v1 に従う。

表示要素 (上から):

    BWT Dashboard
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Latest run: 2026-05-14T08:30Z  bwt=-0.008  acc=0.78  n=5
    BWT trend: ▁▂▁▃▅▄▆▇ (8 runs)
    Per-task drop (latest):
      t1 ──┤ -0.010
      t2 ──┤ -0.006
      t3 ──┤ -0.008
      t4 ──┤ -0.009
      t5     ┤  0.000

`feed_events(list[TimelineEvent])` で全件 idempotent 取り込み。event_id で
dedup するので、polling のたびに `fetch_recent()` の結果を全件渡しても
無駄な再描画を避けられる (内部で「変化があったときだけ render」する)。

Pure 関数 + Textual `Static` の薄い継承で UI 部分はテスト容易に分離。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from textual.widgets import Static

from llove.mcp.client import TimelineEvent
from llove.views.base import View

# Sparkline blocks — low → high (metric_dashboard と同じ文字を使う)
_SPARK = "▁▂▃▄▅▆▇█"


# ---------------------------------------------------------------------------
# Pure rendering — UI 非依存、テスト容易
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BWTRun:
    """One ``bwt_summary`` event reduced to the fields the dashboard needs.

    Lenient defaults so missing metadata doesn't crash the view.
    """

    event_id: str
    timestamp_utc: str
    bwt: float
    avg_accuracy: float
    n_tasks: int
    per_task_drop: dict[str, float]
    task_order: tuple[str, ...]

    @classmethod
    def from_event(cls, ev: TimelineEvent) -> BWTRun | None:
        """Convert a ``TimelineEvent`` into a ``BWTRun``. Non-BWT events
        and malformed payloads return ``None``."""
        if ev.event_type != "bwt_summary":
            return None
        md = ev.metadata or {}
        try:
            bwt = float(md.get("bwt", 0.0))
            acc = float(md.get("avg_accuracy", 0.0))
            n = int(md.get("n_tasks", 0))
        except (TypeError, ValueError):
            return None
        raw_drop = md.get("per_task_drop") or {}
        if not isinstance(raw_drop, dict):
            return None
        # キーは task name (str), 値は float に揃える
        per_drop: dict[str, float] = {}
        for k, v in raw_drop.items():
            try:
                per_drop[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        order = md.get("task_order")
        order_tuple = (
            tuple(str(x) for x in order) if isinstance(order, list) else ()
        )
        return cls(
            event_id=ev.event_id,
            timestamp_utc=ev.timestamp_utc,
            bwt=bwt,
            avg_accuracy=acc,
            n_tasks=n,
            per_task_drop=per_drop,
            task_order=order_tuple,
        )


def render_sparkline(samples: list[float]) -> str:
    """`metric_dashboard._sparkline` と同等。BWT trend 用に独立コピー
    (依存方向を `llive viewer → metric_dashboard` にしない設計判断)。"""
    if len(samples) < 2:
        return ""
    lo = min(samples)
    hi = max(samples)
    span = hi - lo
    if span <= 0:
        return _SPARK[len(_SPARK) // 2] * len(samples)
    out: list[str] = []
    for s in samples:
        frac = (s - lo) / span
        idx = min(len(_SPARK) - 1, max(0, round(frac * (len(_SPARK) - 1))))
        out.append(_SPARK[idx])
    return "".join(out)


def render_per_task_drop(
    per_drop: dict[str, float],
    task_order: tuple[str, ...] = (),
    *,
    bar_width: int = 20,
) -> str:
    """Per-task drop を水平 ASCII bar として整形.

    各タスクの drop 値を ``-max_abs..+max_abs`` のスケールで横棒に。
    負の drop (regression) は ``│ ──`` で左方向、正の drop (improvement)
    は ``── │`` で右方向。center 軸を ``│`` で示す。
    """
    if not per_drop:
        return "  (no per-task drop data)"
    keys = list(task_order) if task_order else sorted(per_drop)
    # task_order に無い key も最後に追加 (forward-compat)
    for k in per_drop:
        if k not in keys:
            keys.append(k)
    max_abs = max((abs(per_drop.get(k, 0.0)) for k in keys), default=0.0)
    if max_abs <= 0:
        max_abs = 1.0  # 全 0 のときは axis のみ表示
    half = max(1, bar_width // 2)
    lines: list[str] = []
    for k in keys:
        v = per_drop.get(k, 0.0)
        cells = int(round(abs(v) / max_abs * half))
        if v < 0:
            left = " " * (half - cells) + "─" * cells
            right = " " * half
        elif v > 0:
            left = " " * half
            right = "─" * cells + " " * (half - cells)
        else:
            left = " " * half
            right = " " * half
        lines.append(f"  {k:<6} {left}│{right} {v:+.3f}")
    return "\n".join(lines)


def render_dashboard(runs: list[BWTRun], *, sparkline_window: int = 24) -> str:
    """Build the entire dashboard text from a chronological list of runs.

    ``runs[-1]`` is treated as the latest (the caller is responsible for
    sorting; ``BWTDashboard`` does it). Empty list → placeholder.
    """
    if not runs:
        return "(no bwt runs yet)"
    latest = runs[-1]
    header = (
        f"Latest run: {latest.timestamp_utc}  "
        f"bwt={latest.bwt:+.4f}  acc={latest.avg_accuracy:.3f}  "
        f"n={latest.n_tasks}"
    )
    spark_samples = [r.bwt for r in runs[-sparkline_window:]]
    spark = render_sparkline(spark_samples)
    spark_line = (
        f"BWT trend ({len(spark_samples)} runs): {spark}"
        if spark
        else f"BWT trend: (need >=2 runs, have {len(spark_samples)})"
    )
    bars = render_per_task_drop(latest.per_task_drop, latest.task_order)
    return "\n".join(
        [
            header,
            spark_line,
            "Per-task drop (latest):",
            bars,
        ]
    )


# ---------------------------------------------------------------------------
# Textual widget
# ---------------------------------------------------------------------------


class BWTDashboard(Static, View):
    """Live BWT dashboard widget.

    ``feed_events(events)`` is the only ingress — pass it the result of
    ``TimelineClient.fetch_recent(event_type="bwt_summary")`` periodically
    (e.g. from a Textual ``Timer``). The widget dedups by ``event_id`` so
    repeated polling is idempotent.
    """

    name = "bwt_dashboard"
    title = "BWT Dashboard"

    DEFAULT_CSS = """
    BWTDashboard {
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }
    """

    def __init__(self, *, sparkline_window: int = 24) -> None:
        super().__init__("(no bwt runs yet)")
        self._sparkline_window = max(2, int(sparkline_window))
        self._runs: deque[BWTRun] = deque(maxlen=200)
        self._seen_ids: set[str] = set()
        self.border_title = "BWT Dashboard"
        self.border_subtitle = ""

    # ------------------------------------------------------------------

    def feed_events(self, events: list[TimelineEvent]) -> int:
        """Add new BWT runs (skipping already-seen event_ids).

        Returns the count of newly-ingested runs. The caller can use this
        to decide whether to re-render or to show a "live" indicator.
        """
        added = 0
        for ev in events:
            if ev.event_id and ev.event_id in self._seen_ids:
                continue
            run = BWTRun.from_event(ev)
            if run is None:
                continue
            if run.event_id:
                self._seen_ids.add(run.event_id)
            self._runs.append(run)
            added += 1
        if added > 0:
            self._render()
        return added

    def clear(self) -> None:
        """Reset state. Useful for tests and explicit refresh."""
        self._runs.clear()
        self._seen_ids.clear()
        self._render()

    def run_count(self) -> int:
        return len(self._runs)

    def latest(self) -> BWTRun | None:
        return self._runs[-1] if self._runs else None

    # ------------------------------------------------------------------

    def _render(self) -> None:
        text = render_dashboard(
            list(self._runs), sparkline_window=self._sparkline_window
        )
        self.update(text)
        self.border_subtitle = f"runs: {len(self._runs)}"


# ---------------------------------------------------------------------------
# Mock fixture — テスト / デモ用. 実 polling driver と同じ shape を返す.
# ---------------------------------------------------------------------------


def make_mock_bwt_events(n: int = 5, base_bwt: float = -0.01) -> list[TimelineEvent]:
    """Generate ``n`` synthetic ``bwt_summary`` events for offline demos.

    Useful in CI / examples / `llove demo` to render the dashboard without
    a running llmesh ingest endpoint.
    """
    events: list[TimelineEvent] = []
    for i in range(n):
        events.append(
            TimelineEvent(
                event_id=f"mock-bwt-{i}",
                task_id=f"mock-task-{i:04d}",
                node_id="llive-mock",
                event_type="bwt_summary",
                timestamp_utc=f"2026-05-14T08:{30 + i:02d}:00Z",
                metadata={
                    "version": 1,
                    "bwt": base_bwt + 0.001 * i,
                    "avg_accuracy": 0.78 - 0.005 * (i % 3),
                    "n_tasks": 5,
                    "task_order": ["t1", "t2", "t3", "t4", "t5"],
                    "per_task_drop": {
                        "t1": -0.010 + 0.002 * i,
                        "t2": -0.006,
                        "t3": -0.008 + 0.003 * (i % 2),
                        "t4": -0.009,
                        "t5": 0.000 + 0.001 * (i % 3),
                    },
                },
            )
        )
    return events


__all__ = [
    "BWTDashboard",
    "BWTRun",
    "make_mock_bwt_events",
    "render_dashboard",
    "render_per_task_drop",
    "render_sparkline",
]


def __getattr__(name: str) -> Any:
    # No special fallback at the moment; reserved for future kind-specific
    # accessors so callers can stay forward-compatible.
    raise AttributeError(name)
