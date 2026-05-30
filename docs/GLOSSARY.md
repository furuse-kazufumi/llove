---
layout: default
title: "用語集 (GLOSSARY)"
description: "llove ドキュメント共通の日本語(英語)用語集"
nav_order: 99
---

# 用語集 (GLOSSARY)

> このページは llove の README / docs 全体で頻出する英語術語を **日本語(English)** 形式でまとめた中央用語集です。各ドキュメントの初出術語からここへリンクして参照します。

---

## llove とは(かみ砕いた説明)

llove（ラブ）は、**黒い文字だけの画面（ターミナル＝文字を打って操作する画面）の中で、グラフや表をきれいに動かして見せてくれる道具**です。ダッシュボードと呼ばれますが、これは車の運転席の前にある、速度や燃料の残りを一目で見られる計器盤のようなもの、と思ってください。工場の機械を測るセンサーの数字や、人の言葉を理解して答えてくれる AI の動きを 1 つの画面でまとめて流し見でき、そのままボタン 1 つで、見ている画面を 1 個のファイルに保存して、仲間にチャットや資料で送って共有できます。さらに、人が大事なところで「これでいいよ」と確認しながら一緒に進める作業台としても使えます。FullSense ™ という 3 つの製品の家族（llmesh / llive / llove）のうち、**画面に見せることと、人の確認を受け持つ役割**が llove です。

---

## 用語集

固有名詞(製品名・ライブラリ名)は訳さず、1 行の日本語注のみ付けます。

- **TUI(Text User Interface)** — テキストユーザーインターフェース。ターミナル(文字端末)の中で動く、罫線やグラフを使った画面のこと。
- **dashboard(ダッシュボード)** — 複数の情報を 1 画面に集約して一覧表示する画面。
- **workbench(ワークベンチ)** — 人が確認・操作しながら作業を進めるための作業台 UI。
- **HITL(Human-in-the-Loop, 人間参加型)** — 自動処理の途中に人間の確認・承認を組み込む方式。
- **widget(ウィジェット)** — 画面を構成する個々の部品(表・グラフ・パネルなど)。
- **view(ビュー)** — 1 つのデータをある形式で見せる表示単位(センサーストリーム表示、SPC チャート表示など)。
- **DataSource(データソース)** — データの供給元を抽象化した仕組み。mock / jsonl / sqlite / llmesh などを同じインターフェースで扱う。
- **ABC(Abstract Base Class, 抽象基底クラス)** — 共通の型を定義し、各実装がそれを継承する Python の仕組み。
- **URI(Uniform Resource Identifier)** — データの場所や種類を表す統一識別子(例: `mock://demo`)。
- **export(エクスポート)** — 表示内容を外部ファイル(1 ファイル HTML など)に書き出すこと。
- **snapshot(スナップショット)** — ある時点の画面を画像(SVG)として保存したもの。テスト用の基準画像にも使う。
- **scenario(シナリオ)** — `llove demo` で機能を体験させるための、用意された合成データの筋書き。
- **arena(アリーナ)** — 複数の LLM を対局させる多人数の競技場(ゲーム機能)。
- **dogfooding(ドッグフーディング)** — 自分たちの製品を自分たちで実際に使って検証すること。
- **i18n(internationalization, 国際化)** — UI を複数言語に切り替えられるようにする仕組み。
- **stream(ストリーム)** — データを連続的に流し続けて表示すること。
- **replay(リプレイ)** — 記録したデータを後から再生して表示すること(live の対義)。
- **SPC(Statistical Process Control, 統計的工程管理)** — 工程の異常を統計的に監視する手法。
- **CUSUM(Cumulative Sum, 累積和)** — 小さな変化の累積を検出する SPC の手法の 1 つ。
- **RAG(Retrieval-Augmented Generation, 検索拡張生成)** — 外部知識を検索して LLM の生成を補強する方式。
- **Audit / AuditTrail(監査証跡)** — 操作履歴を改ざん検知可能な形(ハッシュチェーン)で記録する仕組み。
- **Trace(トレース)** — 処理の経路や実行の流れを追跡した記録。
- **SensorEvent(センサーイベント)** — センサーから届く 1 件分の計測データ。
- **trust boundary(信頼境界)** — 信頼できる側とできない側を分ける境界線。越えるたびに再検証する。
- **fail-closed(フェイルクローズド)** — 検証に失敗したら通過させず安全側に倒す設計方針。
- **BWT(Bayesian Work Tree, ベイズ作業木)** — llive の作業状態をベイズ的に表現した木構造。
- **MCP(Model Context Protocol)** — LLM とツール・データ源を接続する標準プロトコル。llmesh が提供。
- **memory bus / memory link(メモリバス / メモリリンク)** — llive のメモリ層を流れるイベントの経路・連結。
- **on-prem(on-premises, オンプレミス)** — クラウドではなく自社・自宅内の環境で動かす形態。
- **extras(エクストラ)** — `pip install "llove[chess]"` のように、追加機能だけを選んで入れるオプション依存。

### 固有名詞(訳さず保持)

製品名・ライブラリ名・ツール名は英語表記のまま使用します。初出時のみ短い日本語注を付けます。

- **llove** — 本製品。TUI dashboard / HITL workbench(llmesh-llove として PyPI 配布)。
- **llmesh** — FullSense の secure LLM hub(オンプレ MCP サーバ)。
- **llive** — FullSense の自己進化型モジュラー記憶 LLM フレームワーク。
- **FullSense ™** — llmesh / llive / llove を束ねる umbrella ブランド。
- **Textual** — Python の TUI フレームワーク。llove の表示基盤。
- **Rich** — Python のターミナル装飾ライブラリ(Textual の基盤)。
- **Mermaid** — テキストから図(フローチャート等)を生成する記法。
- **SVG(Scalable Vector Graphics)** — 拡大しても劣化しないベクター画像形式。
- **Markdown** — 軽量マークアップ記法。GFM = GitHub Flavored Markdown。
- **PyPI(Python Package Index)** — Python パッケージの公式配布リポジトリ。
- **VS Code** — Microsoft のコードエディタ(devcontainer に対応)。
- **Slack** — チームチャットツール(HTML 共有先の例)。
- **Ollama / OpenAI / Anthropic** — LLM バックエンドの提供元(切替対象)。
- **Modbus / OPC-UA** — 産業 IoT 通信プロトコル(llmesh アダプタ経由で接続)。
- **SCADA(Supervisory Control and Data Acquisition)** — 産業の監視制御システム。
- **Ed25519** — 楕円曲線デジタル署名方式(shogi の per-move 署名で使用)。
- **HMAC(Hash-based Message Authentication Code)** — 鍵付きハッシュによる改ざん検知(Audit chain で使用)。
- **chafa / viu / timg / kitty / wezterm / mmdc / rsvg-convert** — 端末への画像描画・図変換ツール群。
- **Phoenix** — LLM トレース観測ツール(DataSource の 1 つ)。

---

> 用語の追加・修正は本ファイルへ。各ドキュメントは初出術語からこの用語集へリンクしてください。
