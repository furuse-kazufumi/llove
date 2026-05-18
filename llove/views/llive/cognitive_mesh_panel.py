"""F25 / M8.1 — Cognitive Mesh Panel (skeleton).

llive `cog_proactive_utterance` / `cog_risk_alert` / `cog_quarantine_pending`
event 群を 1 つの読み取り専用パネルで表示する skeleton viewer.

設計判断 (本パネル):
- **3 種 event を 1 widget で統合表示** — 「能動性 / 安全 / 隔離」の
  3 系統を独立に並べず、time-stamp 順の単一ペインで読む UI 仮説。
  Phase 5 M8.1 で操作者と本パターン (vs. 3 widget 分割) を比較する。
- **idempotent feed_events** — event_id で dedup、複数 polling round で
  同じ events を渡しても多重カウントしない。BWTDashboard と同じ pattern.
- **pure rendering** — `_render_text(events)` は Static の外でテスト可能.
- **TUI は本 file に**、配線 (dispatch) は ``dispatch.py`` 側で増設.

`docs/llove_llive_bridge.md` 仕様 v1 に従う。Phase 6 で実 llive emit と
配線、本 skeleton 段階では `make_mock_cog_events(n)` で UI 確認できる.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from textual.widgets import Static

from llove.mcp.client import TimelineEvent
from llove.views.base import View

# 既知 event_type — dispatch 側と一致を維持
COG_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "cog_proactive_utterance",
        "cog_risk_alert",
        "cog_quarantine_pending",
    }
)


CogKind = Literal["proactive", "risk", "quarantine"]


@dataclass(frozen=True)
class CogEntry:
    """1 cog event を読み取り用に正規化したもの."""

    event_id: str
    timestamp_utc: str
    kind: CogKind
    summary: str

    @classmethod
    def from_event(cls, ev: TimelineEvent) -> "CogEntry | None":
        if ev.event_type not in COG_EVENT_TYPES:
            return None
        md = ev.metadata or {}
        if ev.event_type == "cog_proactive_utterance":
            content = str(md.get("content", "(no content)"))
            mode = str(md.get("mode", "timer"))
            gv = md.get("gift_value")
            gv_part = f" gv={float(gv):.2f}" if isinstance(gv, (int, float)) else ""
            return cls(
                event_id=ev.event_id,
                timestamp_utc=ev.timestamp_utc,
                kind="proactive",
                summary=f"[{mode}]{gv_part} {content}",
            )
        if ev.event_type == "cog_risk_alert":
            model = str(md.get("model_name", "?"))
            score = md.get("score")
            score_part = f"={float(score):.2f}" if isinstance(score, (int, float)) else ""
            return cls(
                event_id=ev.event_id,
                timestamp_utc=ev.timestamp_utc,
                kind="risk",
                summary=f"ALERT {model}{score_part}",
            )
        # quarantine
        sig = str(md.get("signer_id", "unsigned"))
        verified = bool(md.get("verified", False))
        action = "active" if verified else "pending"
        summary = str(md.get("summary", "")) or f"{sig} → {action}"
        return cls(
            event_id=ev.event_id,
            timestamp_utc=ev.timestamp_utc,
            kind="quarantine",
            summary=f"[{action}] {summary}",
        )


def render_panel(entries: list[CogEntry], *, max_lines: int = 12) -> str:
    """Pure rendering — UI 非依存テスト容易."""
    if not entries:
        return "(no cognitive mesh events yet)"
    # 新しい順
    items = sorted(entries, key=lambda e: e.timestamp_utc, reverse=True)[:max_lines]
    glyph = {"proactive": "🗣 ", "risk": "⚠ ", "quarantine": "📦"}
    lines = ["Cognitive Mesh"]
    lines.append("─" * 60)
    for e in items:
        # emoji を読み手任意で抑制したい場合用に kind 名も併記
        g = glyph.get(e.kind, "?")
        lines.append(f"{g} {e.kind:<11} {e.timestamp_utc}  {e.summary}")
    return "\n".join(lines)


class CognitiveMeshPanel(Static, View):
    """Read-only TUI panel for cog mesh events."""

    name = "cognitive_mesh_panel"
    title = "Cognitive Mesh"

    DEFAULT_CSS = """
    CognitiveMeshPanel {
        height: 1fr;
        border: round $secondary;
        padding: 0 1;
    }
    """

    def __init__(self, *, history: int = 64, max_lines: int = 12) -> None:
        super().__init__("(no cognitive mesh events yet)")
        self._history: deque[CogEntry] = deque(maxlen=max(2, int(history)))
        self._seen_ids: set[str] = set()
        self._max_lines = max_lines
        self.border_title = "Cognitive Mesh"
        self.border_subtitle = ""

    def feed_events(self, events: list[TimelineEvent]) -> int:
        added = 0
        for ev in events:
            if ev.event_id and ev.event_id in self._seen_ids:
                continue
            entry = CogEntry.from_event(ev)
            if entry is None:
                continue
            if entry.event_id:
                self._seen_ids.add(entry.event_id)
            self._history.append(entry)
            added += 1
        if added > 0:
            self._render()
        return added

    def clear(self) -> None:
        self._history.clear()
        self._seen_ids.clear()
        self._render()

    def entry_count(self) -> int:
        return len(self._history)

    def latest(self) -> CogEntry | None:
        return self._history[-1] if self._history else None

    def _render(self) -> None:
        text = render_panel(list(self._history), max_lines=self._max_lines)
        self.update(text)


# ---------------------------------------------------------------------------
# Mock fixtures for offline demo / CI
# ---------------------------------------------------------------------------


def make_mock_cog_events(n: int = 3) -> list[TimelineEvent]:
    """Generate ``n`` synthetic cog events (3 kinds round-robin)."""
    events: list[TimelineEvent] = []
    for i in range(n):
        kind = ("cog_proactive_utterance", "cog_risk_alert", "cog_quarantine_pending")[i % 3]
        md: dict[str, object]
        if kind == "cog_proactive_utterance":
            md = {
                "content": f"自動発話 #{i}",
                "mode": "timer",
                "gift_value": 0.72 + (i * 0.01),
            }
        elif kind == "cog_risk_alert":
            md = {"model_name": "critical_logs", "score": 0.85 - (i * 0.02)}
        else:
            md = {
                "signer_id": "trusted-rss" if i % 2 == 0 else "unsigned",
                "verified": i % 2 == 0,
                "summary": f"news entry #{i}",
            }
        events.append(
            TimelineEvent(
                event_id=f"cog-mock-{i:03d}",
                event_type=kind,
                timestamp_utc=f"2026-05-19T10:0{i % 10}:00+09:00",
                metadata=md,
            )
        )
    return events


__all__ = [
    "COG_EVENT_TYPES",
    "CogEntry",
    "CogKind",
    "CognitiveMeshPanel",
    "make_mock_cog_events",
    "render_panel",
]
