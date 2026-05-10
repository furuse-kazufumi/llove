# llove 進捗ログ

> セッション間で持ち越したい「いま何が出来て、次に何をやるか」を記録するファイル。
> `docs/SESSION_SUMMARY.md` (Stop hook 自動生成) は git log のスナップショットなので、
> こちらは人間 / Claude が手で書き足し、要件側の文脈をたどれる足跡を残す。

---

## 2026-05-10 (続き 2) — F15 (t3) MarkdownView mermaid 自動展開統合

### 完成したもの

`MarkdownView` に opt-in で mermaid 自動展開を統合。前段で作った
`mermaid_render.py` を View 側から呼び出し、本文を実描画に置換する。

- 新パラメータ 4 つ (デフォルト OFF で既存呼び出し側を破壊しない):
  - `mermaid_render: bool = False` — 機能 ON/OFF
  - `mermaid_renderer` — renderer fn (None なら `render_mermaid` ラップ)
  - `mermaid_image_callback` — image kind の結果を受け取るホストフック
  - `mermaid_cache_dir` — SVG キャッシュ先 (None で tempdir)
- `_expand_mermaid_in()`: `find_code_block_regions` で `kind="mermaid"` の
  フェンスを抽出 → 内側 DSL を renderer に流して、ASCII 経路は本文に
  fallback 文字列を差し込み、image 経路はマーカー (`◇ mermaid diagram →
  rendered separately via chafa`) を残し callback で MermaidRender を渡す。
- **fold との順序**: fold が走った後で展開する。閉じ折られた mermaid は
  サマリ行に置換済みなので、開いているフェンスだけが renderer に流れる。
- **キャッシュ**: 同じ mermaid source は SHA-256 16 桁の subdir に集約。
  再 feed で SVG を作り直さない。
- **2 段 fail-closed**: renderer 例外 → 元 source 表示 / callback 例外 →
  マーカーだけ残して view は健全。
- 旧履歴は展開対象外 (最新エントリのみ)。スクロールバック中の fold が
  動かないようにする方針 (fold と統一)。

### テスト

- 9 件追加 (`test_markdown_view_mermaid.py`):
  default disabled / 通常 code 不変 / ASCII 経路 / 複数ブロック /
  image callback / ASCII 時 callback 不発 / renderer 例外 / callback 例外 /
  fold 互換性。
- フルスイート **394 PASS + 3 skipped** (385 → +9)、ruff クリーン、回帰ゼロ。

### 次セッションで着手する候補 (重要度順)

1. **Textual subprocess worker** — 現在 callback で MermaidRender を渡す
   までで止まっている。これを Textual の `run_worker` か `subprocess`
   モジュールで実起動して、kitty graphics / sixel を View 上に貼る。
   chafa は stdout 直書き派なので Textual が画面を奪われない仕組み
   (Pixels widget / Term Image 連携) が必要。
2. **(t2) SVG レンダラ** — `rsvg-convert` 検出 → image チェイン。
   mermaid_render.py の構造をテンプレに `svg_render.py` を複製、
   View 側統合は本セッションのパターンを再利用。
3. **キーバインド (Vim/VSCode)** — `za` / `zM` / `zR` / `Ctrl+Shift+[`。
4. **JSON ツリービュー / ログペイン fold** — folding.py の純粋関数を
   別ビューに展開。
5. **タスクリスト / コールアウト / 数式 (t1 拡張)** — `mdit-py-plugins`。

### 設計メモ (将来参照)

- 統合は `_expand_mermaid_in(text)` という pure 関数 1 本に閉じている
  ので、Notebook View / DiagramPane が同じパターンを再利用できる。
- 画像経路で本文にマーカーだけ残すのは「画像が後から非同期で出てくる」
  ケースを想定 (Textual subprocess worker は async)。同期 callback で
  既に画像表示が済んでいる場合もマーカーだけ残るが、これは「位置を
  予約する」役割として正しい。
- `mermaid_cache_dir` を tempdir デフォルトにしているのは、ユーザが
  cache 場所を意識せず使えるようにするため。本格運用時は doc_id 連動
  の永続キャッシュが望ましいが、F15 (t3) のスコープ外。

---

## 2026-05-10 (続き) — F15 (t3) mmdc → SVG → 画像チェイン基盤

### 完成したもの

`llove/views/mermaid_render.py` を新設。`folding.py` が
`kind="mermaid"` で識別したフェンスを **実描画** に流すための薄い shim。

- 公開 API: `MermaidRender` / `mmdc_available()` / `find_image_tool()` /
  `render_mermaid_to_svg()` / `render_mermaid()` / `ascii_fallback()`。
  すべて `llove.views` から再公開。
- パイプライン: `source` → `mmdc -i .mmd -o .svg` → 既存 image catalog
  (chafa/viu/timg/kitty/wezterm) の最優先ツール → ターミナル画像。
- Fail-closed: mmdc 欠損 / 画像ツール欠損 / mmdc 失敗 / OSError は
  すべて **ASCII フォールバック** (マーカー + 罫線 + source) に降りる。
  UI が renderer 失敗で落ちることはない。
- セキュリティ: subprocess は list-based argv のみ (shell=True 禁止)。
  mermaid source は temp `.mmd` 経由 (引数経由の長文流入を避ける)。
- 依存性注入: `mmdc_path` / `image_tool` / `runner` を全部差し替え可能で、
  mmdc 未インストールの CI でも 16 件の単体テスト全 PASS。

### テスト

- 16 件追加 (`test_mermaid_render.py`): 検出 4 / SVG 変換 5 (argv 検証 +
  失敗パス) / ASCII fallback 2 / 統合 5 (image 成功 / mmdc 欠 / image 欠 /
  mmdc 失敗 / 自動検出)。
- フルスイート **385 PASS + 3 skipped** (前回 369 → +16)、回帰ゼロ、
  ruff クリーン。

### 次セッションで着手する候補 (重要度順)

1. **MarkdownView 統合** — mermaid kind の region を見つけたら、本文の
   フェンス内容を `render_mermaid()` に流して `MermaidRender.argv` で
   subprocess 起動 / `ascii_text` で本文置換。Textual の subprocess 連携
   (worker thread) が必要。
2. **(t2) SVG レンダラ** — `rsvg-convert` 検出 → image チェイン。
   mermaid_render の構造をテンプレに `svg_render.py` として複製。
3. **キーバインド (Vim/VSCode)** — `za` / `zM` / `zR` / `Ctrl+Shift+[`。
4. **JSON ツリービュー / ログペイン fold (u)** — folding.py の純粋関数を
   別ビューに展開。
5. **タスクリスト / コールアウト / 数式 (t1 拡張)** — `mdit-py-plugins`。

### 設計メモ (将来参照)

- mermaid_render は **describe-only**: 実 subprocess 起動は呼び出し側
  (MarkdownView / DiagramPane) の責務。Pure 関数化 + dataclass 戻り値で
  テスト容易性を保ち、Textual との結合点を最後にずらした。
- temp `.mmd` は `output.with_suffix(".mmd")` で SVG と同ディレクトリに
  書き出すため、caller は tmpdir を 1 つ管理するだけで両方掃除できる。
- 画像ツール検出は `llove.browser.external.available_tools("image")` 経由
  なので、catalog に新ツール (例: img2sixel) を 1 行追加するだけで
  mermaid_render も自動的に対応する。

---

## 2026-05-10 — F15 (t1) MarkdownView + F15 (u) Foldable Blocks ひと山完成

### 完成したもの (9 コミット連続)

| コミット | 概要 |
|----------|------|
| `fcc6983` | F15 (t1) MarkdownView 骨組み — Rich GFM レンダラ |
| `85e7cb9` | F15 (u) 見出しセクション fold + UI 非依存 folding.py |
| `edfab25` | F15 (u) コードブロック / 表 fold 拡張 |
| `e0339a0` | F15 (u8) `:fold` コマンドパレット連携 + hook factory |
| `7119564` | F15 (u3) fold 状態 TOML 永続化 (純粋 I/O) |
| `a8a1393` | F15 (u3) MarkdownView 永続化統合 (auto load/save) |
| `3a3ff40` | F15 (u8) `:fold preset` 4 種 (outline/code/data-only/prose) |
| `3ad757f` | F15 (t3 prep) Mermaid 識別 (kind="mermaid") |
| `414f1b8` | F15 (u6) Fold ステータス表示 (border_subtitle 自動更新) |

### 公開された API (`llove.views`)

- 純粋データ層: `FoldRegion / FoldState / find_heading_regions /
  find_code_block_regions / find_table_regions / apply_folds /
  apply_preset / fold_preset_names`
- 永続化: `FOLD_STATE_VERSION / save_fold_state / load_fold_state /
  default_fold_state_path`
- View: `MarkdownView(*, doc_id, fold_persist_dir, ...)` +
  `make_markdown_fold_hook(view)`
- F20 ビルトイン: `:fold close-all|open-all|by-tag <kind>|toggle <line>|
  preset <outline|code|data-only|prose>`

### テスト

- 約 80 件追加 (各機能 TDD 先行)
- フルスイート: **369 PASS + 3 skipped**, 回帰ゼロ, ruff クリーン

### 次セッションで着手する候補 (重要度順)

1. **mmdc 連携** — `kind="mermaid"` を起点に外部ツール `mmdc` で SVG
   生成 → 既存 image チェイン (`chafa` / `kitty +kitten icat` 等) に流す。
   要件 t3 完成。`shutil.which("mmdc")` 検出 + subprocess + 失敗時
   ASCII フォールバック。
2. **(t2) SVG レンダラ** — `rsvg-convert` 検出 → 画像チェイン。
   要件 t2 着手。
3. **キーバインド (Vim/VSCode)** — Textual binding システム + `za`/`zM`/`zR`/
   `Ctrl+Shift+[` を MarkdownView に割り当て。run_test() で動作確認。
4. **JSON ツリービュー / ログペイン fold (u)** — folding.py の純粋関数を
   再利用して別ビューに展開。
5. **タスクリスト / コールアウト / 数式 (t1 拡張)** — `mdit-py-plugins`
   経由で markdown-it-py を強化。

### 設計メモ (将来参照)

- 折り畳みは「最新エントリのユーザテキストのみ」に作用し、履歴上の
  旧エントリは常に展開。スクロールバック時の文脈喪失を回避するため
  意図的な制約。
- fold 状態は line-number ベースで永続化されているので、ドキュメント
  の中身がほぼ変わらない限り再 feed でも閉じたまま維持される。
- `make_markdown_fold_hook` は I/O 失敗を黙って続行する fail-closed
  なので、UI が永続化問題で止まることはない。
- mermaid は code の subset ではなく独立 kind として扱う。これにより
  `:fold by-tag mermaid` や `prose` プリセットが diagram のみを操作
  できる。
