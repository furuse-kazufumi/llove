# Changelog

All notable changes to **llove** are recorded here.
This project follows [Semantic Versioning](https://semver.org).

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
