# llove — Roadmap

> **「30 秒で動くターミナル Artifact」** から **「OSS / プロダクトで使えるダッシュボード基盤」** まで、段階的に育てる。

---

## 全体方針

1. **v0.1 を素早く出す**（合成データだけで動く、`pip install llove` → `llove demo` で見える）
2. **v0.2 で実 LLMesh と繋ぐ**（オプショナル依存）
3. **v0.3 で HTML エクスポート + 共有体験**を完成（Claude Artifacts 相当の単一 HTML）
4. **v0.4 でデータソース拡張**（SQLite / Phoenix Trace / CSV）
5. **v0.5+ でプラグイン化** と コミュニティ受け皿

各バージョンは **2〜4 週** を想定。すべて **fail-closed × OWASP 静的監査クリーン** を維持。

---

## v0.1.0 — Hello, llove!（最初の動く形）

**ゴール:** `pip install llove && llove demo` で **30 秒** で **3 種のビュー** が同時に動くデモが出る。

### 入る機能

- [ ] `llove` CLI コマンド（Click）— `demo / view / export / tail / help`
- [ ] DataSource ABC + `MockSource`（合成 SensorEvent / RAG / Audit）
- [ ] View ABC + 3 ビュー: `sensor_stream`, `spc_chart`, `audit_log`
- [ ] Textual App（3 ペイン分割、キーバインド `q` / `r` / `h`）
- [ ] `llove demo` で 30 秒シナリオ（ノーマル → 異常 → 復帰）
- [ ] tests/ で `MockSource` + ビューの単体テスト
- [ ] devcontainer + docker-compose で 1 発環境
- [ ] GitHub Actions CI（ruff + pytest + bandit）
- [ ] README にスクリーンショット / SVG スナップショット同梱
- [ ] PyPI への公開

### 受け入れ基準

- `pip install llove` → `llove demo` が **エラーなく** 起動して 3 ペインが見える
- `q` で終了、`r` でリロード、`h` でヘルプが出る
- pytest / ruff / bandit が **CI で全部 green**
- リポジトリ README に **動く絵**（GIF / SVG / asciinema）がある

---

## v0.2.0 — Talk to LLMesh

**ゴール:** 本物の LLMesh ノードに接続して **リアルタイムでセンサーと SPC を表示** できる。

### 入る機能

- [ ] `llove.sources.llmesh.LLMeshSource`（extras `[llmesh]`）
- [ ] LLMesh の `SensorEvent` ストリームに接続（async iterator）
- [ ] CUSUM / Hotelling T² の Live 表示（`textual-plotext`）
- [ ] `llove view --source llmesh+modbus://10.0.0.10:502` 風の URI
- [ ] LLMesh `ExplainedCUSUM` の IncidentReport を Markdown ペインで表示
- [ ] LLMesh `AuditTrail` を読む `AuditFileSource`
- [ ] Live ⇄ Replay の切り替え（`<space>` キー）
- [ ] テスト: モック LLMesh で接続 / フェイルオーバー / タイムアウト

### 受け入れ基準

- ローカル `ollama` + LLMesh PoC ノードを立てて **5 分以内に** 自分のセンサーが見られる
- LLMesh が落ちたら **空ペインに「offline」表示**（プログラムは死なない）

---

## v0.3.0 — Share with llove (HTML Export)

**ゴール:** 1 ファイル HTML を吐いて Slack / Issue にそのまま貼れる。

### 入る機能

- [ ] `llove export <source> --html out.html` コマンド
- [ ] スナップショット時点のデータを **静的 HTML（CSS + 軽 JS）** に焼く
- [ ] read-only モード（Replay 可、書き込み不可）
- [ ] 「Made with llove」フッター + リポジトリリンク
- [ ] CDN 不要 / 単一ファイル / オフラインで開ける（base64 埋め込み）
- [ ] Time-range スライダー（HTML 側でも動く）
- [ ] テスト: HTML がブラウザで開ける（HTML パース + 期待要素チェック）

### 受け入れ基準

- 出力 HTML が **`file://` で開いて** ペインが見える
- ファイルサイズ ≤ 1 MB（典型的な 1 時間分のデータで）
- Slack / Discord / Twitter にリンクとして貼ったときカード表示で意味が伝わる

---

## v0.4.0 — Many Sources, One llove

**ゴール:** LLMesh 以外のデータソースも見られる。

### 入る機能

- [ ] `llove.sources.sqlite` — 任意の SQLite を `--table` 指定で読む
- [ ] `llove.sources.jsonl` — JSON Lines を tail / replay
- [ ] `llove.sources.csv` — シンプル CSV
- [ ] `llove.sources.phoenix` — Phoenix Trace（OpenInference）
- [ ] `llove tail <file.jsonl> --view sensor_stream` の自動推論（Pydantic で型を当てに行く）
- [ ] スキーマレス・ヒューリスティクスで「だいたい見える」体験

### 受け入れ基準

- 任意の SQLite ファイルを与えると **テーブル一覧が出てペインに表示できる**
- Phoenix のトレース DB を読み込むと **Trace timeline ビュー** が即出る

---

## v0.5.0 — Plugin Architecture

**ゴール:** 他者が `llove-foo` を `pip install` するだけで View や Source が増える。

### 入る機能

- [ ] entry_points: `llove.sources` / `llove.views`
- [ ] サードパーティ向け開発ガイド（`docs/plugins.md`）
- [ ] 公式サンプル: `llove-grafana`（Grafana JSON ダッシュボードを TUI に翻訳）
- [ ] プラグインの SHA-256 整合性チェック（LLMesh の `plugin-integrity` から流用）
- [ ] テスト: 仮想プラグインの read / load / fail-closed

---

## v1.0.0 — Stable Release

**ゴール:** SemVer 適用、API 公開契約、十分なドキュメント、安定運用。

### 入る機能

- [ ] `__all__` 契約 + `docs/API_STABILITY.md`
- [ ] 公式ドキュメントサイト（mkdocs-material）
- [ ] チュートリアル動画 + 1 ステップ tutorial（asciinema）
- [ ] パフォーマンスベンチ + メモリプロファイル
- [ ] 100k+ event/sec の Live 表示で 60 fps 維持

---

## アイデアバックログ（未確定 / v1 以降）

- llove の Spec を JSON で表現して、TUI / HTML / 静的 SVG いずれにもレンダリングする中間層（Vega-Lite 思想）
- VS Code 拡張: 開いてる JSONL を 1 クリックで `llove tail`
- 統合された LLM チャット（LLMesh のメッシュ越しに、UI からプロンプト送信）
- マスコット llove のアニメーション SVG / Lottie（README 用）
- ダークモード × ライトモード × ハイコントラスト
- 多言語化（英 / 日 / 中）
- カスタムテーマ機能（CSS で自前色配色）

---

## 開発の進め方（規律）

- 全機能変更には **テスト** を伴う（テストが先か後かは問わないが PR にはテストが必要）
- すべての PR は **ruff + pytest + bandit を緑にする**
- `docs/snapshots/` に **そのバージョンで動く絵**を残し、退行を視覚的にも検出
- 主要バージョンの release では **CHANGELOG.md** を更新
- `llove demo` が常に **エラーなく起動できる** ことを CI でも確認（headless）
