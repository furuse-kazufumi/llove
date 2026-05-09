# Changelog

All notable changes to **llove** are recorded here.
This project follows [Semantic Versioning](https://semver.org).

## [Unreleased]

### Added
- **`mindmap` scenario** — LLM expands a seed query (`What is LLMesh?`)
  into a knowledge tree via BFS. Each node is emitted as a TRACE_SPAN;
  when tree breadth crosses 12 an SPC alarm fires. Final tree renders
  as a Unicode-tree outline in the narration pane.
- **`coin_toss` scenario** — entry-level student demo: 50 tosses of an
  early-biased coin, watch the heads ratio settle near 0.5 (Law of
  Large Numbers). Bilingual narration with mile-marker comments.
- **Per-scenario pane title overrides** — `DemoScenario` now exposes
  `sensor_pane_title_key` / `spc_pane_title_key` / `audit_pane_title_key`
  / `narration_pane_title_key`. `LoveApp.on_mount` resolves any set keys
  through the i18n catalog and rewrites the matching pane's
  `border_title`, so non-LLMesh-flavoured demos can read naturally
  (e.g. coin_toss now shows "🪙 Toss outcomes" instead of
  "📡 SensorEvent stream").
- **`scripts/snapshot_scenario.py`** — Pilot-driven SVG snapshot tool
  for reviewing TUI presentation quality without launching a real
  terminal. Patches in a CJK-aware monospace font fallback chain
  (`MS Gothic` / `BIZ UDGothic` / `Noto Sans Mono CJK JP` / …) and
  injects `lengthAdjust="spacingAndGlyphs"` on every `<text>` so
  Japanese glyphs cannot overlap when a viewer falls back to a
  proportional font.

### Changed
- **`cost` scenario** — also yields a `daily_cost_usd` SENSOR event
  per LLM call so the SensorStream pane displays a clear running total
  alongside the LLM_CALL audit entries (was: SensorStream stayed empty).

### Process
- Per [feedback_scenario_iterative]: from now on, each new scenario must
  pass real-terminal (or Pilot SVG) review before its release commit,
  not just the smoke test.
- New [REQUIREMENTS](REQUIREMENTS.md) **F9** (per-scenario quality bar),
  **F11** (student-friendly demos), **F12** (`shogi` two-LLM + human
  duel scenario, planned in 4 MVPs); see ROADMAP.md "v0.2.x" section.

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
