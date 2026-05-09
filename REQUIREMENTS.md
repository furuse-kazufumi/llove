# llove — Requirements

> A cute, terminal-first **Artifact** for inspecting LLMesh data with **llove**.
> `pip install llove`

---

## 1. なぜ作るか（背景）

LLMesh は産業 IoT・SCADA・LLM 連携・RAG・Audit・Trace と **多種多様なストリーム**を一つのフレームワークに収めた。だが現状その **可視性 (visibility) は CLI ログ + JSON ダンプ** に依存しており、

- 現場で **「いま何が起きているか」を一目で把握する手段がない**
- **ノンエンジニア**（SRE / 制御技術者 / プロダクト責任者）が状況を確認できない
- **デモ・教育・PoC** で「動くこと」を見せるたびに毎回スクリプトを書き直している

Claude HTML Artifacts のように、**自己完結・共有可能・インタラクティブな単一ビュー** を **ターミナル** で実現できれば、LLMesh の作業効率と普及率が一段上がる。`llove` はその「ターミナル版 Artifact」。

---

## 2. 何を作るか（ゴール）

**ひとことで言うと:** LLMesh のデータをかわいく見せる TUI ダッシュボード CLI。

### 2.1 中核機能

| # | 機能 | 受け入れ基準 |
|---:|---|---|
| F1 | `llove demo` で 30 秒でフル機能のデモが立ち上がる | 合成 SensorEvent / SPC alarm / RAG hit / Audit log が同時に流れる |
| F2 | LLMesh データを TUI で表示（リアルタイム + 履歴） | SensorEvent ストリーム、CUSUM / T² チャート、Audit log、RAG hit、Trace timeline |
| F3 | `llove export <source> --html out.html` で 1 ファイル HTML を吐ける | ブラウザで開けば同等の見た目（read-only スナップショット）|
| F4 | LLMesh 不在でも動く（オフラインで遊べる） | `pip install llove` のみ、外部 daemon 不要、合成データで完結 |
| F5 | 別データソース（JSON Lines / SQLite / Phoenix Trace）も読める | プラグイン的に Source 追加可能、`pip install llove` だけで JSON / SQLite は読める |
| F6 | キーボード駆動 + マウスもクリックできる | Textual の標準サポート、Vim 風キーバインドも提供 |
| F7 | デモ環境 / テスト環境 / 開発環境を同梱 | demo コマンド + Mock LLMesh + devcontainer + docker-compose + GitHub プレビュー用スケッチ |

### 2.2 非機能要件

- **CLI 起動 → 最初の画面が見えるまで 1 秒以内**（合成データ時）
- **依存ゼロで動く本体**（Textual / Rich / pydantic / click 以外は extras）
- **Python 3.11 / 3.12 サポート、Linux / macOS / Windows 全対応**
- **fail-closed**: データソース異常時は空ペインを出して落ちない
- **OWASP 静的監査クリーン**（ruff + bandit を CI に組み込む）
- **テストカバレッジ 80%+**（`--cov-fail-under=80`）

---

## 3. ターゲットユーザー / ユースケース

| ペルソナ | 一番嬉しい瞬間 |
|---|---|
| 制御技術者 | 現場 PLC の SensorEvent と CUSUM alarm を **1 つの画面で時系列に並べて** 見られる |
| LLMesh 開発者 | `llove tail llmesh-trace.jsonl` で **LLM レスポンスと Audit log を同時にデバッグ** |
| SRE | `llove dashboard --source production.sqlite` で **24h 運用ダッシュボード**を CLI で見続ける |
| プロダクト責任者 | `llove export demo.html --send-link` で **動くデモを Slack に貼る** |
| 講師 / 教育担当 | `llove demo --tutorial` で **学習者がインタラクティブに各機能を触れる** |
| OSS 来訪者 | リポジトリの README を見るだけで **動く絵が出てくる** |

---

## 4. アーキテクチャ概観

```
   ┌──────────────────────────────────────────────────────┐
   │  Data Source Layer (DataSource ABC)                  │
   │   jsonl / sqlite / mock / llmesh / phoenix / custom  │
   └──────────────┬───────────────────────────────────────┘
                  │  yields  Event (pydantic)
                  ▼
   ┌──────────────────────────────────────────────────────┐
   │  View Layer (View ABC)                               │
   │   sensor_stream / spc_chart / audit_log / rag_hits / │
   │   trace_timeline / llm_dialog                        │
   └──────────────┬───────────────────────────────────────┘
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
   ┌──────────┐        ┌──────────────┐
   │  Textual │        │  HTML Export │
   │   App    │        │  (single .html)
   │  (TUI)   │        │  read-only   │
   └──────────┘        └──────────────┘
```

### 4.1 主要コンポーネント

| パッケージ | 役割 |
|---|---|
| `llove.sources` | DataSource ABC + 各種実装（jsonl, sqlite, mock, llmesh-optional） |
| `llove.views` | View ABC + 各種ビュー（sensor_stream, spc_chart, audit_log, rag_hits, trace_timeline） |
| `llove.app` | Textual App（メインウィンドウ、ペイン分割、キーバインド） |
| `llove.export` | `--export-html` 実装（Textual の SVG/HTML エクスポート + 自前合成）|
| `llove.demo` | `llove demo` コマンドの合成データ + シナリオ |
| `llove.cli` | Click ベース CLI（`demo / view / export / tail`） |

---

## 5. 矛盾と TRIZ 観点

| 矛盾（改善したい × 悪化する） | 解決アプローチ | TRIZ 原理 |
|---|---|---|
| **視認性を上げる × CLI で完結させる** | TUI の表現力を上げる（Textual の CSS / Sparkline / 色） + 必要なときだけ HTML エクスポート | #15 動的化, #5 結合 |
| **LLMesh 専用 × 普及スコープを広げる** | DataSource ABC を中間層にして、LLMesh は **オプショナル extras** | #24 仲介, #1 分割 |
| **リアルタイム × 履歴閲覧** | 同じビューで「Live モード」と「Replay モード」を切り替えるトグル | #15 動的化 |
| **コマンドで完結 × インタラクティブに探索** | `llove demo` は引数ゼロで起動、起動後は TUI 内でキーボードで全部できる | #25 自助 |
| **学習コストを下げる × 上級ユーザーの効率を上げる** | キーバインドはデフォルト OK + Vim ライクなオプションキーマップ | #15 動的化 |
| **テスト容易性 × 副作用ある実時系処理** | `MockSource` を入れて時刻 / 並行を抽象化、テストでは決定論的 | #24 仲介, #28 機械的相互作用の置換 |
| **デモを派手に × バイナリ依存を増やさない** | 純 Python + Unicode + Textual のスタイル機能だけで派手に演出 | #25 自助, #2 抽出 |

---

## 6. スコープ外（v1.0 までやらない）

- 書き込み操作（PLC の制御、LLM への能動的プロンプト）— 観察と表示に専念
- マルチユーザ Web ダッシュボード（HTML エクスポートは read-only スナップショットのみ）
- プラグインの公式マーケットプレイス
- データ永続層（時系列 DB の独自実装）— 既存ストア（SQLite/JSONL/Phoenix）を読むだけ

---

## 7. 成功基準

| 指標 | v0.1 目標 | v1.0 目標 |
|---|---|---|
| `llove demo` 起動時間 | ≤ 3 秒 | ≤ 1 秒 |
| サポートビュー種類 | 3 種（SensorEvent, AuditLog, RAG） | 6 種以上 |
| サポートデータソース | 3 種（mock, jsonl, llmesh） | 6 種以上（+ sqlite, phoenix, csv） |
| テストカバレッジ | 70% | 85% |
| GitHub README プレビュー | 静的 SVG | 動く .cast (asciinema) |
| インストールから初動まで | 60 秒 | 30 秒 |
| 月間 GitHub Star | — | 100+ |
| PyPI ダウンロード / 月 | — | 500+ |

---

## 8. 技術スタック

| 層 | 採用技術 | 理由 |
|---|---|---|
| TUI | **Textual** (Python) | CSS スタイル / マウス + キーボード / SVG エクスポート / web レンダリング実験的サポート |
| 描画プリミティブ | **Rich** | Textual の基盤、テーブル・進捗バー・syntax highlight |
| プロット | `textual-plotext` (extras) | ターミナル内グラフ |
| CLI | **Click** | サブコマンド + 自動ヘルプ生成 |
| データバリデーション | **Pydantic v2** | 型安全 + JSON シリアライズ |
| パッケージング | **Hatchling** | 軽量、シンプル、LLMesh と揃える |
| テスト | pytest + pytest-asyncio | Textual の async 起動と相性 |
| 静的解析 | ruff + bandit | LLMesh と揃える |

---

## 9. リスクと緩和策

| リスク | 緩和策 |
|---|---|
| Textual の HTML エクスポートが思ったより貧弱 | 自前で SVG → HTML 変換を別実装、Textual 公式機能はオプション |
| LLMesh のデータ構造変更で壊れる | DataSource を ABC で疎結合、LLMesh への依存は extras + 互換テスト |
| CI で TUI テストが flaky | pilot モード（Textual 公式 test driver）で headless 実行 |
| Windows のターミナルで色化け | Textual は Windows Terminal 公式サポート、cmd.exe は限定対応と明示 |
| マスコット (llove ロゴ) の権利 | 自前 ASCII art / SVG、外部素材は使わない |

---

## 10. 関連プロジェクト

- **LLMesh** — メインのデータソース。`llove[llmesh]` で接続。
- **Textual** — TUI フレームワーク。
- **Phoenix / Arize AX** — Trace の互換読み込みを v0.3 で検討。
- **Claude HTML Artifacts** — 着想元。read-only スナップショット共有のメタファ。
