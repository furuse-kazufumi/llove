# One terminal pane for "watching LLMs on the shop floor" — llove

> Designing and shipping `llmesh-llove`, the Artifact terminal for LLMesh.
> I'm betting on a quiet, very specific niche: **observing LLMs × industrial IoT, cutely, from a terminal.**

## Why I started

LLM dashboards usually mean Streamlit, Grafana, or a fresh web UI. But regulated environments, offline sites, and SRE control rooms share a different set of constraints:

- Some terminals must not — or cannot — run a browser.
- You want to see "what's happening *now*" in seconds, over SSH.
- Heavy GUI lag and over-animation actually get in the way of operational decisions.
- Logs / traces / SPC / RAG / audit should sit on **one shared timeline**, on one screen.

`llove` is my personal attempt to solve this in **one terminal pane**. It observes LLMesh data (SensorEvent / SPC / RAG / Audit / Trace) inside a Textual-based TUI, and the entire layout is user-defined via TOML — same view over SSH, on the floor PC, or on a dev workstation.

## The 8 design pillars

1. **TUI-first** — Textual today, Rust acceleration on the roadmap. No browser needed, SSH-friendly, sub-second response on thin links.
2. **Everything via layout.toml** — SDI/MDI switching, free-form panes, locked persistent panes, multi-display. Think "Qt-ADS, but for the terminal."
3. **Browser-grade rendering (F15)** — Markdown / SVG / Mermaid / images / folding / themes, all in the terminal. Five visibility pillars.
4. **Multi-game LLM arena (F16)** — chess / go / mahjong / poker / connect4… all played through the **same abstraction**. Useful for comparing LLM strategies.
5. **"LLM × human collaboration" demos** — typing, Tetris, etc. Tiny educational samples (~200 LOC), strong SNS-shareability, great for evangelism.
6. **Embedded scripting + IDE mode (F19)** — Python / Lua / Starlark / Janet / JS. Helix / Kakoune / Neovim feel.
7. **PowerShell-compatible shell + Claude Code integration (F23/F24)** — a differentiation axis for in-the-field operational tooling.
8. **F25 family integration** — `llmesh` brokers `llove ↔ llive` over MCP. BWT, route traces, memory links — all observable in TUI.

## Why this matters for my career

Flashy web UIs look great on a CV; **operational ergonomics** is a deeper problem. Building `llove` left me with quieter, durable strengths:

- I went deep on **TUI in the web-everything era** — that intuition pays off in SRE-style, control-room, and shop-floor work where SSH is a way of life.
- I designed a **Textual + tree-sitter + LSP** stack to deliver IDE-grade operations inside a terminal.
- I built **layout.toml-centric** UX so the user genuinely *owns* their interface.
- I wired a **multi-game LLM arena** that puts comparison, observation, and education on one abstraction.
- I codified a **family-design principle**: keep the backend minimal, concentrate "presentation craft" on the TUI side.

These talents punch above their weight in dev-tools, ops-tools, DevRel, and EUC-adjacent careers.

## Where it stands today (2026-05-14)

- **v0.6+** in active development. F15 (browser-grade rendering), F16 (LLM arena), F17 (window-management foundation), F19 (embedded scripting + IDE), and F25 (llmesh × llive bridge) being delivered in stages.
- **716 PASS + 1 skipped** (including 105 F25 tests), ruff clean.
- PyPI: `pip install llmesh-llove` (v0.2.2 published, v0.3.0a1 in flight).

## Where it's going

`llove` is the visualisation layer of a stack that pairs `llmesh` (on-prem MCP hub) with `llive` (self-evolving modular-memory LLM) to deliver **LLM × industrial-IoT observation in a single terminal pane**. If you've ever wanted to take TUI seriously, or to *own* your operational tooling, give it a try.

> GitHub: <https://github.com/furuse-kazufumi/llove>
> PyPI: `pip install llmesh-llove`

#AI #LLM #TUI #Textual #DeveloperTools #SRE #IndustrialIoT #OpenSource #IndieHacker #Career
