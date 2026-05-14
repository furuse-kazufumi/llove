<!--
title: 「LLM 観測ダッシュボードを TUI で書く」設計の話 ― llove v0.3.0a1 (Textual / layout.toml / F25 連携基盤)
tags: Python,TUI,Textual,LLM,MCP
-->

# 「LLM 観測ダッシュボードを TUI で書く」設計の話 ― llove v0.3.0a1 (Textual / layout.toml / F25 連携基盤)

> A cute, terminal-first **Artifact** for inspecting LLMesh data — `pip install llmesh-llove`

## TL;DR

- **llove** は、LLMesh 系のデータ (SensorEvent / SPC / RAG / Audit / Trace + llive の BWT / route_trace / concept_update) を **1 枚のターミナル** で観測する Textual ベースの TUI。
- レイアウトは **`layout.toml` で完全可変**。SDI/MDI 切替、自由可変ペイン、常駐ロックペイン、マルチディスプレイ。Qt-ADS の TUI 版。
- v0.3.0a1 では **F25 連携基盤 Phase 0/1/2/5a/5b/5c が完結**。`llove ↔ llmesh ↔ llive` を MCP 経由で結ぶ 3 viewer (BWTDashboard / RouteTraceViewer / MemoryLinkVizPanel) と dispatch helper / TimelinePollDriver を備える。
- **716 PASS + 1 skipped / ruff クリーン**、F25 関連だけで 105 テスト。
- リポジトリ: <https://github.com/furuse-kazufumi/llove> / PyPI: `pip install llmesh-llove`

```bash
pip install llmesh-llove
llove demo --scenario llive    # llmesh 経由で llive データを見るシナリオ
```

---

## なぜ TUI なのか

LLM dashboard というと、Streamlit / Grafana / Web UI が定番です。けれど **規制現場・オフライン現場・SRE オペ室** には、共通する別の制約があります。

- ブラウザを置けない、または置きたくない端末がある
- SSH 越しに「いまの状態」を秒で見たい
- グラフィカル UI のラグや過剰アニメーションが、運用判断の邪魔になる
- ログ・トレース・SPC・RAG・監査を **同じ時間軸** で 1 画面に並べたい

`llove` はこれを **1 枚のターミナル** で解く設計選択をしました。SSH 越しでも、現場 PC でも、開発機でも、**同じ画面が出ます**。

---

## 設計の核

### 1. Textual ベース、Rust 加速候補

UI 層は [Textual](https://textual.textualize.io/)。低帯域でも秒単位応答。
Phase 5+ で `llove F18` (Rust 移植) 候補。

### 2. layout.toml で「ユーザが UI を所有する」

```toml
[main]
mode = "mdi"               # sdi / mdi
locked = ["status", "log"] # 常駐ロックペイン

[[panes]]
id = "bwt"
view = "llive.BWTDashboard"
size = "40%"
position = "left"

[[panes]]
id = "trace"
view = "llive.RouteTraceViewer"
size = "30%"
position = "center"

[[panes]]
id = "links"
view = "llive.MemoryLinkVizPanel"
size = "30%"
position = "right"
```

レイアウトは git 管理可能。チーム / プロダクト / 個人で別ファイルを持てる。

### 3. ブラウザ並み表示 (F15)

TUI 内で:

- Markdown レンダリング (markdown-it-py + 折り畳み)
- SVG / Mermaid / Graphviz / svgbob / PlantUML → 画像チェイン (chafa / kitty +kitten icat / rsvg-convert / mmdc)
- テーマ切替 (light / dark / high-contrast)
- 折り畳み (line-number ベース永続化)
- code-fence kind ごとの操作 (`:fold by-tag mermaid` 等)

折り畳み状態は line-number ベースで永続化されているので、再描画しても閉じたまま維持されます。

### 4. F25 連携基盤 (本記事の中核)

llove ↔ llmesh ↔ llive を MCP 経由で結ぶ仕組み。**llove は llive を import しない** (単方向依存 llove → llmesh のみ、llive の breaking change は llmesh が吸収)。

```
[llive process]  ─POST /timeline/ingest─►  [llmesh MCP server]  ◄─GET /timeline/recent─  [llove TUI]
                                              │ TimelineStore
                                              └─ event_type で分離
                                                 (bwt_summary / route_trace / concept_update)
```

llmesh 側の **`TimelineStore.record(task_id, node_id, event_type, **metadata)`** という五つ組が llive 3 種データに完全フィット。新 router を作らず、既存 endpoint を流用しています (最小侵襲)。

### 5. 3 viewer + dispatch helper

| モジュール | 役割 |
|---|---|
| `llove/views/llive/bwt_dashboard.py` | BWT (Backward Transfer) 推移可視化、closeness メーター |
| `llove/views/llive/route_trace_viewer.py` | sub-block bar (▓░ 比率) + memory access (read=hits 数+最大スコア / write=surprise) |
| `llove/views/llive/memory_link_panel.py` | concept_id 単位で **latest 保持** (スナップショット意味論) |
| `llove/views/llive/dispatch.py` | `dispatch_events(events, *, bwt, trace, link)` 純粋関数 + `TimelinePollDriver` |

```python
from llove.views.llive import dispatch_events, TimelinePollDriver
from llove.mcp.client import TimelineClient

driver = TimelinePollDriver(
    client=TimelineClient(base_url="http://llmesh:8443"),
    bwt=bwt_dashboard,
    trace=route_trace_viewer,
    link=memory_link_panel,
)
# Textual Timer から
result = driver.poll_once()
status_bar.update(driver.status_line())
```

### 6. リテンション戦略 (viewer 別)

| viewer | 戦略 | 理由 |
|---|---|---|
| BWTDashboard / RouteTraceViewer | event_id 単位で全件保持 | 時系列データ |
| MemoryLinkVizPanel | concept_id 単位で latest 保持 | スナップショット意味論 |

### 7. 依存ゼロ (httpx は extras)

`llove.mcp.client.TimelineClient` は **stdlib `urllib.request` のみ**。httpx は extras に追い出し可能。

### 8. F16 マルチゲーム LLM 対局アリーナ

chess / go / mahjong / poker / connect4… を **同じ抽象** で対局。LLM 戦略の比較研究にも使える。`llmesh シンプル / llove で表示工夫` という設計原則を貫いた最初の例。

---

## 実装で気を付けたこと

### TimelinePollDriver は時間軸を持たない

Textual `Timer` から `poll_once()` を呼ぶ前提。これにより:

- CLI からも sync に動作確認可能
- SSE / WebSocket への切替がローカル変更で済む
- テストで時計を mock する必要がない

### viewer は llive を一切 import しない

llive の dataclass は `from_event(TimelineEvent)` で **llove 側が defensive にパース**。不正フィールドは型違いも含めて全部スキップ。これで:

- llive の breaking change が llove テストを壊さない
- llmesh だけ更新しても画面は出続ける
- mock 駆動先行 (Phase a-e は llmesh/llive 接続なしで完結) ができた

### F25 Phase b-e は mock 駆動で完結

Phase a-e (viewer 全実装 + dispatch + driver) を、llmesh の ingest endpoint や llive の bridge writer が無いまま完成させた。これで llove 開発が他 2 リポジトリの遅延でブロックされない。

---

## 数字で見る現在地 (2026-05-14)

- **v0.3.0a1 (pre-release)** in progress
- **716 PASS + 1 skipped** / ruff クリーン (F25 関連 105 件: client 18 / bwt 25 / trace 26 / link 22 / dispatch 14)
- F15 (ブラウザ並み表示) / F16 (LLM 対局アリーナ) / F17 (window 管理基盤) / F19 (埋込スクリプト + IDE) / F25 (llmesh × llive 連携) を段階実装中
- F25 Phase: 0 (設計凍結) / a (MCP client) / b (BWTDashboard) / c (RouteTraceViewer) / d (MemoryLinkVizPanel) / e (Dispatch + TimelinePollDriver) **完了**
- 残: Phase h (E2E 統合検証 — 3 リポジトリ同時起動) / i (SSE/WebSocket push v2)

---

## ファミリー構成

| プロダクト | 役割 |
|---|---|
| **llove** (本記事) | TUI dashboard / 観測層 |
| **llmesh** | セキュア LLM ハブ (オンプレ MCP サーバ) |
| **llive** | 自己進化型モジュラー記憶 LLM |

3 つを組み合わせると、クラウドを使わず・監査証跡を残し・現場で観測できる **LLM × 産業 IoT** スタックになります。

---

## まとめ

- LLM 観測ダッシュボードは、現場制約 (ブラウザ不可 / SSH 越し / 低帯域) に向けた選択肢として **TUI が再評価されるべき**。
- `layout.toml` 中心の設計で、ユーザが UI を所有できる開発者ツールが書ける。
- F25 のように **3 リポジトリ連携** を設計するときは、依存方向を単方向に固定し、defensive パーサと mock 駆動先行を徹底すると、片方の遅延が全体を止めない。

> GitHub: <https://github.com/furuse-kazufumi/llove>
> PyPI: `pip install llmesh-llove`
