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
| F8 | LLMesh の **各機能** を体験できるシナリオ別 demo | `llove demo --list` で一覧、`llove demo --scenario <name>` で個別起動。シナリオごとに narration pane が解説を流し、何が起きているか自然言語で読める |
| F9 | **シナリオ品質基準** — smoke test だけで完了扱いしない | 各シナリオは 4 ペインすべてに情報が流れる（SensorStream / SPC / Audit / Narration の空白ペイン禁止）。`scripts/snapshot_scenario.py` で en/ja 両方の SVG を取得し目視確認した上で commit |
| F10 | **数式表示シナリオ**（バックログ） | LLM が LaTeX 記法で出した数式（例: `\int_0^\infty e^{-x^2} dx`）を TUI では Unicode に変換、`tools/qt_viewer/equation_viewer.py` で matplotlib mathtext によるリッチ表示。SPC は計算複雑度・推論時間で発火 |
| F11 | **学生向け入門シナリオ群** — LLMesh 知識ゼロでも「動いてる！」と楽しめる初歩デモ | 数学・物理・身近な現象がベース。narration はくだけた文体（"わー、表がたくさん出てるね" 等）。SensorStream にすぐ動きが出る。SPC alarm の意味を 1 行で説明。例: `coin_toss`（コイン投げ → 0.5 への収束）/ `dice_roll`（サイコロ分布）/ `number_guess`（二分探索）/ `weather`（1 都市の気温推移）/ `game_of_life`（ASCII セル）/ `pomodoro`（集中タイマー）/ `prime_sieve`（エラトステネスの篩） |
| F12 | **対局シナリオ** `shogi` — 2 つの LLM に共通盤面を見せて将棋させる + 人間対戦モード + ローカル LLM 対応 | (a) 共通盤面: 9x9 ASCII で TUI 表示、漢字駒（先手玉 / 後手王）、成駒・持ち駒も対応 (b) **合法手判定**: `[shogi]` extras (`python-shogi`、GPL-3.0 だが extras なので本体 MIT に感染しない) で駒の動き / 二歩 / 王手放置 / 行き所のない駒 / 持ち駒打ち / 打ち歩詰め / 千日手 / 入玉宣言勝ちまで判定。違反手は 3 回リトライで投了 (c) **LLM プレイヤ抽象化**: `mock` / `anthropic` (Claude) / `openai` (GPT) / `ollama` (**ローカル LLM** Llama 3 / Qwen / DeepSeek-R1 等) / `llamacpp` (llama.cpp HTTP server) / `lmstudio` (LM Studio OpenAI 互換) / `human` (キーボード入力)。CLI: `llove play shogi --sente <provider:model> --gote <provider:model>` で任意の組み合わせ (d) **プロンプト設計**: stateless per-move（system prompt は固定で prompt caching に乗る、user は SFEN + hands + last_5 + last_5_comments のみ毎ターン）。詳細は ROADMAP MVP2a 節 (e) 4 ペイン: SensorStream=評価値推移 / SPC=形勢逆転 alarm / Audit=棋譜 (`▲７六歩 (2.4秒)` 形式) / Narration=LLM の指し手解説 (f) 人間対戦: `llove play shogi --sente human --gote <model>` で TUI が合法手候補をハイライト (g) 棋譜 export: KIF / SFEN / JSONL の 3 形式で保存・再生可能 (h) Qt viewer (`tools/qt_viewer/shogi_viewer.py`): 本物の駒画像で局面表示、後手駒は 180° 回転 (i) **バッチ評価**: `--games N` で AvsB を N 局回して勝率を取れる |
| F13 | **ウェブカメラ + 画像 LLM デモ** `face_landmarks` (バックログ) | (a) `[webcam]` extras: `opencv-python`, `mediapipe` (Apache-2.0) もしくは `face_recognition` (b) 1 フレーム取得 → 顔検出 → 目/鼻/口の landmarks 抽出 (c) TUI: ASCII art で顔の縮小版 + landmark 位置を `*` `o` 等のマーカーで重ねる、SensorStream に「目の高さ」「両目間距離」等の数値 (d) SPC alarm: 複数人検出・顔向きの急変・カメラブラックアウト (e) Qt viewer (`tools/qt_viewer/face_viewer.py`): 実画像 + landmark オーバーレイ (f) 別シナリオ案: `gesture` (手のジェスチャ)・`pose` (全身姿勢)・`vlm_caption` (画像→キャプション LLM)。`vision` シナリオがすでにあるので拡張系として整理 |
| F14 | **マイク + 音声 LLM デモ** `voice_transcribe` / `voice_emotion` (将来検討) | (a) アイデアレベル — 実用 OSS 音声 LLM が手薄な間は要件のみ (b) 候補依存: `sounddevice` + OpenAI Whisper API もしくは ローカル `faster-whisper`、感情分析は `wav2vec2-emotion` 系 (c) TUI: 音量ストリーム / 書き起こしテキスト / 感情ラベル / 沈黙アラーム (d) Qt viewer: 波形 + spectrogram + 書き起こしハイライト (e) ストリーミング書き起こし (chunk → partial transcript) を SensorStream に流す (f) 着手は **WhisperX** など chunk 対応モデルが手堅くなるタイミング |
| F15 | **ブラウザ並みのデータ表示機能** — llove が「ターミナル版 Artifact」として、HTML ブラウザに匹敵する多モーダル表示力を持つ (新要求 2026-05-09) | (a) **画像** インライン表示（Sixel / Kitty / iTerm2 グラフィックスプロトコル）+ ASCII フォールバック (b) **PDF** ページレンダリング（Sixel 経由、または Qt viewer） (c) **HTML / Markdown** Rich ベースの整形表示（既存 NarrationView 拡張） (d) **テーブル** ソート・フィルタ可能な対話的 DataTable（Textual 標準） (e) **グラフ**: 折れ線・棒・散布・ヒートマップ（textual-plotext 既存 + 新拡張） (f) **地理データ**: 緯度経度を terminal-aware ascii map にプロット（natural earth tile 化、または Qt viewer） (g) **3D**: 既存 `pointcloud` の延長で、点群・メッシュを Sixel + Qt viewer (h) **音声波形 / spectrogram**: F14 と統合 (i) **動画**: フレーム ASCII / Sixel ストリーム（Kitty graphics 推奨） (j) **JSON / YAML**: ツリービューで折りたたみ可能 (k) **新パネル種**: `BrowserView` を追加し、上記を URI でルーティング（`image://path`, `pdf://path`, `geo://lat,lon`, `web://https://...`, `csv://path`, ...） (l) **依存方針**: コア依存は増やさず、各種 viewer は extras（`[browser-image]`, `[browser-pdf]`, `[browser-geo]`, `[browser-3d]`, または一括 `[browser-all]`）。fail-closed: viewer が無ければ ASCII フォールバック表示 + 「`pip install llmesh-llove[browser-all]` で X が見えます」案内 (m) **llmesh 普及**: 同じ表示面を `llove view --source llmesh+...` で LLMesh のあらゆるストリームに向けると、識別子・署名つきで多モーダルデータが見える状態にする — Telnet を NetSurf / Firefox に育てるイメージ (n) **roadmap**: v0.6.0「Browser-grade Display」を新設、F15 の (a) 画像 → (b) PDF → ... の順に小刻みに刻む (o) **外部ツール呼び出し OK 方針** (2026-05-09 確定): Python で全部書かず、既存 CLI ツールを `subprocess` で呼んで標準出力をペインに流すレンダラを許容。例: 画像 = `chafa` / `viu` / `kitty +kitten icat` / `wezterm imgcat`、PDF = `pdftoppm` + 画像レンダラ、動画 = `ffmpeg` でフレーム抽出 + `mpv --vo=tct`、HTML = `w3m -dump` / `lynx -dump`、グラフ = `gnuplot -e "set term sixel"`、地図 = `mapscii` / OSM tile + `chafa`、QR = `qrencode -t ANSI`、シンタックスハイライト = `bat`、JSON 整形 = `jq`、SQL = `sqlite3`、… **方針**: (i) llove は薄い shim に徹し、外部ツールの存在を実行時検出 (`shutil.which`)、無ければ ASCII フォールバック + 「`apt install chafa` で X が見えます」案内、(ii) コマンド実行は **list-based subprocess** のみ (shell=True 禁止、untrusted パスは shlex.quote 等で escape)、(iii) ツールカタログは `llove/browser/external.py` に YAML 風辞書で定義 (URI scheme → tool 候補リスト + 引数テンプレ + フォールバックチェイン)、(iv) Sixel 対応端末検出 (`$TERM`, `tput` のクエリ) で自動分岐、(v) Qt viewer は最終フォールバック (TUI で出ない時のみ起動) (p) **複数選択肢 + 設定メニュー方針** (2026-05-09 確定): 1 モーダルに複数レンダラ候補を提示し、ユーザがメニューから選べる形。実装方針: (i) `llove/browser/registry.py` でレンダラを「優先度・互換性・Pure Python / 外部 CLI / Qt」の 3 軸で分類、(ii) 設定モーダルを `Ctrl+,` または Help メニューから開ける（Textual の ModalScreen + DataTable で「URI scheme × renderer 候補 × 状態 (✓ available / ✗ missing / ⚠ degraded)」表示）、(iii) ユーザ選択は `~/.config/llove/renderers.toml` に永続化（XDG 準拠）、(iv) **Qt 許容**: 端末が Sixel/Kitty 非対応かつ画像表示の重要シナリオでは Qt viewer (PySide6) を first-class フォールバックとして許容。`llove/browser/qt_fallback.py` でモーダル別 Qt window をスポーン、TUI と並走、(v) 環境互換性: WSL / SSH 越し / tmux / screen / Docker exec / Termux 等で動く構成を CI で smoke 化、(vi) **GUI/TUI ハイブリッド許容**: 「TUI で識別子・ログ・棋譜・テキストデータ」「Qt で画像・3D・PDF」のように分担可能。フィードバック起点は常に TUI (キーボード) |

| F16 | **マルチゲーム LLM 対局アリーナ** — shogi (F12) と同じ枠組みで chess / go / mahjong / カードゲームを LLM 間対局できる (新要求 2026-05-09) | (a) **共通骨格**: F12 で確立した `Engine` + `Player ABC` + `Loop` + `Provider` 抽象を `llove/games/<game>/` に展開。各ゲームは独立の extras で分離 (`[chess]`, `[go]`, `[mahjong]`, `[poker]`, `[card]`, または一括 `[games-all]`) (b) **CLI 統一**: `llove play <game> --player1 <provider:model> --player2 <provider:model> [--players N for multi-player games]`。例: `llove play chess --player1 anthropic:claude-haiku-4-5 --player2 ollama:llama3:70b` (c) **対象ゲーム**: ① **chess** (`python-chess`, MIT、合法手・stalemate・en passant・castling 完備、参考: 14k★ GitHub) ② **go** (碁、`sente` or `katago` python bind、9x9 / 13x13 / 19x19 切替) ③ **mahjong** (麻雀、`mahjong` package = nekobean/mahjong、Riichi ルール、点数計算同梱) ④ **poker** (`pokerkit` Texas Hold'em / Omaha、`treys` for hand evaluation) ⑤ **bridge** (`endplay` package) ⑥ **hanafuda** こいこい (花札、自前実装) ⑦ **大富豪 / 七並べ / 神経衰弱 / speed** (自前実装、簡単な card game pack) ⑧ **blackjack** (dealer vs LLM 複数) (d) **参考プロジェクト**: **OpenSpiel** (DeepMind, 50+ ゲーム、C++ + Python、Apache-2.0) を inspiration とし、可能なら拡張ゲームのソース足場として一部利用検討。**pgx** (JAX-based、shogi/chess/go/backgammon/connect4 等の RL gym) も参考 (e) **共通機能**: Ed25519 署名 (F12 同様) / 棋譜 export (各ゲームの標準フォーマット — chess: PGN, go: SGF, mahjong: tenhou.net JSON, card: 自前 JSONL) / バッチ評価 `--games N` で勝率比較 / 観戦モード (`llove view`) (f) **TUI 表現**: ゲーム盤を ASCII / 半角換算で表示、SensorStream に評価値・残り時間・残り牌、SPC alarm に大局急変・違法手・連続王手の千日手、Audit に手順・棋譜、Narration に LLM の手読み解説 (g) **マルチプレイヤー対応**: 麻雀・大富豪は 3〜4 名 LLM。各 LLM 独立の identity (`llmesh.identity` per-player)、署名は誰が打牌したかをチェイン (h) **不完全情報ゲーム対応**: 麻雀・ポーカーは「自分の手だけ見える」prompt 設計が必須 — 共通 Player ABC を「観測 → 行動」非対称型に拡張、`Engine.observation_for(player)` を追加 (i) **roadmap**: v0.7.0「Game Arena」を新設、shogi (F12 完了) → chess (最小コスト) → go → mahjong → poker → カードゲーム小品の順 (j) **llmesh 普及貢献**: 各ゲーム対局を 2 つの llmesh ノード間で行う場合 `llmesh:peer:<NodeID>` プロバイダで peer の `<game>.think` MCP ツール経由 — llmesh-mcp が「LLM 同士のメッシュ越しゲーム」基盤に育つ (k) **fail-closed**: 各ゲームの extras が無い場合は `pip install llmesh-llove[chess]` 等の案内のみ表示し、shogi など他ゲームの動作は影響しない |

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

## 5.5 LLMesh 機能カバレッジシナリオ（F8 詳細）

llove は LLMesh のほぼ全機能を **オフライン合成データで** 体験できるシナリオを揃える。各シナリオは決定論的（seed 固定）、完全にネットワーク不要。

| ID | シナリオ名 | カバーする LLMesh 機能 | 体験できること |
|---|---|---|---|
| S1 | `firewall` | `PromptFirewall` 4 層 (L0/L1/L1.5/L2) | 12 サンプル prompt が各層で BLOCK / SUMMARIZE / ALLOW される様子 |
| S2 | `scada` | `ExplainedCUSUM` + `LLMExplainer` | センサーが正常→異常→復帰し、alarm 時に LLM が原因仮説を Markdown で吐く |
| S3 | `multimodal` | `UnifiedSPC` + `VLMFeatureExtractor` | 数値センサーと画像 caption の 2 系統が時刻同期して結合 SPC 判定 |
| S4 | `rag` | RAG 3 ストア (Numpy / SQLite / LSH ANN) | 同一クエリを 3 ストアで検索、レイテンシ + recall@10 を比較表示 |
| S5 | `backends` | LLM backend ABC (Ollama / OpenAI / Anthropic) | 同一プロンプトを 3 backend に投げた風の比較（tokens / latency / cost） |
| S6 | `audit` | `AuditTrail` HMAC chain | エントリ追加 → 改ざん → `verify_chain()` が検知する流れ |
| S7 | `reliability` | `MessageAssembler` + `ChunkSender` + `WatchdogTimer` | パケット損失あり通信での ACK / RETRANSMIT / TTL 期限切れの動き |

実装は `llove/demo/scenarios/` 配下に各シナリオ 1 ファイル。共通インタフェースは `DemoScenario` ABC で `name`, `title`, `description`, `events()` を要求する。

### シナリオ起動方法

```bash
llove demo                       # メニューで対話的に選ぶ
llove demo --list                # 一覧表示
llove demo --scenario firewall   # 直接起動
llove demo --scenario rag --seed 99
```

実行中は **narration pane** が画面下部に常駐し、各イベントに紐づく解説を Markdown 風に流す。

### シナリオ拡張要件

- 第三者が **5 分** で新シナリオを追加できること
- リポジトリ `llove/demo/scenarios/_template.py` をコピーし、`__init__.py` に 1 行追加で起動可能になる構成
- 詳細手順は `docs/contributing-scenarios.md`（コピペ用テンプレート + 命名規則 + Style Guide + 禁止事項）
- 各シナリオは **完全オフライン**（ネットワーク禁止 / ファイルシステム書き込み禁止 / LLMesh import 禁止）
- 既存テスト `tests/test_scenarios.py` は `SCENARIOS` 全件にパラメタライズで自動適用されるため、新シナリオ追加時もスモークテストが追従する

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
