# llove Day-0 Gap Analysis (Week 1 Day 1)

> **この文書をひとことで**: llove は、画面いっぱいに文字だけで作った「ようすを見るための画面」です。センサーの数字やログ(機械の作業記録)を、ずらっと表示して眺めるための道具だと思ってください。この文書は、その llove を自分たちの毎日の仕事で実際に使い始める前に、「いまの llove で何ができて、何ができないか」を一つずつ数え上げた点検メモです(自分で作った道具を自分で使って試すことを、ここでは「お試し運用」と呼びます)。点検の結論はこうです — 「llove は、見る・流す・出力するだけの道具で、文字を書きこんだり手で操作したりする機能がない」。むずかしい言葉が出てきたら、各章のはじめで日本語(英語)の形にして言いかえています。まとまった説明は文書のいちばん後ろにある言葉の一覧([GLOSSARY.md](../GLOSSARY.md))を見てください。

> 2026-05-18 朝着手. Week 1 ドッグフーディング(dogfooding)スプリント Day 1 (5/19) 前の予測精度向上が目的.
> 戦略思索 [[project-llove-dogfooding-first]] + [[project-30day-action-plan-2026-05]] 準拠.

## 1. 評価軸

- **可否**: 現状の llove (v0.3.0a1) で典型作業が完結するか
  - ✓ できる
  - △ 一部できる / workaround
  - ✗ できない
- **Engine 抽出度**: その機能 / source を engine 化する難度 (1=容易 〜 5=完全密結合)

## 2. ユーザの 1 日作業 vs llove 現状機能

| # | 作業 | 可否 | llove 現状機能 | 不足 / 課題 |
|---|---|---|---|---|
| A | 戦略思索 (markdown 長文執筆) | **✗** | MarkdownView (表示のみ) | テキスト編集機能 (F19 scripting IDE) 未実装 |
| B | Brief 実行 (llive) | **△** | mcp/ module, F25 Phase 0-g 完了 | F25 Phase h E2E 未着手、Brief を流す pane なし |
| C | git operations (status/commit/diff/log) | **✗** | (なし) | F23 シェル統合 / F24 Claude Code 統合 計画のみ |
| D | memory 整理 (read / write / edit) | **✗** | (なし) | 編集機能未実装、表示も memory 形式に未対応 |
| E | ベンチ実行 (progressive matrix) | **△** | demo --scenario 一部 | 外部 benchmark CLI 呼び出し subprocess 未統合 |
| F | WebSearch / Perplexity 調査 | **✗** | (なし) | HTTP source は browser/ 一部、Perplexity 統合無 |
| G | テスト実行 (pytest) | **✗** | (なし) | subprocess 統合 (F24) 計画のみ |
| H | 記事執筆 (現状 articles_pause) | **✗** | MarkdownView (表示のみ) | A と同じ |
| I | 規制 / 業界調査 (WebSearch + 整理) | **✗** | (なし) | F と同じ + 整理機能無 |
| J | コード実装 (Python/Rust) | **✗** | (なし) | F19 scripting IDE 計画のみ |
| K | docs 更新 (REQ/PROGRESS/CHANGELOG) | **✗** | MarkdownView (表示のみ) | A と同じ |
| L | PR / Issue 管理 (gh) | **✗** | (なし) | gh 統合 未計画 |
| M | LLM 観測 (思考因子/Annotation等) | **✗** | (Research IDE F27 未実装) | llive Annotation を流す pane 不在 |
| N | 将棋 / chess 対局を見る | **✓** | F16 chess + shogi MVP2a | (現状のデモ用途のみ) |
| O | sensor / SPC / audit ログ表示 (llmesh) | **✓** | F2 sensor_stream / spc_chart / audit_log | (LLMesh 接続が前提) |
| P | LLMesh データを 1 ファイル HTML 化 | **✓** | F3 `llove export --html` | |
| Q | typing / tetris demo | **△** | F21 typing 実装、F22 tetris 計画 | (デモ用途のみ) |

### サマリ

- **可否**: ✓ 4 件 (24%) / △ 3 件 (18%) / ✗ 10 件 (59%)
- **「将棋を少し見た程度」が実態** = 17 作業中 ✓ なのは demo + ゲーム + 観測のみ
- **編集 / 操作 / 統合機能が全部不在** = 玩具止まりの構造的原因

## 3. llove の構造 — 「観測専用」設計の証拠

```
llove/
├── views/              # 14 種の pane (sensor / spc / audit / markdown / mermaid / svg / timeline 等)
├── widgets/, window/   # TUI 描画専用
├── sources/            # JSONL / mock / base — read-only data source
├── export/html.py      # HTML 出力 (read-only)
├── games/, shogi/, demo/ # 対局 / シナリオ (デモ用途)
├── mcp/                # F25 連携 (llmesh ↔ llive 経由、Phase 0-g 完了 / h 未着手)
├── browser/            # HTTP source 抽象
├── i18n/               # 多言語化
├── identity.py         # ノード identity
├── events.py           # event bus
└── cli.py              # CLI entry (llove demo / play / export)
```

→ **編集 / 操作系のモジュールが構造的に存在しない**. 全 components が「見る」「流す」
   「出力する」に特化. これは戦略思索 PART 5 で確認した「llove は LLM 観測 / Research
   IDE が本来の役割」と整合する.

## 4. Engine 抽出可能性評価 (TUI(Text User Interface、テキストユーザーインターフェース) 結合度)

| Module | 結合度 (1-5) | engine 化方針 |
|---|---|---|
| sources/ (jsonl/mock/base) | **1** | そのまま engine 化、HTTP API endpoint で expose |
| export/html.py | **1** | engine 化容易、CLI / HTTP 経由で呼べる |
| mcp/ | **2** | F25 統合の延長で engine 化、MCP server として独立 |
| events.py (event bus) | **2** | engine 化容易、SSE / WebSocket で stream |
| identity.py | **1** | engine 化容易 |
| i18n/ | **1** | engine 化容易 |
| browser/ (HTTP source) | **2** | engine 化容易 |
| demo/ (シナリオロジック) | **3** | シナリオデータ部分は抽出可、TUI 連携部分は残る |
| games/, shogi/ | **4** | ゲームロジック抽出可、TUI 表示は残る |
| views/ (14 種 pane) | **4-5** | Textual と密結合、「データ準備 / 状態管理」と「描画」に分離が必要 |
| widgets/, window/ | **5** | TUI 完全専用、engine 抽出対象外 |
| term/ | **5** | TUI 完全専用 |
| cli.py | **3** | CLI parsing は engine 側に移植可 |

### Engine 抽出 Phase 1 (Week 2) で着手すべき範囲

**engine 化容易な layer (結合度 1-2)**:
- sources/ + export/ + mcp/ + events/ + identity/ + i18n/ + browser/
- これらだけで「データ取得 → 加工 → HTML 出力」の core path が engine として独立する
- Research IDE F27 の 5 pane を engine 経由で動かせる土台になる

**Phase 1 で残置 (結合度 3-5)**:
- views/, widgets/, window/, term/, games/, shogi/
- これらは TUI 専用として残し、Phase 2 でビュー(view)層と分離を検討

## 5. Week 1 ドッグフーディング(dogfooding) スプリントの予測

### ✓ できる作業 (4 件) を中心に dogfooding 開始

- N: 将棋 / chess を見る → 既に実施済
- O: sensor / 統計的工程管理(Statistical Process Control, SPC) / audit ログ表示 → **llmesh 接続環境を作れば dogfooding 開始可**
- P: HTML 出力 → llmesh データを HTML 化して Slack/Issue 貼り付けに使う
- (Q: typing/tetris 観察)

### △ できる作業 (3 件) を Day 1 で詰める

- B: Brief 実行 → F25 Phase h E2E 着手で Day 1 中に動かせる可能性
- E: ベンチ実行 → subprocess 経由で外部 benchmark を呼ぶスパイク
- Q: typing/tetris のシナリオ追加

### ✗ できない作業 (10 件) — Week 1-4 で順次対応

- A/H/K (markdown 編集): F19 scripting IDE を Phase 2 以降で着手
- C (git): F23 シェル統合を Phase 2 以降で着手
- D (memory): F19 + memory 専用ビュー(view)を Phase 3 で着手
- F/I (WebSearch/規制調査): HTTP source 経由で実現可能だが優先度低
- G (pytest): F24 Claude Code 統合の一部
- J (コード実装): F19 scripting IDE
- L (gh): F24 / 別 plugin
- M (LLM 観測): **F27 Research IDE が直接の答え** (Week 3 着手)

## 6. Day 1 (5/19) 起床後の最初 30 分プラン

1. **llmesh + llive 起動** (現状の F25 Phase 0-g セットアップで)
   - llove に llmesh 接続情報を渡し、sensor / audit / spc 観測 pane を生で動かす
   - 観測 pane が動かなければ最初の bug
2. **`llove demo --scenario <main>` を 30 秒走らせる**
   - メインシナリオで 4 pane (sensor / spc / audit / narration) が全部埋まるか確認
   - 1 つでも空白 pane があれば F9 違反として bug 記録
3. **`llove export --html out.html` を生 llmesh データで動かす**
   - HTML が壊れずに Slack/Issue 貼れる品質か確認
4. **発見した詰まりを全部 `docs/audits/dogfooding-day1.md` に記録**

## 7. Day 0 で得た重要 insight

1. **llove の構造的本質は「観測専用」** — views/ 14 種が全部 read-only。編集 / 操作系は
   そもそも実装されていない。これは pivot 議論の前提条件
2. **「将棋を少し見た程度」が実態** — 17 作業中 ✓ なのは demo + ゲーム + 観測のみで、
   日常作業の主流 (markdown 編集 / git / memory / WebSearch / テスト / コード実装 /
   gh) が一切できない構造
3. **Engine 抽出 Phase 1 (Week 2) で sources + export + mcp + events を engine 化**
   すれば、F27 Research IDE (Week 3) の土台が整う. views / widgets / window 等の
   TUI 専用 layer は Phase 1 では触らない判断
4. **ドッグフーディング(dogfooding)は「観測 + デモ + HTML 出力」だけで開始可能** — 完全カバーを目指す
   と着手が遅れる. まず可能な領域で実機運用を回し、不足を Week 2-4 で埋める
5. **編集機能不在は F19 scripting IDE (Editor/IDE Mode) で解決する設計** だが、これは
   Phase 2-3 (1-3 か月後) の領域. Week 1 内では届かない. dogfooding スプリントは
   「観測者として llmesh / llive 出力を毎日見る」運用に絞る

## 8. 撤退条件 (Day 1 で確認)

- Day 1 で観測 pane (sensor/spc/audit) が動かなければ → F25 Phase h E2E が Day 2-7 の
  最優先タスクに昇格
- Day 1 で 4 pane の 1 つでも空白なら → F9 違反、品質スプリントを最優先化
- Day 3 までに ドッグフーディング(dogfooding) が定着しなければ → F27 / Engine 抽出着手を 1 週間延期、
  品質スプリント長期化 ([[project-llove-dogfooding-first]] R9 適用)

---

## 改訂履歴

- 2026-05-18 — v1 作成 (Day 0, 10-20 分作業)

## 関連 memory / docs

- [[project-llove-dogfooding-first]] — 1 週間 dogfooding スプリント計画
- [[project-llove-research-ide-pivot]] — F27 Research IDE Mode
- [[project-llove-editor-extensions]] — 多 UI 戦略
- [[project-30day-action-plan-2026-05]] — Week 1-4 全体計画
- `D:/projects/audit/STRATEGY_EAR_LOCAL_LLM_2026-05-17_PART5_ENGINE.md` — Engine 抽出
  protocol design (Phase 1 範囲の根拠)
