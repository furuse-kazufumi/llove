# 💗 llove

> A cute, terminal-first **Artifact** for inspecting LLMesh data — with **llove**.

```
       .--.
      /    \         llove
     ( ^  ^ )       "Made with llove"
      \(--)/        ── Watch your LLMesh with llove
      /    \
     ──────
      ll♥ve
```

`llove` は **Claude HTML Artifacts のターミナル版** を目指したダッシュボード CLI です。
**LLMesh の SensorEvent / SPC / RAG / Audit / Trace** を 1 つの TUI（ターミナル UI）で美しく流し、
そのまま **1 ファイル HTML にエクスポート** して Slack / Issue / プレゼンに貼れます。

```bash
pip install llove
llove demo            # 30 秒で動くフル機能デモ
```

---

## なぜ llove か

LLM 時代の運用・研究の現場では、**「いま何が起きているかを 1 画面で見せる」** がいつも難所になります。
LLMesh は産業 IoT・SCADA・RAG・Audit・Trace を統一しましたが、**可視化** はまだ JSON / ログ依存。

`llove` はその穴を埋めます:

1. **30 秒で動く**: `pip install llove && llove demo`
2. **LLMesh と直結**: `llove view --source llmesh+modbus://...`
3. **HTML で共有**: `llove export --html dashboard.html`（**Claude Artifacts 流の単一 HTML**）
4. **オフラインでも動く**: 合成データだけで完結、ネットワーク不要
5. **依存ゼロでも見える**: 本体は Textual + Rich のみ、LLMesh は **オプショナル**

---

## 5 秒で見えるイメージ

```
┌─ llove demo ──────────────────────────────────────────────────────────┐
│ ┌─ SensorEvent stream ─────────┐ ┌─ SPC chart (CUSUM h=5.0) ────────┐ │
│ │ 03:22:08  bearing_temp  68.4 │ │     ╭────────────╮               │ │
│ │ 03:22:09  bearing_temp  69.1 │ │   ──╯           ╰──── h          │ │
│ │ 03:22:10  bearing_temp  70.7 │ │                                  │ │
│ │ 03:22:11  bearing_temp  74.3 │ │                                  │ │
│ │ 03:22:12  bearing_temp  78.9 │ │ ▁▂▃▄▆█ ▶ ALARM 03:22:11Z         │ │
│ └──────────────────────────────┘ └──────────────────────────────────┘ │
│ ┌─ Audit log ──────────────────────────────────────────────────────┐ │
│ │ 03:22:11  firewall.allow   layer=L2  user=ops                    │ │
│ │ 03:22:11  cusum.alarm      sensor=bearing_temp_07  cusum=+9.4    │ │
│ │ 03:22:11  llm.explain      tokens=237  latency=412ms             │ │
│ └──────────────────────────────────────────────────────────────────┘ │
│ q: quit  r: refresh  h: help  space: live/replay  e: export-html      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. インストール

```bash
pip install llove                # 本体（オフラインで動く）
pip install "llove[llmesh]"      # LLMesh と接続
pip install "llove[plots,llmesh]"# textual-plotext のグラフ + LLMesh
```

### 2. 30 秒デモ

```bash
llove demo                       # 合成データでフル機能のデモ
llove demo --tutorial            # 各ビューを順に解説しながら触る
```

### 3. 自分のデータを見る

```bash
llove tail logs/audit.jsonl --view audit_log
llove view --source llmesh+modbus://10.0.0.10:502
llove view --source sqlite:///data.db --table sensors
```

### 4. HTML として共有

```bash
llove export --source mock://demo --html dashboard.html
# → dashboard.html を Slack / Issue / Twitter に貼る
```

---

## 基本コマンド

```bash
llove demo                       # フル機能デモ（合成データ）
llove demo --list                # シナリオ一覧
llove demo --scenario firewall   # 個別シナリオを起動
llove view --source <URI>        # ライブ表示
llove tail <file>                # ファイル末尾を流す
llove export <source> --html <path>   # 1 ファイル HTML
llove --help                     # コマンド一覧
```

### LLMesh 機能カバレッジシナリオ

`llove demo --scenario <name>` で、LLMesh の各機能を **オフライン合成データで** 体験できます。

| name | 何を見せる | カバーする LLMesh 機能 |
|---|---|---|
| `firewall` | 12 prompt が L0/L1/L1.5/L2 で BLOCK / SUMMARIZE / ALLOW される様子 | `PromptFirewall` 4 層 |
| `scada` | センサー drift → CUSUM alarm → LLM の Markdown 説明 | `ExplainedCUSUM` + `LLMExplainer` |
| `multimodal` | 数値センサー × 画像 caption の AND 結合 SPC | `UnifiedSPC` + `VLMFeatureExtractor` |
| `rag` | 同じクエリを 3 ストア（Numpy / SQLite / LSH ANN）で比較 | RAG 3 段ストア |
| `backends` | 同じプロンプトを Ollama / OpenAI / Anthropic に投げた風の比較 | LLM backend ABC |
| `audit` | 5 エントリ追加 → 改ざん → `verify_chain()` が検知 | `AuditTrail` HMAC chain |
| `reliability` | パケット損失下で ACK / RETRANSMIT / TTL 失効を実演 | `MessageAssembler` + `ChunkSender` |

**自分のシナリオを追加するのは超簡単です** — [`docs/contributing-scenarios.md`](docs/contributing-scenarios.md) と [`llove/demo/scenarios/_template.py`](llove/demo/scenarios/_template.py) を参照（5 分でできます）。

### URI スキーム例

| URI | 意味 |
|---|---|
| `mock://demo` | 合成データ |
| `jsonl:///path/to/file.jsonl` | JSON Lines ファイル |
| `sqlite:///data.db?table=events` | SQLite テーブル |
| `llmesh+modbus://10.0.0.10:502` | LLMesh + Modbus アダプタ |
| `llmesh+opcua://opc.tcp://...` | LLMesh + OPC-UA |

---

## 開発環境

### devcontainer / docker-compose で 1 発

```bash
# devcontainer (VS Code) — クローン後 "Reopen in Container"
# または手動で:
docker compose up -d
docker compose exec dev bash
pip install -e ".[dev,all]"
llove demo
```

### ローカルセットアップ

```bash
git clone git@github.com:furuse-kazufumi/llove.git
cd llove
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,all]"
pytest
llove demo
```

---

## アーキテクチャ概観

```
┌────────────────────────────────────────────────────────┐
│  Data Sources (DataSource ABC)                         │
│   mock / jsonl / sqlite / llmesh / phoenix / custom    │
└───────────────┬────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────┐
│  Views (View ABC)                                      │
│   sensor_stream / spc_chart / audit_log /              │
│   rag_hits / trace_timeline                            │
└───────────────┬────────────────────────────────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
   ┌────────┐      ┌──────────────┐
   │ Textual│      │ HTML Export  │
   │  (TUI) │      │ (single .html)│
   └────────┘      └──────────────┘
```

詳細は [`REQUIREMENTS.md`](REQUIREMENTS.md) と [`ROADMAP.md`](ROADMAP.md)。

---

## Docs

- [`REQUIREMENTS.md`](REQUIREMENTS.md) — 要件定義 + TRIZ 観点での矛盾解消
- [`ROADMAP.md`](ROADMAP.md) — v0.1 〜 v1.0 のフェーズ計画
- [`docs/snapshots/`](docs/snapshots/) — 各バージョンで動く絵（GitHub プレビュー）

---

## ライセンス

MIT © 2026 Kazufumi Furuse

---

> **Made with llove** — お気軽に Issue / PR / アイデアをどうぞ.
