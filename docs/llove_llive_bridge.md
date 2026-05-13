# llove ↔ llmesh (MCP) ↔ llive 連携 仕様 v1

**Status:** Design draft frozen 2026-05-14. 実装は段階着手。

llmesh の既存 MCP サーバー + `TimelineStore` を中継 hub として、llive の
観測 JSONL データを llove の TUI viewer に流す。新規ルーターは追加せず、
**`/timeline/ingest` という ingest endpoint 1 つを llmesh に足すだけ**で
連携が成立する設計を採用する (B 案、2026-05-14 確定)。

---

## アーキテクチャ

```
[llive process]                [llmesh MCP server]              [llove TUI]
   │                              │                                │
   │  POST /timeline/ingest       │                                │
   │  {task_id, node_id, event_   │  TimelineStore.record(...)     │
   │   type, metadata}            │  ──────────────────────────►   │
   │  ─────────────────────────► │                                │
   │                              │                                │
   │                              │  GET /timeline/recent          │
   │                              │  ◄─────────────────────────── │
   │                              │   { count, events: [...] }     │
   │                              │  ────────────────────────►    │
   │                              │                                │
                              [SQLite TimelineStore]                │
                              (既存)                                │
```

設計上の責務分担:

- **llive**: 既存 JSONL writer に **optional な MCP push 経路** を追加
  (existing file writer は維持)。`LLIVE_MCP_INGEST_URL` 環境変数で
  ingest 先を指定。
- **llmesh**: 新規 endpoint `POST /timeline/ingest` 1 つ + schema validator。
  既存の `TimelineStore.record()` に流す。Trusted Peers / mTLS 等の既存
  認証層をそのまま継承。
- **llove**: 新規パッケージ `llove/mcp/` (HTTP client) + `llove/views/llive/`
  (3 viewers)。`/timeline/recent?event_type=...&node_id=...` で消費。

---

## TimelineEvent と llive 三種の対応

`TimelineStore` は `(task_id, node_id, event_type, timestamp_utc, metadata)`
の五つ組を持つ汎用イベントログ。llive の 3 種データを以下のようにマッピング:

| llive データ | event_type | task_id | metadata 構造 |
|---|---|---|---|
| route_trace (one request) | `"route_trace"` | request_id (UUID v4) | `{subblocks: [...], memory_accesses: [...], metrics: {...}, container: str}` |
| memory_link (concept upsert) | `"concept_update"` | concept_id を UUID v4 化 (deterministic hash) | `{concept_id, title, page_type, linked_entry_ids, linked_concept_ids, surprise_stats, summary}` |
| bwt (bench run) | `"bwt_summary"` | run_id (UUID v4) | `{task_order, n_tasks, bwt, avg_accuracy, per_task_drop, diagonal, final}` |

`node_id` 規約: llive プロセスは `"llive-<instance-id>"` を名乗る。
複数 llive プロセスや別ソース (llmesh-MQTT 等) との混在を分離する。

`version` フィールドは metadata 内に保持 (`metadata["version"] = 1`)。
将来の schema 進化に備える。

---

## llmesh: `/timeline/ingest` endpoint 仕様

```http
POST /timeline/ingest
Content-Type: application/json
X-Node-Id: llive-instance-1   # 任意、認証 middleware の対象

{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "node_id": "llive-instance-1",
  "event_type": "bwt_summary",
  "timestamp_utc": "2026-05-14T08:30:01Z",
  "metadata": {
    "version": 1,
    "bwt": -0.008,
    "avg_accuracy": 0.78,
    "per_task_drop": {"t1": -0.01, "t2": -0.006},
    "diagonal": {"t1": 0.81},
    "final": {"t1": 0.80},
    "task_order": ["t1", "t2"],
    "n_tasks": 2
  }
}

Response 200:
{"event_id": "...", "stored": true}

Errors:
  400 invalid_json | unknown_event_type
  422 missing_required_field | invalid_uuid | metadata_too_large
  503 timeline_not_configured
```

Validation:
- `task_id`: UUID v4 必須
- `event_type`: `{route_trace, concept_update, bwt_summary}` のいずれか
- `metadata.version`: 1 (現状)
- `metadata` JSON サイズ上限: 64 KB (llmesh 既存 limit に揃える)

Security:
- 既存 auth middleware (Trusted Peers) を継承
- 既存 rate limiter (per node) を継承
- Nonce は不要 (ingest は idempotent でなくてよい — 重複ログは検索側で
  時系列に並べれば問題ない)

---

## llove: 消費側 API

### MCP client (`llove/mcp/client.py`)

```python
class TimelineClient:
    def __init__(self, base_url: str, *, transport: httpx.BaseTransport | None = None): ...
    def fetch_recent(self, *, limit: int = 50, event_type: str = "",
                     node_id: str = "") -> list[TimelineEvent]: ...
    def fetch_task(self, task_id: str) -> TaskTimeline: ...
```

- 同期 API (Textual worker thread から呼ぶ前提)
- httpx 依存性注入 (CI / テスト用に mock transport を差し込める)
- fail-closed: HTTP error → 空 list + audit log

### Viewers (`llove/views/llive/`)

| Viewer | event_type フィルタ | 表示 |
|---|---|---|
| `BWTDashboard` | `bwt_summary` | per_task_drop の bar chart + bwt の時系列 sparkline |
| `RouteTraceViewer` | `route_trace` | subblock 一覧 + duration 内訳 + memory access trace (folding) |
| `MemoryLinkVizPanel` | `concept_update` | concept graph (ASCII tree) + surprise 統計 |

3 viewer とも:
- `TimelineClient` を依存性注入 (constructor で受ける)
- mock list を渡しても動く (CI で `TimelineClient` 不要)
- 周期的 polling (1 秒間隔、Textual `Timer`) で更新。SSE は v2 候補

---

## 実装フェーズ (3 リポジトリ並行可能)

| Phase | リポジトリ | 内容 | 状態 |
|---|---|---|---|
| 0 | llove | 設計メモ凍結 (本ドキュメント) | 2026-05-14 完了 |
| 1 | llove | `llove/mcp/client.py` + tests (mock driven) | 着手 |
| 2 | llove | `BWTDashboard` (mock driven) + tests | 着手 |
| 3 | llmesh | `POST /timeline/ingest` + schema validator + tests | 別セッション |
| 4 | llive | route_trace / memory_link writer 補完 + optional MCP push | 別セッション |
| 5 | llove | `RouteTraceViewer` / `MemoryLinkVizPanel` | 別セッション |
| 6 | E2E | 3 リポジトリ同時起動で BWTDashboard 実データ確認 | 別セッション |

各 Phase は独立して動作可能 (mock driven テストで完結) なので、
Phase 1〜2 だけでも CI green / 機能的に完成する。

---

## 設計判断とその理由

1. **既存 TimelineStore を使う (新 router を作らない)**:
   - すでに `(task_id, node_id, event_type, metadata)` の五つ組形式で、
     llive の 3 種データに完全フィット
   - llove は既に存在する `GET /timeline/recent` `/timeline/task/{id}`
     を叩くだけで読み取れる → llove 側の新規エンドポイント実装ゼロ
   - 既存の auth / rate limit / Trusted Peers を流用できる

2. **ingest endpoint だけ追加 (push 経路)**:
   - 現状 `TimelineStore.record()` は llmesh 内部からしか呼ばれない
   - 外部プロセス (llive) から書き込む経路が無いので 1 つだけ追加
   - 既存の `/tools/{tool_name}` は LLM プロンプト専用 (firewall / privacy
     summarizer) なので、データ ingest には不適

3. **llive を import しない (llove → llmesh の単方向依存)**:
   - llove は llmesh HTTP API のみに依存。llive 仕様は知らない
   - llive の breaking change は llmesh 経由で吸収
   - 将来 llive 以外のソース (llmesh-MQTT / llmesh-SPC) も同じ ingest
     経由で llove に流せる (TimelineStore が node_id で分離)

4. **同期 client + Textual worker thread**:
   - Textual の async event loop で httpx async client を直接動かすと
     UI thread を奪う恐れ
   - 同期 httpx + `run_worker(thread=True)` パターン (既存 ImageRenderPane
     と同じ哲学) で UI を凍結させない

5. **mock 駆動先行開発**:
   - llmesh ingest endpoint が無い段階でも、llove 側で TimelineClient と
     viewer の動作確認は完結する
   - CI は外部依存ゼロで PASS
   - 後段 (Phase 3〜) の実装が遅れても llove 側の進捗は止まらない

---

## Out of scope (v2 候補)

- SSE / WebSocket による push 通知 (現状は polling)
- llmesh stdio_server.py 経由の MCP プロトコル正式対応 (Anthropic 仕様)
- 複数 llmesh node のフェイルオーバ (リーダー選出 / replica)
- TimelineStore 圧縮 (古い event の archive)

---

*Frozen: 2026-05-14*
