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

## v0.2.x — シナリオ磨き（順次マイナーリリース）

**ゴール:** 既存 9 シナリオ (cost / chat / bench / drift / mcp_call / vision / pointcloud / mindmap +
旧 7 種) を 1 個ずつ TUI 実機検証で品質を上げる。新規シナリオを足すより、既に量産した
ものを「Sensor / SPC / Audit / Narration の 4 ペイン全部に意味のある情報が流れる」状態に
仕上げてから次に進む。

### 入る機能

- [ ] `scripts/snapshot_scenario.py` で en/ja の SVG を全シナリオ分取る
- [ ] cost に `daily_cost_usd` の SENSOR 追加 — **完了**（v0.2.x branch ローカル）
- [ ] chat に「累積トークン数」or「ターン経過」の SENSOR 追加
- [ ] bench に「latency / cost / quality」の 3 系列 SENSOR 追加
- [ ] mcp_call に「tool latency」の SENSOR 追加
- [ ] mindmap に「tree breadth」の SENSOR 追加 (alarm と連動)
- [ ] narration pane の pause/scroll 挙動を確認（中間ビートが流れて消えないか）
- [ ] shared util: ASCII-art 描画ヘルパ・累積カウンタ Sensor mixin を base.py に切り出す
- [ ] LaTeX/数式シナリオ (REQUIREMENTS F10) — Unicode 変換 + Qt mathtext viewer
- [ ] **学生向け入門シナリオ群** (REQUIREMENTS F11) — coin_toss / dice_roll / number_guess /
      weather / game_of_life / pomodoro / prime_sieve から 2-3 個を選んで実装。
      LLMesh 機能学習の前段としても使える「動かして遊べる」レベル。
      - [x] coin_toss (v0.2.x ローカル) — pane title override 機構も同時導入

- [x] **対局シナリオ `shogi` MVP1** (REQUIREMENTS F12) — scripted 20 半手 +
      漢字駒（先手玉 / 後手王）+ `[bright_red]` 後手色 + 持ち駒上下表示 +
      `▲７六歩 (2.4秒)` 形式の棋譜 + 半手ごと盤面更新 + 自動 JSONL ログ
      (`out/shogi/shogi-<ts>.jsonl`) + Reset で対局やり直し（ログも作り直し）+
      先後 LLM 名表示 + ユニットテスト (`tests/test_shogi.py`)。

- [x] **対局シナリオ `shogi` MVP2a** — *最小の実対局ループ*。**v0.3.0a1 完了**
      - [x] `[shogi]` extras: `python-shogi` (GPL-3.0、本体 MIT は extras 経由で隔離)
      - [x] 合法手チェッカ統合 — 駒の動き / 二歩 / 王手放置 / 行き所のない駒 / 持ち駒打ち / 打ち歩詰め (`Engine.push_usi`、`is_legal` に委譲)
      - [x] LLM プロバイダ抽象化 (`llove/shogi/players/`): `mock` (script/illegal/resign の 3 variant)
      - [ ] LLM プロバイダ実装 (MVP2b へ移行): `anthropic` / `ollama` / `llmesh:peer`
      - [x] CLI: `llove play shogi --sente <provider:model> --gote <provider:model>` (mock 同士は動作)
      - [x] ゲームループ — 違法手 3 回で投了、詰み / 投了 / 千日手 / max_ply で終局 (`run_game`)
      - [x] **Per-move Ed25519 署名は仕様** — canonical = `"{ply}|{side}|{usi}|{sfen_after}"` (llmesh identity 利用)
      - [x] 既存 `--log` JSONL に対局全体を継続記録 + `--no-tui --stream` で stdout JSONL 出力可
      - [ ] system prompt を locale 別 TOML に外出し (MVP2b で実装)

- [ ] **対局シナリオ `shogi` MVP2b** — *プロバイダ拡張 + メッシュ越し対局 + バッチ評価*。
      - [ ] `anthropic` / `ollama` / `openai` / `llamacpp` / `lmstudio` プロバイダ
      - [ ] **`llmesh:peer:<NodeID>` プロバイダ — first-class 対応** (llmesh-mcp v3.2 に `game.think` 汎用 MCP ツール追加)
      - [ ] バッチ実行 `--games N` で AvsB の勝率比較
      - [ ] KIF 形式 export `out/shogi/<ts>.kif`（標準棋譜フォーマット）
      - [ ] system prompt を locale 別 TOML に外出し
      - [ ] HMAC-chain スタイル署名 (オプション、MVP2a の独立署名から拡張)

- [ ] **対局シナリオ `shogi` MVP3** — *人間対戦モード*。
      - [ ] `human` プロバイダ（キーボード入力、合法手 highlight）
      - [ ] 投了 / 待った / 局面コピー操作
      - [ ] ボタン拡張（投了・次手）

- [ ] **対局シナリオ `shogi` MVP4** — *Qt 盤面ビューア*。
      - [ ] `tools/qt_viewer/shogi_viewer.py` で本物の駒画像表示
      - [ ] 後手駒は 180° 回転表示
      - [ ] 棋譜送り戻し UI、SFEN コピー

- [ ] **ウェブカメラ + 画像 LLM デモ** (REQUIREMENTS F13) — `face_landmarks`。
      `[webcam]` extras (opencv-python + mediapipe)。TUI で ASCII 顔 + landmark、
      Qt viewer で実画像 + overlay。`gesture` / `pose` / `vlm_caption` も同じ
      入力経路で増設可能。

- [ ] **マイク + 音声 LLM デモ** (REQUIREMENTS F14) — 実用 OSS 音声 LLM が
      コミュニティに揃ったタイミングで `voice_transcribe` / `voice_emotion`。
      WhisperX など chunk 対応モデル + sounddevice が安定してきたら着手。

### 受け入れ基準

- 全シナリオで 4 ペイン全部に non-trivial な情報が流れる
- en/ja 両方の SVG snapshot が `docs/snapshots/{en,ja}/<name>-tui.svg` に揃う
- snapshot CI が「SensorStream pane が空白でない」「SPC pane が waiting/alarm のいずれか
  状態を持つ」を assert する

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

## v0.6.0 — Browser-grade Data Display *(F15, 2026-05-09 追加)*

**ゴール:** llove を「ターミナル版 Artifact」から「ターミナル版ブラウザ」に
広げる。HTML ブラウザに匹敵する多モーダル表示力をもたせ、LLMesh のあらゆる
ストリーム（センサー / 画像 / PDF / 表 / 地図 / 3D / 音声 / 動画）を
単一 TUI で見られるようにする。各モーダルはコア依存を増やさず extras 経由。

### 入る機能 (F15 (a)〜(n) を順に刻む)

- [ ] **画像**: Sixel / Kitty / iTerm2 graphics 自動検出 + ASCII フォールバック
      (`[browser-image]` extras: `pillow`, `term-image` or `chafa` ラッパ)
- [ ] **PDF**: ページレンダリング → Sixel または Qt viewer
      (`[browser-pdf]`: `pypdf`/`pymupdf`)
- [ ] **HTML / Markdown**: Rich ベースの整形表示拡張（NarrationView の派生）
- [ ] **DataTable**: Textual の対話的 DataTable で CSV/JSONL/SQLite を
      ソート・フィルタ可能に
- [ ] **グラフ拡張**: 折れ線・棒・散布・ヒートマップ
      (`[browser-charts]`: `textual-plotext` 既存 + 新拡張)
- [ ] **地理データ**: 緯度経度を terminal-aware ASCII map にプロット
      (`[browser-geo]`: natural earth tile 化、または Qt viewer)
- [ ] **3D**: 既存 `pointcloud` の延長 — 点群・メッシュを Sixel + Qt viewer
- [ ] **音声波形 / spectrogram**: F14 と統合
- [ ] **動画**: フレーム ASCII / Sixel ストリーム（Kitty graphics 推奨）
- [ ] **JSON / YAML**: 折りたたみ可能なツリービュー
- [ ] **新パネル種** `BrowserView`: `image://path`, `pdf://path`,
      `geo://lat,lon`, `web://https://...`, `csv://path` などの URI ルーティング
- [ ] **fail-closed**: viewer 未インストールでも ASCII フォールバック +
      「`pip install llmesh-llove[browser-all]` で X が見えます」案内
- [ ] **llmesh 統合**: `llove view --source llmesh+...` で LLMesh の
      多モーダルストリームを **識別子・署名つき**で見られる
      （Telnet を NetSurf / Firefox に育てるイメージ）

### 受け入れ基準

- 画像をインライン表示できる端末（Wezterm / Kitty / Konsole / iTerm2）
  では実画像が見える。それ以外は ASCII でぼやけた縮小版が見える
- PDF を開くと最初のページがインライン表示される
- `llove view --source geo://35.68,139.76` で東京中心の ASCII 世界地図が
  ピンとともに見える
- 地理 / 画像 / PDF / 動画のいずれも、対応 extras 不在時は **クラッシュせず**
  「ASCII フォールバック + インストール案内」を表示する
- 既存 18 シナリオの動作は不変（regression なし）

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

## v0.7.0 — Multi-Game LLM Arena *(F16, 2026-05-09 追加)*

**ゴール:** shogi (F12) で確立した `Engine + Player + Loop + Provider` 抽象を
`llove/games/<game>/` に汎用化し、chess / go / mahjong / poker /
カードゲーム小品を順次実装。LLM 同士の **多種ゲーム対局アリーナ** に。

### 入る機能（順序）

- [x] `llove/games/base/` 共通骨格 (Engine / Player / Loop / Move /
      Observation / TermReason / GameOutcome / 汎用 Ed25519 署名) — **v0.3.0a1 完了**
- [x] **chess 最小実装** (`llove/games/chess/`、`[chess]` extras: python-chess 14k★ MIT) — **v0.3.0a1 完了**.
      PGN export、Stockfish 評価値オプションは未着手
- [x] **F21 タイピングデモ** (`llove/games/typing/`) — F16 抽象の 1-player 検証 (v0.3.0a1)
- [ ] **F22 LLM テトリスデモ** (`llove/games/tetris/`) — F16 抽象を「リアルタイム 1-player」へ拡張
- [ ] **go** (`[go]` extras: sente / katago bind) — 9x9 → 13x13 → 19x19、SGF export
- [ ] **mahjong** (`[mahjong]` extras: nekobean/mahjong) — Riichi ルール、不完全情報対応 (`Engine.observation_for(player)`)、tenhou.net JSON
- [ ] **poker** (`[poker]` extras: pokerkit / treys) — Texas Hold'em
- [ ] **bridge** (`[bridge]` extras: endplay) — PBN export
- [ ] **カードゲーム小品** (`[card]` extras): こいこい / 大富豪 / 七並べ / 神経衰弱 / speed / blackjack
- [ ] **CLI 統一**: `llove play <game> --player1 ... --player2 ... [--players N]` (shogi 用 `llove play shogi` は実装済、汎用化は go/mahjong 着手時)
- [x] **共通機能 — Ed25519 署名** (per-move、shogi で実装済 / games/base に汎用化済)
- [ ] **共通機能 — 棋譜 export / `--games N` バッチ勝率 / 観戦モード / multi-LLM identity per player**
- [ ] **llmesh peer 越し対局**: `llmesh:peer:<NodeID>` プロバイダで `<game>.think` MCP ツール経由 — llmesh-mcp に v3.2 追加 (shogi MVP2b と同期で実装)

### 参考プロジェクト

- **OpenSpiel** (DeepMind, 50+ ゲーム、Apache-2.0)
- **pgx** (JAX-based RL gym)
- **python-chess** / **python-shogi**

### 受け入れ基準

- 各ゲームが `llove play <game> --player1 mock --player2 mock` で
  完走する（offline、API キー不要）
- 各 extras 不在時は `pip install llmesh-llove[<game>]` 案内のみで、
  他ゲームと shogi は影響を受けない
- 全ゲームで Ed25519 署名付きの棋譜が `out/<game>/` に自動保存

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
