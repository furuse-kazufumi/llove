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
- [ ] **F15 (t) Markdown + SVG + Mermaid 視認性ターミナル** (2026-05-10 追加):
      - GitHub-flavored Markdown 全機能 (見出し / 表 / コードブロック /
        コールアウト / 数式 / フットノート / タスクリスト / 絵文字短縮形)
      - **(t1) MarkdownView 骨組み 完了 (2026-05-10)**: Rich `Markdown`
        ベースの新 View `llove/views/markdown_view.py` を導入。
        NarrationView と同じ feed(event) インタフェース + latest-first 履歴 +
        last_render / last_source スナップショット。GFM 基本構文
        (見出し / 段落 / 箇条書き / 引用 / fenced code / inline / 太字)
        が rich.markdown 経由でレンダリング。i18n は
        `ui.pane.markdown.title` / `ui.pane.markdown.empty` を ja/en に追加。
        テスト 12 件 PASS。コールアウト / 数式 / フットノート / タスクリスト /
        絵文字短縮形は次段階で markdown-it-py プラグイン経由で拡張予定。
      - **MermaidImagePane → ImageRenderPane リネーム完了
        (2026-05-10, F15 (t2/t3))**: `mermaid_pane.py` を削除し
        `image_render_pane.py` を新設。`DiagramRenderResult` Protocol
        (kind / argv / ascii_text 構造的型付け) で pane の入力型を抽象化、
        `MermaidRender` / `SVGRender` 両方が満たす。後続フォーマットも
        Protocol を満たせば pane を触らず対応可能。`make_image_render_callback`
        も同名修正。テスト 21 件を新ファイルに移行 (Protocol 互換テスト
        1 件追加)、フルスイート 442 PASS、新ファイルは ruff クリーン。
      - **MarkdownView を mermaid + svg 統一処理に汎化完了
        (2026-05-10, F15 (t2/t3))**: `mermaid_*` パラメータを `diagram_*`
        に rename し (`diagram_render` / `diagram_renderers: dict[str,
        Callable]` / `diagram_image_callback` / `diagram_cache_dir`)、
        `_expand_mermaid_in` を `_expand_diagram_blocks_in` に汎化。
        kind ∈ {mermaid, svg, ...} に対応する renderer を dict から動的
        ディスパッチする構造に変更。`folding.py` も svg fence の `kind="svg"`
        認識 + prose preset 拡張 + summary marker 追加でフルサポート。
        ユーザは constructor で `{"plantuml": fn, "dot": fn, ...}` 等の
        kind を追加でき、find_code_block_regions が同 kind を返せば
        即座に展開対象になる拡張点を提供。Alpha 段階のため既存
        `mermaid_*` パラメータは互換 alias を残さず非互換 rename。
        既存 9 テスト移行 + svg 統合 5 件 + folding-svg 7 件追加、フル
        スイート 441 PASS、回帰ゼロ。**残課題**: `MermaidImagePane` →
        `ImageRenderPane` リネーム / 実 chafa での E2E。
      - **PlantUML ターミナル表示 (plantuml → SVG → image チェイン) 基盤完了
        (2026-05-14, F15 (t2/t3))**: `llove/views/plantuml_render.py` 新設。
        mermaid_render / svg_render と一対一対応する構造で、PlantUML
        DSL → temp `.puml` → `plantuml -tsvg input.puml` → 同ディレクトリ
        `<stem>.svg` → image catalog 経由で chafa / viu / timg / kitty /
        wezterm の最優先ツールに流す。`PlantUMLRender` (kind/argv/svg_path/
        ascii_text/image_tool) は `DiagramRenderResult` Protocol を満たす
        ので `ImageRenderPane` / `MarkdownView` の `diagram_renderers=
        {"plantuml": render_plantuml}` 1 行で組み込める。plantuml の
        `-o` 仕様 (出力ファイル名を直接指定できず同ディレクトリ命名規則)
        には入力 `.puml` のステムを出力 `.svg` のステムに合わせて吸収。
        subprocess は list-based argv + temp file (shell=True 禁止)。
        テスト 16 件、フルスイート 545 PASS、回帰ゼロ。次段階: folding.py
        で ` ```plantuml ` フェンス → `kind="plantuml"` ラベリング +
        prose preset 連携 + `:fold by-tag plantuml`。Graphviz dot 系は
        同パターンで `dot_render.py` を追加。
      - **SVG ターミナル表示 (rsvg-convert → PNG → image チェイン) 基盤完了
        (2026-05-10, F15 (t2))**: `llove/views/svg_render.py` を新設。
        mermaid_render と一対一対応する構造で、SVG XML → temp `.svg` →
        `rsvg-convert -o output.png input.svg` → image catalog 経由で
        chafa / viu / timg / kitty / wezterm の最優先ツールに流す。
        ASCII fallback は XML 全文ではなく先頭 240 文字の抜粋を出す
        (SVG は人間可読 DSL ではないため)。`SVGRender` は `MermaidRender`
        と同じ shape (kind/argv/ascii_text) なので、`MermaidImagePane`
        にそのまま渡せて duck typing で再利用可能。subprocess は
        list-based argv + temp file 経由でセキュアに固定。テスト 14 件、
        フルスイート 429 PASS。`[browser-svg]` extras + cairosvg バックエンド
        (Python 純粋実装) は今後の追加候補。
        次段階: MarkdownView 内 svg ブロック / `<svg>` タグ自動展開統合
        (現状はモジュール公開のみ。mermaid と同じパターンで足せる)。
      - **MermaidImagePane 非同期化完了 (2026-05-10, F15 (t3))**:
        `set_render_async(mr)` を追加し Textual `run_worker(thread=True,
        exclusive=True)` 経由で subprocess を別スレッドに逃がす。3 段
        fallback (`worker_dispatcher` 注入 → `self.run_worker` → 同期実行)
        で App 未 mount / 例外でも必ず work が走る。worker thread からの
        widget 更新は `app.call_from_thread` 経由 (Textual thread safety
        規約)。`_compute_text` を pure 関数として切り出してテスト容易化。
        `make_mermaid_image_callback` のデフォルトを async に変更
        (旧来挙動は `async_dispatch=False` で復活可能)。テスト 9 件追加、
        フルスイート 415 PASS。**残課題**: 実 chafa での E2E 検証
        (現状は runner / dispatcher 注入の単体テストのみ)。
      - **Textual subprocess worker + MermaidImagePane 完了
        (2026-05-10, F15 (t3))**: 新モジュール `llove/views/mermaid_pane.py` で
        `MermaidImagePane(Static)` widget + `run_image_render` (pure 関数,
        runner 注入可) + `make_mermaid_image_callback` (MarkdownView 互換)
        を提供。`set_render(mr)` で chafa を実起動 → stdout の ANSI 出力を
        Rich `Text.from_ansi` 経由で widget に貼る。subprocess は
        list-based argv + timeout 必須 (10s)、失敗時は ascii_text or
        unavailable マーカーに 2 段で降りる fail-closed。MarkdownView と
        組み合わせると本文にマーカー / pane に画像という分割表示になり、
        Textual の画面オーナーシップを壊さない。テスト 12 件追加、
        フルスイート 406 PASS。**残課題**: 実 chafa での E2E 検証 (現状は
        `runner` 注入の単体テストのみ)、Textual `run_worker(thread=True)`
        による非同期化 (現状は同期 `set_render`、画像描画が遅い場合の
        UI 凍結対策)。
      - **MarkdownView mermaid 自動展開統合完了 (2026-05-10, F15 (t3))**:
        `MarkdownView` に opt-in パラメータ 4 つ
        (`mermaid_render` / `mermaid_renderer` / `mermaid_image_callback` /
        `mermaid_cache_dir`) を追加。`_expand_mermaid_in` が fold の後段で
        `kind="mermaid"` フェンスを抽出 → renderer に流して本文を差し替え。
        ASCII 経路は本文に fallback 文字列を直接差し込み、image 経路は
        本文にマーカーを残しつつ `MermaidRender` を callback に渡して
        subprocess 起動はホスト責務 (Textual worker からも安全に呼べる)。
        SHA-256 16 桁ハッシュで同一 source は SVG キャッシュ共有。renderer /
        callback の例外は 2 段で fail-closed (元 source に戻る or マーカー
        だけ表示)。最新エントリのみ展開し旧履歴は不変。テスト 9 件追加、
        フルスイート 394 PASS。**残課題**: Textual subprocess worker での
        実 chafa 起動 + 画像描画完了通知 (現状は callback まで)。
      - **Mermaid 図インライン表示 (mmdc → SVG → image チェイン) 基盤完了
        (2026-05-10, F15 (t3))**: `llove/views/mermaid_render.py` に
        `MermaidRender` (kind/argv/svg_path/ascii_text) と
        `mmdc_available` / `find_image_tool` / `render_mermaid_to_svg` /
        `render_mermaid` / `ascii_fallback` を新設。mmdc を呼んで `.mmd` →
        `.svg` を生成し、既存 image catalog (chafa / viu / timg / kitty /
        wezterm) の最優先ツールで argv 構築。両ツールが揃わない / mmdc が
        失敗した場合は ASCII フォールバック (マーカー付き source 表示) に
        降りる fail-closed 設計。subprocess は list-based argv のみ
        (shell=True 禁止)、source は temp `.mmd` 経由。依存性注入で
        mmdc/chafa 未インストールの環境でもフルテスト可能 (16 件、
        フルスイート 385 PASS)。`[browser-mermaid]` extras + flowchart /
        sequence / class / state / ER / gantt / pie / mindmap / gitGraph /
        journey 等 13 種は mmdc が対応する図種をそのまま継承。
        次段階: MarkdownView 内での mermaid ブロック → image 自動描画統合
        (現状はモジュール公開のみ)。
      - テーマシステム (light / dark / high-contrast / dyslexia-friendly /
        solarized / nord / dracula) + `~/.config/llove/theme.toml`
      - 行間 / 余白の compact / comfortable / spacious 切替
      - CJK / 絵文字 / Nerd Font の 3 段フォントフォールバック (F17(s) 連携)
      - 見出しレベルの色 + 罫線 + 番号化、コードブロックの行番号 + diff
        ハイライト、表セルのゼブラストライプ、コールアウト種別アイコン
      - スクリーンリーダー連携 (espeak / festival / say) — オプション
      - 統合 URI: `md://`, `svg://`, `mermaid://`
- [ ] **F15 (u) Foldable Blocks (ブロック折り畳み)** (2026-05-10 ユーザ要望):
      - **(u 段階 1) UI 非依存データ層 + 見出しセクション折り畳み 完了
        (2026-05-10)**: `llove/views/folding.py` に
        `FoldRegion / FoldState / find_heading_regions / apply_folds` を
        新設 (純粋関数 + 不変/可変データクラス、Textual/Rich 非依存)。
        ATX 見出し抽出はネスト + code fence 回避対応。
        `▶ ## Heading (N lines)` サマリ生成 (u4)。MarkdownView に
        `toggle_fold / close_all_folds / open_all_folds / fold_regions`
        を統合。最新エントリのみに fold 適用 (旧履歴は常に展開)、
        line-number ベース永続性で同一文書再 feed でも保持。
        テスト 19 件全 PASS。
      - **(u 段階 2) コードブロック / 表 fold 完了 (2026-05-10)**:
        `find_code_block_regions` (` ``` / ~~~ ` ペア + 言語ラベル +
        unclosed fence は fail-closed) と `find_table_regions`
        (GFM header + alignment + body, code fence 内は無視) を folding.py
        に追加。`apply_folds` の summary は kind 別書式
        (heading: `▶ ## h (N lines)`, code: `▶ \`\`\`py (N lines)`,
        table: `▶ | table (3 cols) (N rows)`)。MarkdownView の
        `fold_regions()` は 3 種を統合して `start_line` 順返却 — 単一の
        toggle で構文種を問わず動作。テスト追加 18 件、フルスイート
        305 PASS + 3 skipped。
      - **(u 段階 3 = u8) F20 `:fold` コマンドパレット連携 完了
        (2026-05-10)**: ビルトイン `:fold close-all|open-all|
        by-tag <kind>|toggle <line>` を `llove/term/builtins.py` に追加
        (フックパターン: 実体は `ctx.hooks['fold']` 経由)。
        `make_markdown_fold_hook(view)` factory で MarkdownView と
        1 行 bind。フック未設定でも verb 正当なら audit-warn 通知に留め、
        verb 非対応 (None 返却) のみ ok=False。`:help` /
        `:help fold` から探索可能。ビルトイン総数 11→12。テスト
        18 件追加、フルスイート 323 PASS。
      - **(u 段階 4 = u3) Fold 状態 TOML 永続化 完了 (2026-05-10)**:
        `llove/views/folding_persistence.py` を新設。
        `save_fold_state(state, path, *, doc_id)` (atomic rename) +
        `load_fold_state(path)` (fail-closed: 不在/不正/異 version は
        空 FoldState 返却) + `default_fold_state_path(doc_id, base_dir)`
        (XDG_CONFIG_HOME or `~/.config/llove/folds/`, doc_id サニタイズで
        path traversal 防止)。`FOLD_STATE_VERSION = 1` で先方互換管理。
        手書き TOML シリアライザで追加依存なし。テスト 14 件追加、
        フルスイート 337 PASS。
      - **(u 段階 5) MarkdownView 永続化統合 完了 (2026-05-10)**:
        `MarkdownView(doc_id, fold_persist_dir)` 引数追加。構築時に
        `load_fold_state` で自動復元、`toggle_fold / close_all_folds /
        open_all_folds` の各 mutation 後に `save_fold_state` で自動保存。
        I/O 失敗は黙って続行 (UI を絶対に止めない fail-closed)。
        明示 flush 用 `save_folds()` 追加。`doc_id` 未指定時は完全に
        レガシー動作。テスト 6 件追加、フルスイート 343 PASS。
      - **(u 段階 6 = u8 補) `:fold preset` 4 種実装 完了 (2026-05-10)**:
        `outline` (h1/h2 のみ展開) / `code` (code のみ展開) /
        `data-only` (table のみ展開) / `prose` (見出しのみ展開) を
        folding.py の純粋関数 `apply_preset` で実装 (冪等、不明名は
        fail-safe defensive copy)。`:fold preset <name>` 動詞を
        `_cmd_fold` に追加、`make_markdown_fold_hook` で MarkdownView
        に bind (適用後 `_render` + `_persist_fold_state` で永続化も
        自動)。`by-tag` 動詞も永続化フック追加。
        テスト 10 件追加、フルスイート 353 PASS。
      - **(u 段階 7 = t3 prep) Mermaid ブロック識別 完了 (2026-05-10)**:
        ` ```mermaid``` ` フェンスを `find_code_block_regions` 内で
        `kind="mermaid"` にリラベル。`apply_folds` summary は
        `▶ ◇ mermaid: <label> (N lines)` で diagram を視覚区別。
        `:fold by-tag mermaid` が動作 (hook の valid kind に追加)。
        `prose` preset を mermaid 畳みに拡張。テスト 9 件追加、
        フルスイート 362 PASS。
      - **(u 段階 8 = u6) Fold ステータス表示 完了 (2026-05-10)**:
        `MarkdownView.fold_metrics() -> (closed, total)` と
        `fold_status() -> "fold: 3 closed / 12 total"` を公開。
        `_render()` 末尾で `border_subtitle` を自動更新するため、
        ホスト側で何もしなくても Textual ボーダーに常に最新メトリクス
        が表示される (要件 u6 ステータスバー連携)。テスト 7 件追加、
        フルスイート 369 PASS。次段階: mmdc 連携 (Mermaid → SVG → image),
        キーバインド (Vim/VSCode), JSONTreeView / NotebookView 連携。
      - 対象: 見出しセクション / コードブロック / Mermaid / SVG / 画像 /
        表 / 引用 / コールアウト / JSON ツリー / ログペイン / Notebook セル /
        Command Palette 出力履歴
      - キーバインド 2 系統: Vim (`za` `zc` `zo` `zM` `zR` `zj` `zk`) と
        VSCode (`Ctrl+Shift+[` `]`, `Ctrl+K Ctrl+0/J`), マウスクリック
      - コマンドパレット連携: `:fold close-all` `:fold by-tag mermaid`
        `:fold preset outline|code|data-only|prose`
      - 検索時の自動展開、ホバープレビュー (先頭 3 行 tooltip)
      - 折り畳み行: `▶ ## 設計詳細 (16 行)` `▶ ```python (42 行)` 等のメタ表示
      - ネスト対応 (外側を畳んでも内側状態保持)
      - 文書ごとの fold 状態を `~/.config/llove/folds/<doc-id>.toml` に永続化
      - F17 ウィンドウ種に `Foldable` mixin、ステータスバーに
        `[fold: 12 closed / 47 total]`
      - tree-sitter `folding` query / Vim foldmethod / Helix の fold UI を参考
      - fail-closed: 未対応ビューは fold 命令を audit warn して無視

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

## v0.8.0 — Window Management *(F17, 2026-05-09 追加)*

**ゴール:** SDI⇔MDI 切替・位置記憶・マルチディスプレイ・可変 Window 数・
「自由可変」「常駐ロック」二重コンテナ. シナリオ駆動レイアウト.

### 入る機能

- [x] **A. WindowManager 最小骨組み** (`llove/window/`) — **v0.3.0a1 完了**
      (Registry + IconSet 3 段 + Free/Locked Container + WindowLayout +
      WindowSpec + layout.toml 往復、全 20 件 PASS)
- [ ] LoveApp との互換層 (window_layout=None なら従来 4 ペイン動作維持)
- [ ] Textual 側 SDI/MDI/Tabbed/Tile レイアウト切替の実装
- [ ] Qt 本格版 (PySide6 + Qt-Advanced-Docking-System)
- [ ] マルチディスプレイ識別 (QScreen UID + DP/HDMI 抜き差し対応)
- [ ] レイアウトプリセット (初期 / 集中 / 観戦) + ワークスペース概念
- [ ] CLI: `llove demo --scenario shogi --layout focus`
- [ ] Sixel / Kitty graphics IconSet (実画像 SVG/PNG)
- [ ] F17(p)(r) シナリオ駆動レイアウトの shogi/typing/chess 適用

---

## v0.9.0 — Embedded Scripting + Editor / IDE *(F19/F20, 2026-05-09 追加)*

**ゴール:** llove 上で Python/Lua/Starlark/Janet/JS REPL + テキスト編集 +
LSP/lint/シンタックスハイライト + Notebook 風セル UI + Command Palette.

### 入る機能

- [ ] **F19 (a) Python REPL** (`code.InteractiveConsole`、デフォ同梱)
- [x] **F20 Command Palette dispatch core** (`llove/term/command.py`,
      `builtins.py` — `:help` `:identity` `:layout` `:demo` `:play`
      `:open` `:peer` `:set` `:get` `:alias` `:macro` 11 種, alias / macro
      入れ子 5 段防止 — 2026-05-10 完了)
- [x] **F20 Command Palette UI 骨組み** (`llove/term/completion.py`,
      `palette.py` — Textual `CommandPaletteWidget` / `CommandPaletteScreen`,
      Tab 補完, Up/Down 履歴, 候補表示 — 2026-05-10 完了)
- [ ] **F20 Command Palette UI 仕上げ** (履歴永続化 / fuzzy ハイライト /
      テーマ切替 / カラーアウトプット / 大入力時のスクロール)
- [ ] **F19 Editor モード** (Textual TextArea + DirectoryTree + tabs)
- [ ] **F19 (b) Lua** (`lupa`)
- [ ] **F19 (c) Starlark** (`pystarlark`)
- [ ] **F19 (l) Jupyter Notebook 風セル UI** (`euporie` 参考、ipynb 互換)
- [ ] **F19 lint / 診断** (ruff JSON, pyflakes)
- [ ] **F19 LSP クライアント** (pylsp, rust-analyzer)
- [ ] **F19 (d) Janet / chibi-scheme** (Lisp DSL)
- [ ] **F19 (e) JavaScript** (PyMiniRacer / pyduktape)

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
