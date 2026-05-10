# Changelog

All notable changes to **llove** are recorded here.
This project follows [Semantic Versioning](https://semver.org).

## [Unreleased] — 0.3.0a1 in progress

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
