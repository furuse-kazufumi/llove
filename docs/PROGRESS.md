# llove 進捗ログ

> セッション間で持ち越したい「いま何が出来て、次に何をやるか」を記録するファイル。
> `docs/SESSION_SUMMARY.md` (Stop hook 自動生成) は git log のスナップショットなので、
> こちらは人間 / Claude が手で書き足し、要件側の文脈をたどれる足跡を残す。

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
