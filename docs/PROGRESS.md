# llove 進捗ログ

> セッション間で持ち越したい「いま何が出来て、次に何をやるか」を記録するファイル。
> `docs/SESSION_SUMMARY.md` (Stop hook 自動生成) は git log のスナップショットなので、
> こちらは人間 / Claude が手で書き足し、要件側の文脈をたどれる足跡を残す。

---

## 2026-05-10 (続き 5) — F15 (t2) SVG → PNG → 画像チェイン基盤

### 完成したもの

mermaid_render の構造をテンプレに `llove/views/svg_render.py` を新設。
SVG XML → temp `.svg` → `rsvg-convert -o output.png input.svg` → 既存
image catalog (chafa/viu/timg/kitty/wezterm) の最優先ツール → ターミナル画像。

- 公開 API (mermaid_render と一対一対応):
  - `SVGRender` (kind/argv/png_path/ascii_text/image_tool dataclass)
  - `rsvg_convert_available()` / `find_image_tool()`
  - `render_svg_to_png(source, output, *, rsvg_path, runner)` — argv
    `[rsvg, "-o", out.png, in.svg]` を組んで実行
  - `render_svg(source, *, output_dir, rsvg_path, image_tool, runner)` —
    高レベル統合、自動検出付き
  - `ascii_fallback_for_svg(source)` — 先頭 240 文字に切ってマーカー付き
    表示 (XML 全文を流すと爆発するため)
- セキュリティ: subprocess は list-based argv のみ (shell=True 禁止)、
  入力 XML は temp `.svg` 経由。
- Fail-closed: rsvg 欠損 / image tool 欠損 / 異常終了 / OSError は全て
  ASCII fallback に降りる。
- 依存性注入: rsvg / image_tool / runner を全部差し替え可能で、
  rsvg-convert + chafa 未インストールの CI でも全機能テスト可能。

### MermaidImagePane との互換性

`SVGRender` は `MermaidRender` と同じ shape (kind/argv/ascii_text を共有)
なので、既存の `MermaidImagePane.set_render(mr)` にそのまま渡せる
(duck typing)。pane 名を将来 `ImageRenderPane` にリネームすると意図が
明確になるが、現状はそのまま再利用が動く。

### テスト

- 14 件追加 (`test_svg_render.py`):
  検出 2 / `render_svg_to_png` argv + 失敗パス 5 / ASCII fallback 2 /
  統合 5 (image 成功 / rsvg 欠 / image 欠 / rsvg 失敗 / 自動検出)。
- フルスイート **429 PASS + 3 skipped** (415 → +14)、ruff クリーン、回帰ゼロ。

### 次セッションで着手する候補 (重要度順)

1. **MarkdownView svg ブロック自動展開統合** — mermaid と同じパターンで
   `<svg>...</svg>` または `svg://path` を fold 後段で展開して `render_svg`
   に流す。MarkdownView の `_expand_mermaid_in` を `_expand_diagram_blocks_in`
   に汎化するのが自然。
2. **MermaidImagePane → ImageRenderPane リネーム** — 既に SVGRender も
   受けられる形になっているので、名前を汎用化して mermaid / svg /
   今後の他フォーマットを統一する。
3. **実 chafa + rsvg-convert での E2E 検証** — dev 環境で `llove demo` 経由
   で動作確認。CI ではスキップ (binary 依存)。
4. **キーバインド (Vim/VSCode)** — `za` / `zM` / `zR` / `Ctrl+Shift+[`。
5. **JSON ツリービュー / ログペイン fold** — folding.py の純粋関数を
   別ビューに展開。

### 設計メモ (将来参照)

- `mermaid_render.py` と `svg_render.py` の **構造が一対一に揃っている** の
  は意図的。後続 (PlantUML, graphviz dot, ditaa, ...) を足すときも同じ
  テンプレで書けば、テスト 14 件を雛形として再利用できる。
- ASCII fallback の方針は format によって分けた:
  mermaid → 元 source 全部 (人間可読 DSL なので情報落ちなし)
  svg → 先頭 240 文字 + 「...」(XML は人間可読でないため抜粋で十分)
- `rsvg-convert` の argv は `-o output input` の順序。mermaid の mmdc は
  `-i input -o output`。両者で違うので argv 構築は format ごとに分けた。
- 中間ファイル名は両者とも `output_dir / "diagram.<ext>"` 固定。caller が
  output_dir を unique にすれば衝突しない (現状 MarkdownView 側で
  SHA-256 16 桁 subdir を使っている)。

---

## 2026-05-10 (続き 4) — F15 (t3) MermaidImagePane 非同期化

### 完成したもの

`set_render_async(mr)` を追加し、subprocess を別スレッドに逃がして UI を
凍らせない経路を完成。

- 3 段 fallback で「必ず work が走る」状態:
  1. `worker_dispatcher` 注入 (テスト / 特殊用途)
  2. Textual の `self.run_worker(work, thread=True, exclusive=True)`
  3. 同期 fallback (App 未 mount / 例外時)
- pure 関数 `_compute_text(mr) -> str` を抽出し、subprocess + 戻り値
  処理 + fallback 計算をここに閉じ込め。widget 更新は `_apply_text` /
  `_apply_text_thread_safe` に分離。
- `_apply_text_thread_safe` は worker thread から widget を更新するときの
  入口で、Textual App 内なら `self.app.call_from_thread` 経由で main
  thread へ飛ばし、App 外なら直接更新する (テスト互換)。
- ANSI 自動判定: `_apply_text` は ESC (`\x1b`) を含む文字列を
  Rich `Text.from_ansi` で描画。プレーンは `update(text)` で直貼り。
- `make_mermaid_image_callback(pane, *, async_dispatch=True)` のデフォルトを
  async に変更。`async_dispatch=False` で旧来の同期 path に戻せるので、
  テストや「即座に結果が欲しい」用途は両立可能。

### テスト

- 9 件追加 (`test_mermaid_pane_async.py`):
  `_compute_text` 3 / `set_render_async` 4 / callback factory 2。
- フルスイート **415 PASS + 3 skipped** (406 → +9)、ruff クリーン、回帰ゼロ。

### 次セッションで着手する候補 (重要度順)

1. **実 chafa での E2E 検証** — chafa を実際にインストールした dev 環境で
   `llove demo` 経由で mermaid → image の見栄えを確認。CI ではスキップ
   (binary 依存)。
2. **(t2) SVG レンダラ** — `rsvg-convert` 検出 → image チェイン。
   `mermaid_render.py` + `mermaid_pane.py` の構造をそのままテンプレ化
   できるはず。
3. **キーバインド (Vim/VSCode)** — `za` / `zM` / `zR` / `Ctrl+Shift+[`。
4. **JSON ツリービュー / ログペイン fold** — folding.py の純粋関数を
   別ビューに展開。
5. **タスクリスト / コールアウト / 数式 (t1 拡張)** — `mdit-py-plugins`。

### 設計メモ (将来参照)

- worker thread からの widget 更新は `call_from_thread` 経由が原則。
  Textual の widget は主に main loop 上で操作される前提なので、これを
  破ると race condition のリスクがある。`_apply_text_thread_safe` で
  この規約を 1 箇所に閉じ込めた。
- `worker_dispatcher` の注入を可能にしたのは、テストで「dispatch されたか」
  「何回呼ばれたか」「同期 fallback が効いたか」を順序付きで検証するため。
  本番では None で十分 (Textual `self.run_worker` が選ばれる)。
- `exclusive=True` を `run_worker` に付けたのは、同じ pane で連続して
  mermaid が来たときに古い render を打ち切って最新だけを表示するため。
  Textual のデフォルトは並列なので、画面が一瞬古い image で上書きされる
  問題を予防。
- ANSI 自動判定 (ESC 含む?) は単純だが堅い。Rich の `Text.from_ansi` は
  ANSI が無い文字列を渡しても安全に動くが、無駄な解析を避けるため
  分岐させている。

---

## 2026-05-10 (続き 3) — F15 (t3) Textual subprocess worker + MermaidImagePane

### 完成したもの

mermaid 統合の最後のピース。MarkdownView の callback で受けた
`MermaidRender(kind="image")` を実 subprocess (chafa) に流して、stdout の
ANSI 出力を Textual widget に貼る経路。

- 新モジュール `llove/views/mermaid_pane.py`:
  - `run_image_render(argv, *, runner, timeout)`: pure 関数。argv を
    実行 → stdout 文字列を返す。失敗時 None。runner 注入でテスト可。
  - `MermaidImagePane(Static)`: Textual widget。`set_render(mr)` で
    image / ascii / 失敗を分岐表示。Rich `Text.from_ansi` で ANSI を貼る。
  - `make_mermaid_image_callback(pane)`: 同期 callback ファクトリ。
    `MarkdownView.mermaid_image_callback` 互換。pane 側例外を吸収。
- セキュリティ: subprocess list-based argv のみ、timeout 必須 (10s 既定)、
  例外 / 非ゼロ / TimeoutExpired は全部 None 経由で fallback に降りる。
- テスト容易性: runner 注入 + Static.update() が App 不要なので、12 件
  全て subprocess を実行せずに走る。

### テスト

- 12 件追加 (`test_mermaid_pane.py`): pure runner 4 / Pane 5 / callback 2 /
  end-to-end (MarkdownView → callback → pane → ANSI) 1。
- フルスイート **406 PASS + 3 skipped** (394 → +12)、ruff クリーン、回帰ゼロ。

### 次セッションで着手する候補 (重要度順)

1. **Textual `run_worker(thread=True)` で `set_render` 非同期化** — 大き
   な diagram で chafa が遅いと UI が凍る。現状は同期。スレッドに逃すと
   UI が動き続けるが、widget update は main thread 経由が必要 (Textual の
   `call_from_thread` パターン)。テストは sleep の代わりに mock runner で
   制御。
2. **実 chafa での E2E 検証 / 動作確認** — chafa が実際にインストール
   されている開発環境で `llove demo` (or 専用 demo) を起動して
   mermaid → image の見栄えを確認。CI ではスキップ (binary 依存)。
3. **(t2) SVG レンダラ** — `rsvg-convert` 検出 → image チェイン。
   `mermaid_render.py` + `mermaid_pane.py` の構造をそのままテンプレ化。
4. **キーバインド (Vim/VSCode)** — `za` / `zM` / `zR` / `Ctrl+Shift+[`。
5. **JSON ツリービュー / ログペイン fold** — folding.py の純粋関数を
   別ビューに展開。

### 設計メモ (将来参照)

- `set_render` を同期にしたのは、テストを `runner` 注入だけで完結させる
  ため。非同期化するときは `set_render` の中で `self.run_worker(...)` を
  呼ぶラッパー (例 `set_render_async`) を足し、テストはそのまま同期版で
  カバーし続けるのが楽。
- `run_image_render` の戻り値は str (UTF-8 デコード済) にした。chafa は
  ANSI を bytes で吐くが、Rich の `Text.from_ansi` が str を期待するため
  型変換のレイヤを 1 箇所に閉じ込めた。デコード不能な bytes は
  `errors="replace"` で生き残らせる (UI が落ちない方を優先)。
- `MermaidImagePane` は `Static.update()` を try/except で囲んで App 外
  でも落ちないようにした。これは MarkdownView の既存パターンと統一。

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
