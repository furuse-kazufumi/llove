# ターミナル一枚で「現場の LLM 観測」を ― llove

> LLMesh の Artifact ターミナル ― `llmesh-llove` を設計・実装している話。
> 「TUI で LLM × 産業 IoT を可愛く観測する」という、地味だが効くニッチに賭けています。

## なぜ作ったか

LLM の dashboard というと、Streamlit / Grafana / Web UI が定番です。けれど **規制現場・オフライン現場・SRE オペ室** には、共通する別の制約があります。

- ブラウザを置けない、または置きたくない端末がある
- SSH 越しに「いまの状態」を秒で見たい
- グラフィカル UI のラグや過剰アニメーションが、運用判断の邪魔になる
- ログ・トレース・SPC・RAG・監査を **同じ時間軸** で 1 画面に並べたい

`llove` は、これを **1 枚のターミナル** で解く個人プロジェクトです。LLMesh のデータ (SensorEvent / SPC / RAG / Audit / Trace) を Textual ベースの TUI で観測し、レイアウトは TOML で完全にユーザ可変。SSH 越しでも、現場 PC でも、開発機でも、同じ画面を出せます。

## 設計の核

1. **TUI ファースト** — Textual + Rust 加速候補。ブラウザ不要、SSH 越し可、低帯域でも秒単位応答。
2. **layout.toml で全部可変** — SDI/MDI 切替、自由可変ペイン、常駐ロックペイン、マルチディスプレイ。Qt-ADS の TUI 版。
3. **ブラウザ並み表示 (F15)** — Markdown / SVG / Mermaid / 画像 / 折り畳み / テーマを TUI で。視認性 5 大柱。
4. **マルチゲーム LLM 対局アリーナ (F16)** — chess / go / mahjong / poker / connect4… を **同じ抽象** で対局。LLM 戦略の比較研究にも使える。
5. **タイピング / テトリス等の "LLM × 人間協働 デモ"** — 教育用最小サンプル (~200 行)、SNS 拡散性高い PR 用。
6. **埋込スクリプト + IDE モード (F19)** — Python / Lua / Starlark / Janet / JS。Helix / Kakoune / Neovim 流の操作感。
7. **PowerShell 互換シェル + Claude Code 統合 (F23/F24)** — 現場運用ツールとしての差別化軸。
8. **F25 連携基盤** — llmesh が MCP 経由で `llove ↔ llive` を仲介。BWT / route trace / memory link を TUI で観測。

## なぜキャリアの観点で重要だったか

派手な Web UI は履歴書には強いですが、**運用のしやすさ** はもっと深い問題です。`llove` を作る過程で残ったのは、次のような "見えない強み" でした。

- **TUI を本気で作る** という、Web 全盛期にあえて掘った深堀り。SSH 越しオペレーションが当たり前の業務 (SRE / 制御室 / 工場現場) で実装感覚が効く。
- **Textual + tree-sitter + LSP** をモダンに組み合わせ、IDE 級の操作を端末で再現する設計判断。
- **layout.toml** を中心に置く設計で、ユーザーが UI を所有できるツールを書ける。
- **LLM 対局アリーナ** によって、LLM 戦略の比較・観測・教育を一つの抽象に乗せた経験。
- **llmesh ファミリー設計** — バックエンドの責務を最小に保ち、TUI 側で "見せる工夫" を集中させる原則。

これらは、開発者ツール / 運用ツール / Devrel / EUC まわりのキャリアで、必ず効きます。

## 数字で見る現在地 (2026-05-14)

- **v0.6+** 開発中。F15 (ブラウザ並み表示) / F16 (LLM 対局アリーナ) / F17 (window 管理基盤) / F19 (埋込スクリプト + IDE) / F25 (llmesh × llive 連携) を段階実装。
- **716 PASS + 1 skipped** (F25 関連 105 件含む)、ruff クリーン。
- PyPI: `pip install llmesh-llove` (v0.2.2 公開済、v0.3.0a1 開発中)。

## どこに向かうか

`llove` は、`llmesh` (オンプレ MCP ハブ) + `llive` (自己進化型モジュラー記憶 LLM) と組み合わせて、**現場の LLM × 産業 IoT を 1 枚のターミナルで観測する** スタックの可視化層です。本気で TUI を磨いてみたい方、運用ツールを所有したい方は、ぜひ触ってみてください。

> GitHub: <https://github.com/furuse-kazufumi/llove>
> PyPI: `pip install llmesh-llove`

#AI #LLM #TUI #Textual #DeveloperTools #SRE #IndustrialIoT #OpenSource #個人開発 #キャリア
