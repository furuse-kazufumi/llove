# Changelog

All notable changes to **llove** are recorded here.
This project follows [Semantic Versioning](https://semver.org).

## [Unreleased] — 0.3.0a1 in progress

### Added — F15 (t3) Textual subprocess worker + MermaidImagePane (2026-05-10)

- **新モジュール `llove/views/mermaid_pane.py`** — `MermaidRender(kind="image")`
  を受け取り、subprocess (chafa / viu / timg / kitty +kitten icat /
  wezterm imgcat) を実起動して **stdout の ANSI 出力を Static widget に貼る**。
- **`run_image_render(argv, *, runner, timeout)`** — pure 関数。argv を実行
  し、捕捉した stdout を str で返す。失敗時 (空 argv / 非ゼロ終了 /
  OSError / TimeoutExpired) は ``None``。テストでは ``runner`` 注入で
  subprocess を踏まずに argv 検証可能。
- **`MermaidImagePane(Static)`** — Textual widget。``set_render(mr)`` で
  `MermaidRender` を受け、kind に応じて分岐:
  - `image` → subprocess 起動 → 成功なら `Text.from_ansi()` で widget 更新
  - `ascii` → `mr.ascii_text` をそのまま貼る
  - 失敗 → `mr.ascii_text` か `_UNAVAILABLE_MARKER` で fallback
- **`make_mermaid_image_callback(pane)`** — `MarkdownView.mermaid_image_callback`
  互換ファクトリ。同期 callback として動き、内部で `pane.set_render(mr)`
  を呼ぶ。`set_render` の例外は `contextlib.suppress` で握り潰して
  View 側に波及させない。
- **セキュリティ**: subprocess は list-based argv のみ (shell=True 禁止)、
  必ず timeout 付き (デフォルト 10 秒)。
- **テスト容易性**: `runner` 差し替えで subprocess 不要 / `Static.update()`
  は App mount 不要 → widget 単体テスト可能。
- **テスト 12 件追加** (`test_mermaid_pane.py`):
  runner pure 関数 4 件 (成功 / 非ゼロ / OSError / 空 argv) /
  Pane 5 件 (placeholder / image 成功 / ascii / 失敗 / argv 空) /
  callback ファクトリ 2 件 (正常ルーティング / pane 例外吸収) /
  end-to-end MarkdownView → pane 1 件。
  フルスイート **406 PASS + 3 skipped** (394 → +12)、ruff クリーン、回帰ゼロ。

### Added — F15 (t3) MarkdownView mermaid 自動展開統合 (2026-05-10)

- **`MarkdownView` 4 つの新パラメータ** (全て opt-in、デフォルトは既存挙動維持):
  - `mermaid_render: bool = False` — 機能 ON/OFF
  - `mermaid_renderer: Callable[[str, Path], MermaidRender] | None` —
    描画エンジン (None なら自動検出する `render_mermaid` をラップ)
  - `mermaid_image_callback: Callable[[MermaidRender], None] | None` —
    image kind の結果を受け取り、subprocess 起動はホストに委譲
  - `mermaid_cache_dir: Path | None` — SVG キャッシュ先 (None で
    `tempfile.gettempdir() / "llove-mermaid-cache"`)
- **`_expand_mermaid_in()` 新メソッド**: `find_code_block_regions` で
  `kind="mermaid"` のフェンスを抽出し、内側の DSL を renderer に流して
  本文を差し替える。fold の **後** に動くので、閉じ折られた mermaid は
  サマリ行のままスキップされる (期待通り)。
- **キャッシュ戦略**: 同じ mermaid source は SHA-256 ハッシュ先頭 16 桁の
  サブディレクトリに集約される。再 feed で SVG を作り直さなくて済む。
- **2 段の fail-closed**:
  - renderer が raise → 元 source を本文に戻す
  - image_callback が raise → view は落ちず、本文マーカーは出す
- 旧履歴エントリは展開対象外 (最新エントリだけ)。スクロールバック中の
  fold/レイアウトを動かさないため。fold 同様の方針。
- **テスト 9 件追加** (`test_markdown_view_mermaid.py`):
  default disabled / 通常 code 不変 / ASCII 経路 / 複数ブロック /
  image callback 起動 / ASCII 時 callback 不発 / renderer 例外 /
  callback 例外 / fold 互換性。
  フルスイート **394 PASS + 3 skipped** (385 → +9)、ruff クリーン、回帰ゼロ。

### Added — F15 (t3) mmdc → SVG → ターミナル画像チェイン (2026-05-10)

- **新モジュール `llove.views.mermaid_render`**: Mermaid source を
  `mmdc -i .mmd -o .svg` で SVG 化 → 既存 image renderer chain
  (`chafa` / `viu` / `timg` / `kitty +kitten icat` / `wezterm imgcat`) に
  流すための薄い shim。
  - 公開 API: `MermaidRender` (kind/argv/svg_path/ascii_text dataclass) /
    `mmdc_available()` / `find_image_tool()` / `render_mermaid_to_svg()` /
    `render_mermaid()` / `ascii_fallback()`。
  - **依存性注入**: `mmdc_path` / `image_tool` / `runner` を全部差し替え可能。
    mmdc 未インストールの CI / dev 環境でも全機能テスト可能 (subprocess を
    踏まずに argv 検証ができる)。
  - **Fail-closed**: mmdc の異常終了・出力ファイル欠損・OSError は全て
    ASCII フォールバック (マーカー付きで mermaid source をそのまま表示) に
    降りる。UI が renderer 失敗で落ちることはない。
  - **セキュリティ**: subprocess は list-based argv のみ (shell=True 禁止)。
    入力 source は temp `.mmd` に書き出し、引数経由の長文流入を回避。
- **既存 image catalog (`llove.browser.external`) 再利用**: 画像ツール検出
  は `available_tools("image")` 経由なので、新ツール追加時は catalog 1 行で
  自動的に mermaid renderer も恩恵を受ける。
- **テスト 16 件追加** (`test_mermaid_render.py`):
  検出 (mmdc / image tool) 4 件 / `render_mermaid_to_svg` argv 検証 + 失敗
  パス 5 件 / ASCII fallback 2 件 / 統合 `render_mermaid` 5 件
  (image 成功 / mmdc 欠 / image 欠 / mmdc 失敗 / 自動検出)。
  フルスイート **385 PASS** + 3 skipped、ruff クリーン、回帰ゼロ。

### Added — F15 (u6) Fold ステータス表示 (2026-05-10)

- **`MarkdownView.fold_metrics()` / `fold_status()` 公開 API**:
  - `fold_metrics() -> tuple[int, int]` で `(closed, total)` を返す
    pure 計算メソッド。view が未 feed でも `(0, 0)` を返し raise しない。
  - `fold_status() -> str` で `"fold: 3 closed / 12 total"` の正準
    ステータス文字列を返す。
- **border_subtitle 自動更新**: `_render()` 末尾で
  `self.border_subtitle = self.fold_status()` を呼び、Textual ボーダー
  に常に最新の fold メトリクスが表示される (要件 u6 ステータスバー)。
  Static widget でテスト可 — App mount 不要。
- **テスト 7 件追加** (`test_markdown_view_fold_status.py`):
  未 feed → (0, 0) / total 計数 (h+code 等) / close-all 後 closed=total /
  status 文字列の数値検証 / 空 view の status / `border_subtitle` が
  close_all で更新 / open_all で 0 復帰。
  フルスイート **369 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (t3 prep / u) Mermaid ブロック識別 (2026-05-10)

- ` ```mermaid ... ``` ` フェンスを **`kind="mermaid"` として特別認識**:
  - `find_code_block_regions` 内で info-string が `mermaid` (case-insensitive)
    の場合のみ `kind="mermaid"` でリラベル。それ以外の言語は従来通り
    `kind="code"`。Mermaid と通常 code は同一文書内で共存可能。
  - `apply_folds` summary を kind 別に拡張: mermaid →
    `▶ ◇ mermaid: <label> (N lines)` (◇ で diagram と視覚区別)。
  - `:fold by-tag mermaid` が動作 (hook の valid kind に "mermaid" を追加)。
  - `_preset_prose` を `(code, table, mermaid)` を畳むよう拡張。
    `outline` / `data-only` は predicate 構造上自動的に mermaid も畳む
    (heading 以外 / table 以外を畳むため)。
- 後段で予定する `mmdc` 連携 (要件 t3 の SVG → image チェイン) は
  この識別レイヤを起点にレンダラを差し込めば良い構造。
- **テスト 9 件追加** (`test_folding_mermaid.py`):
  Mermaid 単独 / 通常 code 維持 / 共存 / `close_by_kind mermaid` 限定 /
  summary 書式 / `prose` preset で mermaid 畳み / `data-only` で mermaid
  畳み / MarkdownView.fold_regions に mermaid 含む / `:fold by-tag mermaid`
  ルーティング。
  フルスイート **362 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (u8) `:fold preset` 4 種ルールセット (2026-05-10)

- **プリセット 4 種を folding.py に追加**:
  - `outline` — h1/h2 のみ展開、それ以外 (h3+ / code / table) を畳む
    (文書スケルトンビュー)。
  - `code` — コードブロックのみ展開、それ以外を畳む
    (コードに集中)。
  - `data-only` — テーブルのみ展開、それ以外を畳む
    (データ閲覧)。
  - `prose` — code / table を畳み、見出しは展開のまま
    (プロース読書モード)。
- **`apply_preset(state, regions, name) -> FoldState`** — 純粋関数で
  新しい FoldState を返却。冪等 (二度かけても同じ)。未知名は入力を
  defensive copy して返す (raise しない fail-closed)。
- **`fold_preset_names()`** で正準名一覧 (sorted) を提供。
- **`:fold preset <name>` 動詞** を `_cmd_fold` に追加。引数欠落は
  usage エラー、不正動詞 / 不正名は valid 名列挙でエラー。
- **`make_markdown_fold_hook` に `preset` verb 実装** — 適用後に
  `_render` + `_persist_fold_state` を呼び、永続化と再描画を一括完了。
  `by-tag` も `_persist_fold_state` を呼ぶよう同時修正
  (永続化漏れ修正)。
- **テスト 10 件追加** (`test_fold_presets.py`):
  各プリセットの open/closed 期待 / 不明名 fail-safe / 冪等性 /
  `:fold preset outline` ルーティング / 引数欠落エラー /
  hook 経由の preset 適用 (本物の MarkdownView で last_render 確認).
  フルスイート **353 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (u3) MarkdownView 永続化統合 (2026-05-10)

- **MarkdownView を folding_persistence と統合**:
  - 新コンストラクタ引数:
    `MarkdownView(doc_id="...", fold_persist_dir=...)`
  - `doc_id` 設定時、構築時に `load_fold_state` で前回状態を自動復元、
    `toggle_fold / close_all_folds / open_all_folds` の各 mutation 後に
    `save_fold_state` で自動保存。
  - `save_folds()` を公開メソッドに追加 — `fold_state` を直接いじった
    ケースや app shutdown 時に明示 flush 可能。
  - **Fail-closed (u10)**: I/O 失敗時 (disk full / 権限 / 不正パス等)
    でも view は raise しない。`load` 失敗 → 空 FoldState、
    `save` 失敗 → 黙って続行。UI が状態保存問題で止まらない設計。
  - **doc_id 不正時の安全弁**: `default_fold_state_path` が ValueError
    を投げた場合は内部で握りつぶし、永続化を黙って無効化
    (空 FoldState で起動)。
  - `doc_id` 未指定時は完全にレガシー動作 (永続化フックは何もしない、
    `tmp_path` 等を渡しても書き込まない)。
- **テスト 6 件追加** (`test_markdown_view_persistence.py`):
  close_all → 書込 / 構築時 load → 自動再現 / doc_id 無し → 書込なし /
  toggle 永続性 / `save_fold_state` raise でも view 続行 (monkeypatch) /
  `save_folds()` 明示 flush。
  フルスイート **343 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (u3) Fold 状態永続化 (TOML) (2026-05-10)

- **`llove/views/folding_persistence.py`** を新設:
  - `save_fold_state(state, path, *, doc_id)` — 一時ファイル → rename の
    擬似アトミック書込。親ディレクトリは自動作成。
  - `load_fold_state(path) -> FoldState` — 不在 / 読込不能 / 不正 TOML /
    バージョン不一致のいずれでも空 FoldState 返却 (fail-closed u10)。
  - `default_fold_state_path(doc_id, *, base_dir=None)` — XDG_CONFIG_HOME
    or `~/.config/llove/folds/<sanitised>.toml` を解決。
  - **doc_id サニタイズ**: `[A-Za-z0-9._-]` 以外を `_` に置換し、
    `..` / `/` / `\` 等のパス traversal は単一ファイル名に折り畳む。
    空文字列 / セパレータのみは ValueError。
  - **バージョン管理**: `FOLD_STATE_VERSION = 1`。先方互換不可な変更は
    bump して旧ファイルは無視 (空状態で起動)。
- TOML フォーマット (シンプル, 手書きシリアライザ — 追加依存なし):
  ```toml
  version = 1
  doc_id = "abc-123"
  closed_starts = [0, 5, 12]
  ```
- `llove.views` から `FOLD_STATE_VERSION / default_fold_state_path /
  load_fold_state / save_fold_state` を再エクスポート。
- **テスト 14 件追加** (`test_folding_persistence.py`):
  round-trip / 親 dir 自動作成 / 不在ファイル / 不正 TOML /
  異バージョン無視 / 整数フィルタ / base_dir override /
  doc_id サニタイズ + traversal 防止 / 空 doc_id / 空状態保存。
  フルスイート **337 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (u8) `:fold` コマンドパレット連携 (2026-05-10)

- **F20 ビルトイン `:fold` コマンド** を追加 (`llove/term/builtins.py`):
  - 動詞: `close-all` / `open-all` / `by-tag <kind>` / `toggle <line>`
  - フックパターン: 実体は `ctx.hooks['fold']` の callable に委譲。
    フック未設定時でも verb が正当なら **audit-warn 風通知** に留める
    (F20(i) fail-closed)。フックが verb を扱えない (None 返却) 場合
    のみ ok=False。
  - 不正動詞 / 引数不足は usage エラー + valid 動詞列挙。
  - `:help` 一覧 / `:help fold` 個別ヘルプから探索可能。
  - ビルトイン総数 11 → **12 件**へ。
- **`make_markdown_fold_hook(view)`** factory を追加
  (`llove/views/markdown_view.py`):
  - 1 行で `ctx.hooks["fold"] = make_markdown_fold_hook(my_view)` と
    bind 可能。
  - close-all / open-all / by-tag (`heading|code|table`) /
    toggle <line> をネイティブ実装。整数化失敗時は None 返却で
    ディスパッチャに「動詞非対応」として委ねる。
- **テスト 18 件追加** (`test_fold_command.py` 11件 +
  `test_markdown_fold_hook.py` 7件):
  ビルトイン登録 / usage エラー / 動詞検証 / フック未設定時の挙動 /
  hook の verb 別 dispatch / by-tag 引数 / toggle 整数検証 / 不明 verb /
  E2E (`:fold close-all` → MarkdownView 経由で実 fold 適用).
  既存 `test_builtin_count` を 11→12 へ更新。
  フルスイート **323 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (u) Foldable Blocks コードブロック / 表 fold 拡張 (2026-05-10)

- **コードブロック fold + 表 fold** を folding.py に追加:
  - `find_code_block_regions(source)` — fenced ``` / ~~~ ペアを抽出。
    info-string (例: `python`) を `label` に保持。閉じフェンス無し時は
    fail-closed で空リストを返却 (phantom region 防止)。
  - `find_table_regions(source)` — GFM パイプテーブル
    (header + alignment + 0+ body 行) を抽出。alignment 行が直後に
    ない場合は table と認識しない。code fence 内のテーブルは無視。
    `label` に列数を保持 (`"table (3 cols)"`)。
  - `apply_folds` の summary 書式を kind 別に拡張:
    - `heading` → `▶ ## 見出し (N lines)` (既存)
    - `code`    → `▶ \`\`\`python (N lines)`
    - `table`   → `▶ | table (3 cols) (N rows)`
- **MarkdownView 統合**: `fold_regions()` が見出し + コード + 表を
  すべて返し `start_line` 順にソートして公開。`toggle_fold(line)` /
  `close_all_folds()` は構文種別を意識せず動作 — 1 つのキーバインドで
  あらゆる fold を扱える。
- **テスト 18 件追加** (`test_folding_code_table.py` 13件 +
  `test_markdown_view_code_table_fold.py` 5件):
  単一/複数 fence / 言語ラベル無し / ~~~ fence / 未閉じ fence /
  table 基本 / 列数ラベル / alignment 必須 / fence 内 table 無視 /
  各 kind の summary 書式 / 混在 fold 独立性 / `close_by_kind` /
  MarkdownView 経由の code/table fold 動作 / `close_all_folds` 全 kind 一括.
  フルスイート **305 PASS** + 3 skipped、ruff クリーン。

### Added — F15 (u) Foldable Blocks 見出しセクション折り畳み (2026-05-10)

- **F15 (u) Foldable Blocks**: UI 非依存の純粋データ層
  `llove/views/folding.py` を新設し、MarkdownView に統合。
  - `FoldRegion(kind, level, label, start_line, end_line)` —
    1 つの折り畳み可能な範囲を行番号で指す不変データクラス。
  - `FoldState` — 開閉状態を `closed_starts: set[int]` で管理する
    可変クラス。`toggle / close / open / close_all / open_all /
    close_by_kind` で操作。Vim の `za / zc / zo / zM / zR` 動詞対応。
  - `find_heading_regions(source)` — Markdown ATX 見出し
    (`#`〜`######`) を抽出。**ネスト対応 (u5)**: 外側の見出し範囲は
    同レベル以下の次見出しまで、内側は親に内包される計算。
    code fence (` ``` ` / `~~~`) 内の `#` は誤認しない。
  - `apply_folds(source, regions, state)` — 閉じた範囲を
    `▶ ## 見出し (N lines)` の 1 行サマリに置換 (**u4 spec 準拠**)。
    外側を閉じれば内側ごと吸収、内側だけ閉じれば外側はそのまま。
    fail-closed (u10): 不正入力でも raise せず元文字列返却。
  - **MarkdownView 統合**: `fold_state` プロパティ +
    `fold_regions() / toggle_fold(line) / close_all_folds() /
    open_all_folds()` API を公開。折り畳みは **最新エントリのユーザ
    テキストのみ** に作用し、履歴上の旧エントリは常に展開状態を維持
    (スクロールバック時の文脈喪失を回避)。
    line-number ベースで状態保持しているので、同一ドキュメントの
    再 feed (テーマ切替・幅変更等) でも折り畳みは閉じたまま。
  - `llove.views` から `FoldRegion / FoldState / find_heading_regions /
    apply_folds` を再エクスポート。
  - **テスト 19 件全 PASS** (`test_folding.py` 14件 +
    `test_markdown_view_folding.py` 5件):
    単一/兄弟/ネスト/空/code fence 内、FoldState 開閉、apply_folds
    閉じ動作 / passthrough / 内外ネスト / 不正入力, MarkdownView
    fold API / close_all+open_all / 再 feed 永続性 / 平文段落.
    フルスイート 287 PASS + 3 skipped、ruff クリーン。
  - 次段階: コードブロック / Mermaid / 表 fold (MarkdownView 内拡張) →
    JSON ツリー / ログペイン / Notebook セル fold (F19 / F17 連携) →
    キーバインド (Vim/VSCode 系) → 状態永続化 (~/.config/llove/folds/).

### Added — F15 (t1) MarkdownView 骨組み (2026-05-10)

- **F15 (t1) MarkdownView** (`llove/views/markdown_view.py`):
  - NarrationView (軽量 markdown のみ) の上位互換として `MarkdownView` を新設。
    Rich の `Markdown` バックエンド (markdown-it-py) を経由する **フル GFM**
    レンダラ。見出し / 段落 / 箇条書き / 引用 / fenced code / inline code /
    太字をネイティブにレンダリング。
  - `feed(event)` / `last_render` / NARRATION 専用フィルタ / latest-first 履歴 /
    `limit` 指定など NarrationView と同じ呼び出し契約。
    追加で `last_source` を持ち、最後に渡された生 Markdown を保持
    (テスト・SVG エクスポート・自動 review 用途).
  - 内部で Rich `Console` を文字列バッファに食わせて
    色なしテキストスナップショットを `last_render` に保存
    (ヘッドレス検査と Textual 内ライブ表示の両立).
  - i18n: `ui.pane.markdown.title` / `ui.pane.markdown.empty` を
    ja.toml / en.toml に追加。
  - `llove.views` から `MarkdownView` を再エクスポート。
  - **テスト 12 件 PASS**: 初期状態 / 見出し+段落 / fenced code /
    箇条書き / blockquote / 太字+inline / 非 NARRATION 無視 /
    空文字列無視 / 履歴順序 / limit / title 表示 / 不正 payload。
    フルスイート無回帰。
  - 次段階: コールアウト / 数式 / フットノート / タスクリスト / 絵文字短縮形は
    markdown-it-py プラグイン (mdit-py-plugins) 経由で拡張予定。
    (t2) SVG / (t3) Mermaid / (t4) テーマ / (u) Foldable は順次着手。

### Added — F20 Command Palette UI 骨組み (推奨順 D' 完了, 2026-05-10)

- **D'. F20 Command Palette UI 骨組み** (`llove/term/`):
  - `llove/term/completion.py` — UI 非依存の純粋関数:
    `filter_suggestions` (前方一致優先 + difflib fuzzy fallback),
    `complete_prefix` (Tab 補完で最大共通プレフィックスを返す),
    `HistoryRing` (上下キー履歴, 重複排除 + 上限つき, push/up/down/reset).
  - `llove/term/palette.py` — Textual widget:
    `CommandPaletteWidget` (Input + 候補表示 Static + 出力 Static を 1 つに束ね,
    Enter=submit→dispatch / Tab=補完 / Up,Down=履歴) と
    `CommandPaletteScreen` (Vim ex 風 ModalScreen, Escape で dismiss).
  - 公開 API: `llove.term` から `CommandPaletteWidget` /
    `CommandPaletteScreen` / `HistoryRing` / `filter_suggestions` /
    `complete_prefix` を再エクスポート (Textual 依存は PEP 562 lazy import で
    UI 非依存テストに巻き込まない).
  - 全 29 件 PASS — 純粋関数 23 (filter / complete / HistoryRing) +
    Widget 6 (run_test() による boot / submit / 履歴 / 補完 / 候補表示 /
    Modal 開閉). ruff クリーン. フルスイート 284 PASS + 1 skip 維持.

### Added — F20 Command Palette dispatch core (推奨順 D 完了, 2026-05-10)

- **D. F20 Command Palette 最小骨組み** (`llove/term/`):
  - `Command` / `CommandResult` / `CommandContext` / `CommandRegistry`
    + `parse_line` (Vim ex 風 `:` 接頭辞 + shlex 分割) +
    `dispatch` (alias / macro 入れ子 5 段防止) + `DEFAULT_REGISTRY` +
    `register_command` (F20(f) 動的追加).
  - ビルトイン **11 種** (F20(b)): `:help` `:identity` `:layout`
    `:demo` `:play` `:open` `:peer` `:set` `:get` `:alias` `:macro`.
    副作用は `ctx.hooks` 経由で `apply_layout` / `start_demo` /
    `start_game` / `open_uri` / `peer_call` / `identity_did` を後段配線
    可能 (F20(i) 未配線時は表示のみで fail-closed).
  - 未知コマンドは difflib で似た名前を `suggested` に提案 (F20(i)).
  - UI (Textual `Input` widget, F20(c)③) は別段階で追加予定. このコアは
    UI 非依存・純粋関数で完結.
  - 全 39 件 PASS — parse_line / Registry / dispatch / 11 ビルトイン
    / hook callable 配線 / alias 循環防止. ruff / bandit クリーン.

### Fixed — test_browser PIL import (2026-05-10)

- `pytest.importorskip("PIL")` の戻り値に `PIL.Image` 属性が無い問題
  (Python 3.12+ で `PIL.Image` がサブモジュール扱い) を `importorskip
  ("PIL.Image")` + `from PIL import Image` 形に変更.

### Added — F17 WindowManager / F21 typing / F16 chess (推奨順 A→B→C 完了)

- **A. F17 WindowManager 最小骨組み** (`llove/window/`):
  - `WindowType` ABC + Registry (`register_window_type` / `get` / `list`).
    ビルトイン 5 種 (`data.{sensor_stream,spc_chart,audit_log,narration}`,
    `meta.identity_panel`).
  - `IconSet` 3 段フォールバック: Nerd Font / 絵文字 / ASCII.
    `LLOVE_ICONS` env + ターミナル自動検出. Sixel / Kitty graphics は将来.
  - `FreeContainer` (自由 + / × 可) / `LockedContainer` (remove 拒否).
  - `WindowManager` + `WindowLayout` / `WindowSpec` (F17(r) シナリオ駆動
    レイアウト) + `to_toml` / `from_toml` で `layout.toml` 往復.
  - 全 20 件 PASS.
- **B. F21 タイピングデモ** (`llove/games/typing/`):
  - `TypingEngine` (F16 GameEngine 継承、1-player). ミスタイプは
    `LegalityResult ok=False` で試行カウントのみ加算 (状態は進めない).
    目標単語数到達で `TermReason.SCORE` 終局.
  - `MockWordSource` + 同梱 `BUILTIN_GENRES` 8 種 (programming-rust /
    programming-llmesh-api / shogi-koma / llmesh-did / multilingual-ja-en
    / math-symbols / unix-commands / common-english).
  - 全 17 件 PASS.
- **C. F16 chess 最小実装** (`llove/games/chess/`):
  - `ChessEngine` — python-chess (MIT 14k★) の薄いラッパ. UCI 形式の
    Move.notation、`is_legal` で en passant / castling / promotion /
    pinned / discovered check / 50-move / threefold すべて委譲.
  - `[chess]` extras 追加 (コア依存ではない).
  - `is_terminated` で CHECKMATE / STALEMATE / REPETITION / DRAW
    (insufficient material / fifty-move rule).
  - 全 12 件 PASS — Fool's Mate 4 手詰み + 構成 stalemate FEN 検証.

### Added — shogi MVP2a + llmesh identity AUDIT + F15/F16 roadmap

- **`llove play shogi`** CLI: real game loop between two `Player`
  instances. `--no-tui` for JSONL stdout, default TUI mode supports
  `--stream`. Auto-logs to `out/shogi/play-<ts>.jsonl`.
- **`llove/shogi/`** package: thin `Engine` over `python-shogi`
  (`[shogi]` extras, GPL-3.0 isolated), async `Player` ABC, `MockPlayer`
  variants (`script` / `illegal` / `resign`), and `run_game` loop
  enforcing 3-strike forfeit, mate / sennichite / max-ply termination.
- **Per-move Ed25519 signing** is now part of the spec. Each move signs
  canonical bytes `"{ply}|{side}|{usi}|{sfen_after}"`.
- **`llove.identity`** + `LoveApp` first-event: every demo's leading
  AUDIT carries the local llmesh `did:key`. Discovery walks env →
  `D:/projects/llmesh/config` → `~/.llmesh` → XDG → llmesh SDK. Missing
  identity nudges to `pip install llmesh-mcp` (en/ja).
- `tests/test_identity.py`, `tests/test_shogi_engine.py`,
  `tests/test_shogi_loop.py` — 24 new cases, full suite green.

### Added — F15 / F16 / design principle (REQUIREMENTS + ROADMAP)

- **F15: Browser-grade Display** (v0.6.0). Image / PDF / table / chart /
  geo / 3D / audio / video / HTML / JSON, with: external CLI tools
  allowed (chafa / pdftoppm / mpv / gnuplot / w3m), multi-renderer
  choice in a settings modal, Qt as first-class fallback, unified 2D /
  3D viewer base (camera + pan/zoom/rotate). HTML and video are
  roadmap items; video is the very last step.
- **F16: Multi-Game LLM Arena** (v0.7.0). chess / go / mahjong / poker /
  bridge / hanafuda / 大富豪 / blackjack on the same `Engine + Player +
  Loop + Provider` abstraction.
- **2.1.1 Design principle**: *llmesh stays simple, llove does the
  presentation* — SFEN / USI / sensor floats / did:key on the wire,
  kanji pieces / colours / Sixel / themes in llove.

### Added — `shogi` scenario (MVP1 complete)
- 17th demo scenario (`llove demo --scenario shogi`). Two LLMs replay a
  scripted 20-half-move game (Yagura opening + 2-file / 8-file pawn
  trades) on a shared 9x9 board. Designed as the prototype for MVP2's
  real-LLM duel.
- **Kanji pieces with side colouring** — sente in default colour, gote
  in `[bright_red]`. Same glyph for both sides except the king:
  traditional Shogi distinction `先手 = 玉` / `後手 = 王`.
- **Captured-piece hands** — header above the board shows gote's
  captured hand, footer below shows sente's. Real captures fire during
  the mid-game extension so the rendering is exercised, not just
  decorative.
- **Traditional kifu in the audit pane** — moves render as
  `▲７六歩 (2.4秒)` / `△３四歩 (1.8秒)`. Per-move thinking time is
  carried in the Event payload (`thinking_ms`) and surfaces in the
  audit line and the JSONL log.
- **Player identity line** — intro narration and the first audit entry
  state who is playing whom (currently `LLM-A (mock · MVP1)` vs
  `LLM-B (mock · MVP1)`; MVP2 will fill these from the actual model
  handles).
- **Half-move board updates** — narration pane re-renders after every
  ply, like a real shogi broadcast.
- Unit tests in `tests/test_shogi.py` cover `_apply` capture
  bookkeeping, `_format_hand` ordering, `_usi_to_kifu` variants
  (promotion / sub-second timing / 王・玉 split), and an integration
  test that asserts the default 20-move script actually produces
  captured pieces on both sides.

### Added — engine plumbing
- **`mindmap` scenario** — LLM expands a seed query (`What is LLMesh?`)
  into a knowledge tree via BFS. SPC alarm on breadth runaway.
- **`coin_toss` scenario** — entry-level student demo: 50 tosses of an
  early-biased coin → Law of Large Numbers settling near 0.5.
- **Per-scenario pane title overrides** — `DemoScenario` exposes
  `sensor_pane_title_key` / `spc_pane_title_key` / `audit_pane_title_key`
  / `narration_pane_title_key`. `LoveApp.on_mount` resolves them through
  the i18n catalog and rewrites each pane's `border_title`, so
  non-LLMesh-flavoured demos read naturally (coin_toss shows
  "🪙 Toss outcomes"; shogi shows "♟ 盤面" / "📋 棋譜" / "📊 評価" /
  "💬 解説").
- **Per-scenario layout overrides** — `DemoScenario` now also exposes
  `narration_pane_height` / `narration_max_entries` / `audit_pane_height`
  / `audit_max_entries`. shogi uses these to grow the board narration
  to 55% of the window with `max_entries=1` (pinned to the latest
  position) and the kifu pane to 32% with 30 lines of scrollback.
- **AuditLogView display override** — `payload['display']` (when
  present) replaces the default `Event.short()` line. shogi uses this
  to show the kifu string without changing the audit format for any
  other scenario.
- **NarrationView Rich-markup parsing** — feed runs the rendered string
  through `Text.from_markup` so colour tags (`[bright_red]` etc.) make
  it through to the SVG export instead of getting collapsed into the
  default-colour class. `narrate(allow_rich=True)` lets a scenario opt
  out of the default `[` escape.
- **Reset = "play from ply 1"** — pressing `r` on a `DemoScenario` now
  cancels the consume task, clears the views, re-instantiates the
  scenario, truncates any active event log, and starts a fresh consume
  task. Arbitrary `DataSource` subclasses still get the old "views
  only" reset so a JSONL tail-follow doesn't restart the file from
  line 1.
- **`--log <path>` JSONL event log** — every dispatched Event is
  appended as one JSON line to the path. `llove tail` can replay it.
  For `--scenario shogi` the log path is auto-assigned to
  `out/shogi/shogi-<UTC timestamp>.jsonl` so you don't have to remember
  the flag (explicit `--log` still wins).
- **`scripts/snapshot_scenario.py`** — Pilot-driven SVG snapshot tool
  for reviewing TUI presentation quality without launching a real
  terminal. Patches in a CJK-aware monospace font fallback chain
  (`MS Gothic` / `BIZ UDGothic` / `Noto Sans Mono CJK JP` / …) and
  injects `lengthAdjust="spacingAndGlyphs"` on every `<text>` so
  Japanese glyphs can't overlap when the viewer picks a proportional
  fallback. `scripts/_inspect_shogi.py` is the matching diagnostic.

### Changed
- **`cost` scenario** — also yields a `daily_cost_usd` SENSOR event per
  LLM call so the SensorStream pane displays a clear running total
  alongside the LLM_CALL audit entries (was: SensorStream stayed empty).
- **i18n header** — `ui.pane.sensor_stream.header` swapped
  `sensor` / `センサー` → `metric` / `指標` so non-LLMesh demos read
  naturally.

### Process
- Per [feedback_scenario_iterative]: each new scenario must pass
  real-terminal (or Pilot SVG) review before its release commit, not
  just the smoke test.
- New [REQUIREMENTS](REQUIREMENTS.md) **F9** (per-scenario quality
  bar), **F11** (student-friendly demos), **F12** (`shogi` 4-MVP plan,
  now staged as **MVP2a / MVP2b / MVP3 / MVP4** — see
  [ROADMAP.md](ROADMAP.md)), **F13** (webcam + image-LLM demo),
  **F14** (mic + voice-LLM demo).

## [0.2.2] - 2026-05-09

### Changed
- **PyPI distribution name renamed** `llove` → **`llmesh-llove`** to match the
  LLMesh ecosystem convention (`llmesh-mcp`). The `llove` PyPI name was too
  similar to existing PyPI projects and could not be registered.
  - **Install**: `pip install llmesh-llove` (was `pip install llove`).
  - **Import** is unchanged: `import llove`.
  - hatch `packages = ["llove"]` keeps the import path stable.

### Fixed
- `NarrationView.feed` no longer crashes on event titles that contain `[`.
  Hypothesis caught a falsifying example (`title='[@=:'`) where the title
  was assigned to `border_subtitle` without escaping, and Textual's markup
  parser raised `MarkupError`. Same defensive `\[` escape that already
  protected `safe_title` is now also applied to `latest`.

### Added
- **`vision` scenario** — VLM-based belt-conveyor inspection across 7 ASCII
  frames. Two frames trigger an SPC defect alarm with a bounding-box payload
  and a "surface_contamination" audit entry.
- **`pointcloud` scenario** — 4-frame LiDAR top-view of a 4x3 parts tray. The
  top-right slot empties for two frames; SPC fires on density drop and the
  audit summary nails which (col, row) is missing.
- **Standalone Qt viewers** under `tools/qt_viewer/`:
  - `vision_viewer.py` upscales each frame to a pixmap (or decodes
    `image_b64` if present) and overlays bounding boxes from SPC_ALARM events.
  - `pointcloud_viewer.py` projects the raw `points_xyz` payload to a 2D
    scatter and highlights the missing slot. Both have a frame slider.
  - Tools require `pip install PySide6` — **not** a llove dependency.
- Total demo scenarios now **14** (was 12 in 0.2.1).

### Changed
- `vision` and `pointcloud` Event payloads carry rich data
  (`image_b64`, `image_ascii`, `points_xyz`, `topview_ascii`, `bbox`,
  `missing_slot`) so external pipelines can consume the same stream and
  render their own way without re-running the scenario.

## [0.2.1] - 2026-05-09

### Fixed
- **`llove demo --list`** previously rendered `<property object at 0x...>`
  instead of each scenario's title. `SCENARIOS` stores classes and v0.2.0
  turned `title` / `description` into `@property`, so `cls.title` returned
  the property descriptor. The list view now instantiates each scenario
  before reading its localized title and description.
- Regression tests added: title resolves to a real string, no
  `<property object` leaks in either `en` or `ja`.

### Changed
- `demo --list` now also prints the scenario description on a second line.

## [0.2.0] - 2026-05-09

### Added
- **Internationalisation (i18n)**: TOML-driven locale catalog under
  `llove/i18n/locales/`. Ships `en` (default) + `ja`. Active locale chosen
  from `--lang` flag, `LLOVE_LANG` env, system locale, fallback `en`.
- `Translator` class + module-level `t()` and `set_locale()` helpers.
- `--lang` flag on the CLI (`llove --lang ja demo --scenario scada`).
- `docs/i18n.md` contributor guide.
- Per-locale SVG snapshots: `docs/snapshots/{en,ja}/*.svg`.
- **HelpScreen modal**: clicking `? Help` (or pressing `h`) opens a modal
  with key bindings, button explanations, pane summary, and the
  Footer-is-clickable tip. Prominent yellow line at the top:
  *"Press ESC (or h / q / Close button) to return."*
- **Read-only badge** on every pane: ` · 📖 read-only` /
  ` · 📖 読み取り専用` so the bordered panes are not mistaken for
  clickable controls.
- **Hint bar** between buttons and panes:
  *"↑ buttons = clickable controls · ↓ panes = read-only data displays"*.
- **Click-feedback for control row** (Pause / Reset / Help / Quit) wired
  to `on_button_pressed` so mouse and keyboard share the same actions.
- **Pause button label flips** between `⏸ Pause` and `▶ Resume`.
- **Counter subtitles** on every pane (event count / alarm count /
  audit·llm·rag splits / scenario beat counter).
- `SensorStreamView` now prepends a `time / sensor / value` column header
  and labels the sparkline.

### Fixed
- **Help button** previously rang the bell only — now opens HelpScreen.
- **Quit button** was a silent no-op (sync handler was discarding the
  async coroutine returned by `App.action_quit`). Now uses a sync
  `action_quit_now()` that calls `self.exit()` directly.
- **Reset button** previously cleared internal state but never told the
  widgets to redraw. Now also zeros per-view counters and calls
  `view.update()` to repaint.
- **NarrationView** title escaping: user-supplied `[` in title is now
  escaped to `\[` so Rich tags from data cannot break out.
- **SensorStreamView** drops NaN/Inf values (sparkline normalisation
  used to crash on them).
- **`temp` → `temperature` / `温度`** normalisation across narration
  copy (the abbreviation was ambiguous as sample code).

### Changed
- Pane titles now end with `· 📖 read-only` (was `· view`).
- `DemoScenario` resolves `title` / `description` lazily through i18n
  (`scenario.<key>.title`) instead of class attributes, so locale
  switching at runtime takes effect without re-instantiation.
- Every shipping scenario now uses `narrate_key()` / `t()` instead of
  hardcoded strings; all narration text lives in TOML.

### Quality
- Coverage 91.7%+ (CI threshold raised 70 → 80 in v0.1).
- Stricter ruff ruleset (E/F/W/I/B/UP + SIM/RUF/PTH/PLE) — clean.
- Bandit clean across all severities.
- Hypothesis property-based tests (event roundtrip, JSONL fail-closed,
  narration tag-injection safety, MockSource determinism).
- Robustness tests for malformed input.
- Textual `run_test()` pilot tests for LoveApp (boot, key bindings,
  pause/resume, reset, quit, fail-closed dispatch).

## [0.1.0] - 2026-05-09

Initial public release.

### Added
- **CLI**: `llove demo / tail / export / version` (Click-based).
- **Textual TUI app** with 3 default panes (SensorStream / SPCChart / AuditLog) plus an optional NarrationView for demo scenarios.
- **DataSource ABC** with built-in implementations: `MockSource` (deterministic synthetic), `JSONLSource` (file or tail-follow).
- **View ABC** with built-in widgets: SensorStreamView, SPCChartView, AuditLogView, NarrationView.
- **HTML export**: `llove export --html` writes a single self-contained HTML snapshot (Claude HTML Artifacts inspired).
- **7 LLMesh-coverage demo scenarios**:
  - `firewall` — PromptFirewall L0/L1/L1.5/L2 layered screening
  - `scada` — ExplainedCUSUM + LLMExplainer drift detection
  - `multimodal` — UnifiedSPC + VLMFeatureExtractor (sensor + caption fusion)
  - `rag` — Numpy / SQLite / LSH ANN store comparison
  - `backends` — Ollama / OpenAI / Anthropic backend comparison
  - `audit` — AuditTrail HMAC-chain tamper detection walkthrough
  - `reliability` — MessageAssembler + ChunkSender packet-loss recovery
- **Contributor template**: `llove/demo/scenarios/_template.py` + `docs/contributing-scenarios.md` for adding new scenarios in ~5 minutes.
- **Dev environment**: `.devcontainer/`, `docker-compose.yml`, GitHub Actions CI matrix (ubuntu/macos/windows × py3.11/3.12).
- **Static analysis**: ruff (strict ruleset including SIM/RUF/PTH/PLE) + bandit (all severities, project-policy skip list documented).
- **Tests**: 60 tests including:
  - Unit tests for events, sources, views, CLI
  - Robustness tests (NaN/Inf/None/oversized input fail-closed)
  - Hypothesis property-based tests (event roundtrip, JSONLSource on arbitrary input, narration tag-injection safety, MockSource determinism)
  - Textual `run_test` pilot tests for the App
- **Coverage**: 91.87% (CI threshold: 80%).

### Security & robustness
- Narration pane neutralises user-supplied Rich tags by escaping `[`.
- SensorStreamView drops NaN/Inf values to prevent sparkline rendering errors.
- JSONLSource is fail-closed: arbitrary input never raises.
- HTML export is self-contained (no CDN, no external assets) so snapshots are safe to share offline.

### LLMesh integration
- LLMesh side ships `llmesh.export.LloveJSONLExporter` — a stdlib-only bridge that writes data in llove's JSON Lines format. Pipe with: `with LloveJSONLExporter("snapshot.jsonl") as ex: ex.feed_sensor_event(ev)` then `llove tail snapshot.jsonl`.
