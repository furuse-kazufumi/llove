"""F25 (a) — Timeline MCP client.

llmesh の MCP HTTP server (`/timeline/recent`, `/timeline/task/{task_id}`)
を呼ぶ最小限のクライアント。`docs/llove_llive_bridge.md` 仕様 v1 に従う。

設計判断:

- **依存ゼロ**: 外部依存 (httpx 等) を増やさず stdlib `urllib.request` のみ。
- **Transport 注入**: 実 HTTP を踏まずにテスト可能。`MCPTransport` Protocol
  を 1 つ満たせば、fake / record-replay / 本物 urllib 何でも差し替えられる。
- **Fail-closed**: HTTP error / JSON parse error / connection error の全てで
  例外を投げず空 list を返す。UI が外部接続失敗で凍結することを防ぐ。
  代わりに ``last_error: str | None`` で原因を保持する (caller が必要なら
  ステータスバーに表示)。
- **Synchronous API**: Textual の async event loop を奪わないよう、同期で
  実装し caller 側で ``run_worker(thread=True)`` 経由で呼ぶ前提
  (既存 ImageRenderPane と同じ哲学)。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MCPClientError(Exception):
    """Raised by transports that *do* want to fail loudly. Default client
    swallows these into ``last_error`` so the UI keeps running."""


# ---------------------------------------------------------------------------
# Data types — mirror /timeline/recent and /timeline/task response shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimelineEvent:
    """One event from `/timeline/recent`.

    Mirrors the llmesh response shape but tolerant of missing fields so
    forward-compatible (new fields → ignored, missing optional → defaults).
    """

    event_id: str
    task_id: str
    node_id: str
    event_type: str
    timestamp_utc: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskTimeline:
    """Full timeline for one task_id from `/timeline/task/{task_id}`."""

    task_id: str
    node_id: str
    started: str
    terminal: bool
    resumable: bool
    events: tuple[TimelineEvent, ...]


# ---------------------------------------------------------------------------
# Transport — どんな HTTP backend でも plug-in できる
# ---------------------------------------------------------------------------


class MCPTransport(Protocol):
    """Minimal HTTP transport contract.

    `request(method, url, *, headers, body)` -> (status, body_bytes).
    The default ``UrllibTransport`` is one implementation; tests pass a fake.
    """

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, bytes]: ...


@dataclass
class UrllibTransport:
    """stdlib `urllib.request` を用いるデフォルト transport.

    タイムアウト 5 秒、SSL 検証はデフォルト挙動 (Python 標準) に従う。
    """

    timeout: float = 5.0

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(
            url,
            method=method,
            data=body,
            headers=headers or {},
        )
        try:
            with urllib.request.urlopen(  # nosec B310 — caller-supplied URL is host-controlled
                req, timeout=self.timeout
            ) as resp:
                return int(resp.status), resp.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), (exc.read() if exc.fp else b"")
        except (urllib.error.URLError, TimeoutError) as exc:
            raise MCPClientError(f"connection_error: {exc}") from exc


# ---------------------------------------------------------------------------
# TimelineClient — high-level wrapper around the timeline endpoints
# ---------------------------------------------------------------------------


@dataclass
class TimelineClient:
    """Read-only client for llmesh timeline endpoints.

    Construct with a transport (DI) so production runs use ``UrllibTransport``
    and tests pass a fake. The client itself contains no I/O.
    """

    base_url: str
    transport: MCPTransport = field(default_factory=UrllibTransport)
    node_id_header: str = "llove-tui"
    last_error: str | None = None

    # -------- internal helpers --------

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        # base_url の末尾スラッシュ / path の先頭スラッシュ両対応
        base = self.base_url.rstrip("/")
        path = "/" + path.lstrip("/")
        qs = ""
        if params:
            # 空値はクエリに出さない (llmesh はデフォルトで全件返すため)
            filtered = {k: v for k, v in params.items() if v != "" and v is not None}
            if filtered:
                qs = "?" + urllib.parse.urlencode(filtered)
        return f"{base}{path}{qs}"

    def _get_json(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        try:
            status, body = self.transport.request(
                "GET",
                self._url(path, params),
                headers={"X-Node-Id": self.node_id_header},
            )
        except MCPClientError as exc:
            self.last_error = str(exc)
            return None
        if status != 200:
            self.last_error = f"http_{status}"
            return None
        try:
            doc = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            self.last_error = f"json_parse_error: {exc}"
            return None
        if not isinstance(doc, dict):
            self.last_error = f"unexpected_response_type: {type(doc).__name__}"
            return None
        self.last_error = None
        return doc

    @staticmethod
    def _make_event(raw: dict[str, Any]) -> TimelineEvent | None:
        """Lenient parser — missing required fields → skip, never raise."""
        try:
            return TimelineEvent(
                event_id=str(raw.get("event_id", "")),
                task_id=str(raw.get("task_id", "")),
                node_id=str(raw.get("node_id", "")),
                event_type=str(raw.get("event_type", "")),
                timestamp_utc=str(raw.get("timestamp_utc", "")),
                metadata=dict(raw.get("metadata") or {}),
            )
        except (TypeError, ValueError):
            return None

    # -------- public API --------

    def fetch_recent(
        self,
        *,
        limit: int = 50,
        event_type: str = "",
        node_id: str = "",
    ) -> list[TimelineEvent]:
        """`GET /timeline/recent?limit=N&node_id=...` 経由でイベントを取得.

        ``event_type`` は llmesh 側が現状 filter を持たないため、クライアント
        側で受信後にフィルタする。これは llmesh に filter 引数を追加する
        際の前向き互換も担保 (server が filter を実装すれば自動的に server
        側で絞られる)。
        """
        doc = self._get_json(
            "/timeline/recent",
            {"limit": int(limit), "node_id": node_id},
        )
        if doc is None:
            return []
        raw_events = doc.get("events") or []
        if not isinstance(raw_events, list):
            self.last_error = "events_not_list"
            return []
        events: list[TimelineEvent] = []
        for r in raw_events:
            if not isinstance(r, dict):
                continue
            ev = self._make_event(r)
            if ev is None:
                continue
            if event_type and ev.event_type != event_type:
                continue
            events.append(ev)
        return events

    def fetch_task(self, task_id: str) -> TaskTimeline | None:
        """`GET /timeline/task/{task_id}` 経由で 1 タスクの全 event を取得.

        404 は ``last_error="http_404"`` を残して ``None`` を返す。
        """
        doc = self._get_json(f"/timeline/task/{task_id}")
        if doc is None:
            return None
        raw_events = doc.get("events") or []
        if not isinstance(raw_events, list):
            self.last_error = "events_not_list"
            return None
        events: list[TimelineEvent] = []
        for r in raw_events:
            if not isinstance(r, dict):
                continue
            # /timeline/task の event row は event_type / event_id /
            # timestamp_utc / delta_ms / metadata の形。task_id / node_id は
            # 上位 doc にあるので個別 event には埋め直しが必要。
            enriched = dict(r)
            enriched["task_id"] = str(doc.get("task_id", task_id))
            enriched["node_id"] = str(doc.get("node_id", ""))
            ev = self._make_event(enriched)
            if ev is None:
                continue
            events.append(ev)
        return TaskTimeline(
            task_id=str(doc.get("task_id", task_id)),
            node_id=str(doc.get("node_id", "")),
            started=str(doc.get("started", "")),
            terminal=bool(doc.get("terminal", False)),
            resumable=bool(doc.get("resumable", False)),
            events=tuple(events),
        )


# ---------------------------------------------------------------------------
# Helpers for tests — fake transport factory
# ---------------------------------------------------------------------------


def make_fake_transport(
    handler: Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]],
) -> MCPTransport:
    """Build a transport that delegates to ``handler(method, url, headers, body)``.

    Tests use this to assert request shape and supply canned responses
    without spinning up an HTTP server.
    """

    @dataclass
    class _FakeTransport:
        def request(
            self,
            method: str,
            url: str,
            *,
            headers: dict[str, str] | None = None,
            body: bytes | None = None,
        ) -> tuple[int, bytes]:
            return handler(method, url, headers or {}, body)

    return _FakeTransport()


__all__ = [
    "MCPClientError",
    "MCPTransport",
    "TaskTimeline",
    "TimelineClient",
    "TimelineEvent",
    "UrllibTransport",
    "make_fake_transport",
]
