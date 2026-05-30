# F25 — llove ↔ llmesh ↔ llive Tutorial

> **かみ砕いた説明**: このチュートリアルは、llove の F25 連携機能を使って、llive(記憶フレームワーク)が出す観測データを、ターミナル画面の表(TUI)としてリアルタイムに映し出す手順を 3 段階で示すものです。まずはサーバ接続なしの「練習モード」から始め、徐々に実サーバ接続へと進みます。用語の意味は [用語集(GLOSSARY.md)](./GLOSSARY.md) を参照してください。

llove の F25 機能を使って llive 観測データを TUI(Text User Interface、テキストユーザーインターフェース)表示するための実践
ガイド。3 つのモード:

1. **オフライン (mock 駆動)** — llmesh / llive 接続なし
2. **半オンライン (実 llmesh 接続)** — llmesh が稼働、llive はまだ
3. **フルオンライン** — 3 リポジトリ同時稼働 (Phase 6 後)

設計仕様: [`llove_llive_bridge.md`](./llove_llive_bridge.md)
コミット履歴: F25 (a/b/c/d/e) は 2026-05-14 に完了済。

---

## 1. オフライン (mock 駆動)

`llmesh-mcp` / `llmesh-live` のどちらが無くても **viewer をテストできる**。
CI / `llove demo` の主な使い方。

### 単体: BWTDashboard だけ動かす

```python
from llove.views.llive import BWTDashboard
from llove.views.llive.bwt_dashboard import make_mock_bwt_events

dashboard = BWTDashboard()
added = dashboard.feed_events(make_mock_bwt_events(n=5))
print(f"Added {added} runs, total: {dashboard.run_count()}")

# Pure render は widget mount せずに呼べる
from llove.views.llive.bwt_dashboard import render_dashboard, BWTRun
runs = [BWTRun.from_event(ev) for ev in make_mock_bwt_events(n=5)]
runs = [r for r in runs if r is not None]
print(render_dashboard(runs))
```

### 3 viewer 同時 (Dispatch helper)

```python
from llove.views.llive import (
    BWTDashboard, RouteTraceViewer, MemoryLinkVizPanel, dispatch_events,
)
from llove.views.llive.bwt_dashboard import make_mock_bwt_events
from llove.views.llive.route_trace_viewer import make_mock_route_trace_events
from llove.views.llive.memory_link_panel import make_mock_concept_events

bwt = BWTDashboard()
trace = RouteTraceViewer()
link = MemoryLinkVizPanel()

events = (
    make_mock_bwt_events(n=3)
    + make_mock_route_trace_events(n=2)
    + make_mock_concept_events(n=4)
)
result = dispatch_events(events, bwt=bwt, trace=trace, link=link)
print(result.status_line())
# → "bwt+3 trace+2 link+4"
```

---

## 2. 半オンライン (実 llmesh 接続)

llmesh が `http://localhost:8000` で起動済の前提。`/timeline/recent`
endpoint で過去データを取得 (既存機能、F25 e の追加なしで動く)。

### `TimelineClient` で fetch

```python
from llove.mcp import TimelineClient

client = TimelineClient(base_url="http://localhost:8000")
events = client.fetch_recent(limit=20)
print(f"Fetched {len(events)} events. last_error={client.last_error}")
```

llmesh が応答しない場合は `events = []` + `client.last_error =
"connection_error: ..."` で返る (UI を凍結しない フェイルクローズド(fail-closed))。

### `TimelinePollDriver` でラップ

```python
from llove.mcp import TimelineClient
from llove.views.llive import (
    BWTDashboard, RouteTraceViewer, MemoryLinkVizPanel, TimelinePollDriver,
)

driver = TimelinePollDriver(
    client=TimelineClient(base_url="http://localhost:8000"),
    bwt=BWTDashboard(),
    trace=RouteTraceViewer(),
    link=MemoryLinkVizPanel(),
    limit=50,
    node_id="",          # 空なら全 node 受信
)
result = driver.poll_once()
print(driver.status_line())
```

llive が ingest していない段階では `result.total_added == 0` のまま。
これが Phase 3 (llmesh `/timeline/ingest` endpoint) と Phase 4 (llive
writer) が立つと自動的に動き出す。

---

## 3. Textual TUI に組み込む

`BWTDashboard` 等は `Static + View` 派生なので、`compose()` でそのまま
mount できる。`Timer` で周期 polling:

```python
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from llove.mcp import TimelineClient
from llove.views.llive import (
    BWTDashboard, RouteTraceViewer, MemoryLinkVizPanel, TimelinePollDriver,
)


class LiveDashboardApp(App):
    CSS = """
    BWTDashboard { width: 1fr; }
    RouteTraceViewer { width: 1fr; }
    MemoryLinkVizPanel { width: 1fr; }
    """

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.bwt = BWTDashboard()
        self.trace = RouteTraceViewer()
        self.link = MemoryLinkVizPanel()
        self.driver = TimelinePollDriver(
            client=TimelineClient(base_url=base_url),
            bwt=self.bwt,
            trace=self.trace,
            link=self.link,
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield self.bwt
            with Horizontal():
                yield self.trace
                yield self.link

    def on_mount(self) -> None:
        # 2 秒ごとに polling. Textual の Timer は async でも sync 関数を
        # 呼べるので、driver.poll_once() はそのまま渡せる。
        self.set_interval(2.0, self._tick)

    def _tick(self) -> None:
        # 同期 driver を別 thread に投げる (urllib のブロッキングを避ける)。
        self.run_worker(self._tick_worker, thread=True, exclusive=True)

    def _tick_worker(self) -> None:
        self.driver.poll_once()


if __name__ == "__main__":
    LiveDashboardApp("http://localhost:8000").run()
```

---

## 4. テスト戦略

すべての viewer は **mount 不要** で API レベルテストが書ける:

```python
# transport を注入して実 HTTP を踏まない
from llove.mcp.client import TimelineClient, make_fake_transport

def handler(method, url, headers, body):
    return 200, b'{"count": 0, "events": []}'

client = TimelineClient(
    base_url="http://h:8000",
    transport=make_fake_transport(handler),
)
events = client.fetch_recent()
assert events == []
```

参考実装は:
- `tests/test_mcp_client.py` (18 件)
- `tests/test_llive_bwt_dashboard.py` (25 件)
- `tests/test_llive_route_trace_viewer.py` (26 件)
- `tests/test_llive_memory_link_panel.py` (22 件)
- `tests/test_llive_dispatch.py` (14 件)

---

## 5. トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `client.last_error == "connection_error"` | llmesh server 未起動 | `uvicorn llmesh.mcp.server:app --port 8000` |
| `client.last_error == "http_503"` | `TimelineStore` 未設定 | llmesh の `LLMESH_TIMELINE_DB_PATH` 環境変数を設定 |
| `result.unknown > 0` | llmesh が新 event_type を返した | `KNOWN_EVENT_TYPES` 更新 / 新 viewer 追加検討 |
| `result.unrouted > 0` | viewer = None で受信 | 該当 viewer を `dispatch_events` / driver に渡す |
| `BWTDashboard` が空のまま | event_type 不一致 / metadata 壊れ | `client.fetch_recent()` の生 events を `print` して確認 |

---

## 6. 拡張ポイント

### 新 event_type を追加するには

1. llive 側で event を書く (writer 補完 = Phase g)
2. llove 側で viewer を作る (例: `llove/views/llive/foo_viewer.py`)
   - パターン: BWTDashboard / RouteTraceViewer / MemoryLinkVizPanel いずれかに似せる
   - 防御的パース (`Foo.from_event` で None 返却)、pure render、widget
   - mock fixture (`make_mock_foo_events`)
3. `llove/views/llive/dispatch.py`:
   - `KNOWN_EVENT_TYPES` に追加
   - `dispatch_events` の if/elif に分岐追加 (or 抽象化する)
   - `DispatchResult` に `foo_added` フィールド追加
4. `tests/test_llive_foo_viewer.py` を BWTDashboard 流に書く

### Transport を差し替えるには

`UrllibTransport` の代わりに任意の `MCPTransport` 実装を渡す:

```python
from dataclasses import dataclass

@dataclass
class HttpxTransport:
    """httpx を使いたい場合のラッパー."""
    timeout: float = 5.0

    def request(self, method, url, *, headers=None, body=None):
        import httpx
        try:
            r = httpx.request(method, url, headers=headers, content=body,
                              timeout=self.timeout)
            return r.status_code, r.content
        except httpx.TransportError as exc:
            from llove.mcp.client import MCPClientError
            raise MCPClientError(str(exc)) from exc

client = TimelineClient(
    base_url="http://h:8000",
    transport=HttpxTransport(),
)
```

`mTLS` / `Trusted Peers` 認証も同パターンで `httpx.Client(verify=...)`
等を `HttpxTransport` 内に組み込めば対応可。

---

*Last updated: 2026-05-14*
