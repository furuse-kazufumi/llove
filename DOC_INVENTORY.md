# 📚 ドキュメント目録 — llove

> 自動生成 (`py -3.11 D:\tools\gen_doc_inventory.py <repo>`)。ファイル追加後に再実行で更新。
> **公開/内部フラグはヒューリスティックの仮判定**。公開前に必ず人手で確認すること。

- 総ドキュメント数: **24** （🌐 公開候補 8 / 🔒 内部? 4 / ❓ 要判断 12）
- コーパス・依存・仮想環境・.git は除外。

## 目次

- [(ルート)](#g0) (6)
- [clients/vscode](#g1) (1)
- [docs](#g2) (7)
- [docs/audits](#g3) (1)
- [docs/linkedin](#g4) (3)
- [docs/qiita](#g5) (2)
- [docs/scenarios](#g6) (1)
- [docs/snapshots](#g7) (2)
- [tools/qt_viewer](#g8) (1)

<a id="g0"></a>

## (ルート) (6)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [CHANGELOG.md](CHANGELOG.md) | Changelog | All notable changes to llove are recorded here. | 2026-05-19 | 🌐 公開候補 |
| [CLAUDE.md](CLAUDE.md) | llove — Project Instructions | このファイルは Claude Code 等の AI 実装支援環境に対する指示書。 | 2026-05-23 | 🔒 内部? |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contributing to llove | Thanks for caring enough to help. This document covers the basics. | 2026-05-09 | 🌐 公開候補 |
| [README.md](README.md) | 💗 llove | codecov(https://codecov.io/gh/furuse-kazufumi/llove/branch/main/graph/badge.svg)(https://codecov.io/gh/furuse-kazufumi/llove) | 2026-05-19 | 🌐 公開候補 |
| [REQUIREMENTS.md](REQUIREMENTS.md) | llove — Requirements | LLMesh は産業 IoT・SCADA・LLM 連携・RAG・Audit・Trace と 多種多様なストリームを一つのフレームワークに収めた。だが現状その 可視性 (visibility) は CLI ログ + JSON ダンプ に依存しており、 | 2026-05-10 | ❓ 要判断 |
| [ROADMAP.md](ROADMAP.md) | llove — Roadmap | 1. v0.1 を素早く出す（合成データだけで動く、pip install llove → llove demo で見える） | 2026-05-14 | ❓ 要判断 |

<a id="g1"></a>

## clients/vscode (1)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [README.md](clients/vscode/README.md) | llove VS Code extension (α PoC) | Bring llove's read-only observation surface (engine info / deps audit / | 2026-05-18 | 🌐 公開候補 |

<a id="g2"></a>

## docs (7)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [contributing-scenarios.md](docs/contributing-scenarios.md) | Contributing demo scenarios to llove | llove ships a small set of scenarios under llove/demo/scenarios/. Each one is | 2026-05-09 | ❓ 要判断 |
| [F25_TUTORIAL.md](docs/F25_TUTORIAL.md) | F25 — llove ↔ llmesh ↔ llive Tutorial | llove の F25 機能を使って llive 観測データを TUI 表示するための実践 | 2026-05-14 | ❓ 要判断 |
| [i18n.md](docs/i18n.md) | 多言語化（i18n）— llove | llove はデフォルト英語、日本語同梱で出荷されます。表示文字列はすべて | 2026-05-09 | ❓ 要判断 |
| [index.md](docs/index.md) | FullSense ™ — llove | TUI dashboard / HITL workbench | 2026-05-16 | 🌐 公開候補 |
| [llove_llive_bridge.md](docs/llove_llive_bridge.md) | llove ↔ llmesh (MCP) ↔ llive 連携 仕様 v1 | llmesh の既存 MCP サーバー + TimelineStore を中継 hub として、llive の | 2026-05-14 | ❓ 要判断 |
| [PROGRESS.md](docs/PROGRESS.md) | llove 進捗ログ | llive 側 COG-MESH 全件 (M8.2〜M8.9) 本実装完了を受け、llove F25 bridge | 2026-05-19 | 🔒 内部? |
| [SESSION_SUMMARY.md](docs/SESSION_SUMMARY.md) | Session Summary (auto-generated) | 2912c2e chore(lint): ruff --fix で 26 件の auto-fixable lint debt を解消 | 2026-05-15 | 🔒 内部? |

<a id="g3"></a>

## docs/audits (1)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [dogfooding-day0-gap.md](docs/audits/dogfooding-day0-gap.md) | llove Day-0 Gap Analysis (Week 1 Day 1) | - △ 一部できる / workaround | 2026-05-18 | 🔒 内部? |

<a id="g4"></a>

## docs/linkedin (3)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [post_2026-05-14_overview.en.md](docs/linkedin/post_2026-05-14_overview.en.md) | One terminal pane for "watching LLMs on the shop floor" — llove | LLM dashboards usually mean Streamlit, Grafana, or a fresh web UI. But regulated environments, offline sites, and SRE control rooms share a different set of constraints: | 2026-05-14 | ❓ 要判断 |
| [post_2026-05-14_overview.ja.md](docs/linkedin/post_2026-05-14_overview.ja.md) | ターミナル一枚で「現場の LLM 観測」を ― llove | LLM の dashboard というと、Streamlit / Grafana / Web UI が定番です。けれど 規制現場・オフライン現場・SRE オペ室 には、共通する別の制約があります。 | 2026-05-14 | ❓ 要判断 |
| [post_2026-05-14_overview.zh.md](docs/linkedin/post_2026-05-14_overview.zh.md) | 用一个终端窗格"看现场的 LLM" — llove | 说到 LLM dashboard，大家默认是 Streamlit / Grafana / 全新 Web UI。但在受监管现场、离线现场、SRE 操作间，有另一套共同的约束： | 2026-05-14 | ❓ 要判断 |

<a id="g5"></a>

## docs/qiita (2)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [AUTHORING.md](docs/qiita/AUTHORING.md) | Qiita Authoring Guide | llove / llive / llmesh の Qiita 投稿に 画像 / Mermaid / アニメ画像 を入れる | 2026-05-16 | ❓ 要判断 |
| [qiita-overview.md](docs/qiita/qiita-overview.md) | <!-- | - llove は、LLMesh 系のデータ (SensorEvent / SPC / RAG / Audit / Trace + llive の BWT / routetrace / conceptupdate) を 1 枚のターミナル で観測する Textual ベースの TUI。 | 2026-05-16 | ❓ 要判断 |

<a id="g6"></a>

## docs/scenarios (1)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [index.md](docs/scenarios/index.md) | Demo Scenarios — SVG Gallery | llove は TUI dashboard としての見え方を、各シナリオに SVG スクリーンショット | 2026-05-16 | 🌐 公開候補 |

<a id="g7"></a>

## docs/snapshots (2)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [legend.md](docs/snapshots/legend.md) | llove TUI レイアウト凡例 | 各シナリオの SVG スクリーンショット（-tui.svg）は次の構造を持っています。 | 2026-05-09 | ❓ 要判断 |
| [README.md](docs/snapshots/README.md) | Snapshots | This directory holds previewable artifacts that GitHub renders inline: | 2026-05-09 | 🌐 公開候補 |

<a id="g8"></a>

## tools/qt_viewer (1)

| ファイル | タイトル | 説明 | 更新 | 区分 |
|---|---|---|---|---|
| [README.md](tools/qt_viewer/README.md) | Qt viewers for llove | Standalone Qt-based viewers that render llove vision and pointcloud | 2026-05-09 | 🌐 公開候補 |
