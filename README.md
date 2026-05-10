# 💗 llove

[![CI](https://github.com/furuse-kazufumi/llove/actions/workflows/ci.yml/badge.svg)](https://github.com/furuse-kazufumi/llove/actions/workflows/ci.yml)
[![CodeQL](https://github.com/furuse-kazufumi/llove/actions/workflows/codeql.yml/badge.svg)](https://github.com/furuse-kazufumi/llove/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/furuse-kazufumi/llove/branch/main/graph/badge.svg)](https://codecov.io/gh/furuse-kazufumi/llove)
[![PyPI](https://img.shields.io/pypi/v/llmesh-llove.svg)](https://pypi.org/project/llmesh-llove/)
[![Python](https://img.shields.io/pypi/pyversions/llmesh-llove.svg)](https://pypi.org/project/llmesh-llove/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

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

> **v0.3.0a1 (pre-release):** llmesh ノード identity を全デモの先頭で
> AUDIT に流す統合 / shogi MVP2a (Ed25519 per-move 署名付きの実対局
> ループ + `llove play shogi`) / F15 ブラウザ並み表示の URI / Camera /
> Viewer 基盤 / F15 (t1) MarkdownView (Rich GFM レンダラ) + (u)
> Foldable Blocks (見出し / コード / 表 / mermaid / svg + プリセット
> 4 種 + TOML 永続化 + ステータスバー連携) / **F15 (t2/t3) Diagram
> auto-render パイプライン: mmdc / rsvg-convert で mermaid / svg を
> SVG/PNG 化し、chafa / viu / timg / kitty / wezterm の最優先ツールに
> 流して `ImageRenderPane` 上に画像表示。Textual `run_worker(thread=True)`
> で UI 凍結を回避、3 段 fallback で fail-closed。** /
> F16 chess (`[chess]` extras) / F21 タイピングデモ (8 ジャンル辞書) /
> F17 WindowManager 最小骨組み (Free/Locked Container + IconSet 3 段 +
> layout.toml). 全 **442 件 PASS** + 3 skipped, ruff クリーン.
> 詳細は [CHANGELOG.md](CHANGELOG.md) と [ROADMAP.md](ROADMAP.md) を参照.

```bash
pip install llmesh-llove        # PyPI 配布名 (llmesh-mcp と統一)
llove demo                       # 30 秒で動くフル機能デモ
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
llove --lang ja demo --scenario scada   # UI を日本語で（v0.2.0+）
```

### 多言語化 (i18n)

UI は `--lang en` / `--lang ja` で切り替えられます（環境変数 `LLOVE_LANG=ja`、システムロケール自動検出にも対応）。新しい言語を足すには `llove/i18n/locales/<lang>.toml` を 1 つ追加するだけ。詳細は [`docs/i18n.md`](docs/i18n.md)。

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
