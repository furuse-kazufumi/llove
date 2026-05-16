---
layout: default
title: "Demo Scenarios — SVG Gallery"
nav_order: 5
---

# Demo Scenarios — SVG Gallery

llove は TUI dashboard としての見え方を、各シナリオに **SVG スクリーンショット**
として階層的に commit していく方針。

階層レイアウト:

```
docs/scenarios/svg/
├── audit/
│   ├── ja.svg
│   └── en.svg
├── chat/
│   ├── ja.svg
│   └── en.svg
...

docs/scenarios/anim/      ← animated SVG (動きがあるシナリオ)
├── shogi.svg
├── mindmap.svg
...
```

各 SVG は Textual の `App.export_screenshot()` で出力された **ベクター形式**
(ターミナル非依存)、GitHub Pages からそのまま見られます。

## 取得手順 (ユーザがローカルで実行)

```bash
# 全 scenario × ja/en を docs に書き出し (公開用)
py -3.11 scripts/snapshot_all_scenarios.py --out=docs/scenarios/svg --overwrite

# 単一 scenario の単一言語
py -3.11 scripts/snapshot_scenario.py firewall ja docs/scenarios/svg/firewall/ja.svg

# 全 scenario × ja/en を out に書き出し (実行ログ、gitignore 対象)
py -3.11 scripts/snapshot_all_scenarios.py
# → out/scenarios/<name>/<lang>.svg

# Animated SVG (動きがあるシナリオ向け)
py -3.11 scripts/export_demo_anim_svg.py --scenario=shogi --frames=8
```

## Animated Gallery (動きがあるシナリオ)

時間軸を持つシナリオは **animated SVG** で動きを残しています。

### Shogi (将棋 8 フレーム × 1.5s = 12 秒ループ)

<img src="anim/shogi.svg" alt="shogi animation" width="100%">

### Mindmap (6 フレーム × 1.5s = 9 秒ループ)

<img src="anim/mindmap.svg" alt="mindmap animation" width="100%">

### RAG (6 フレーム × 1.5s = 9 秒ループ)

<img src="anim/rag.svg" alt="rag animation" width="100%">

### Chat (6 フレーム × 1.5s = 9 秒ループ)

<img src="anim/chat.svg" alt="chat animation" width="100%">

### Benchmark (6 フレーム × 1.5s = 9 秒ループ)

<img src="anim/bench.svg" alt="bench animation" width="100%">

再生成: `py -3.11 scripts/export_demo_anim_svg.py --scenario=<name> --frames=N --frame-delay=S`

---

## Static Gallery (各 scenario × 言語)

各 scenario のディレクトリに `ja.svg` / `en.svg` を配置。Textual の
CJK font fallback chain で日本語表記が崩れないよう対策済。

### Audit
| ja | en |
|---|---|
| ![](svg/audit/ja.svg) | ![](svg/audit/en.svg) |

### Backends
| ja | en |
|---|---|
| ![](svg/backends/ja.svg) | ![](svg/backends/en.svg) |

### Benchmark
| ja | en |
|---|---|
| ![](svg/bench/ja.svg) | ![](svg/bench/en.svg) |

### Chat
| ja | en |
|---|---|
| ![](svg/chat/ja.svg) | ![](svg/chat/en.svg) |

### Coin Toss
| ja | en |
|---|---|
| ![](svg/coin_toss/ja.svg) | ![](svg/coin_toss/en.svg) |

### Cost
| ja | en |
|---|---|
| ![](svg/cost/ja.svg) | ![](svg/cost/en.svg) |

### Drift
| ja | en |
|---|---|
| ![](svg/drift/ja.svg) | ![](svg/drift/en.svg) |

### Firewall
| ja | en |
|---|---|
| ![](svg/firewall/ja.svg) | ![](svg/firewall/en.svg) |

### MCP Call
| ja | en |
|---|---|
| ![](svg/mcp_call/ja.svg) | ![](svg/mcp_call/en.svg) |

### Mindmap
| ja | en |
|---|---|
| ![](svg/mindmap/ja.svg) | ![](svg/mindmap/en.svg) |

### Multimodal
| ja | en |
|---|---|
| ![](svg/multimodal/ja.svg) | ![](svg/multimodal/en.svg) |

### Point Cloud
| ja | en |
|---|---|
| ![](svg/pointcloud/ja.svg) | ![](svg/pointcloud/en.svg) |

### RAG
| ja | en |
|---|---|
| ![](svg/rag/ja.svg) | ![](svg/rag/en.svg) |

### Reliability
| ja | en |
|---|---|
| ![](svg/reliability/ja.svg) | ![](svg/reliability/en.svg) |

### SCADA
| ja | en |
|---|---|
| ![](svg/scada/ja.svg) | ![](svg/scada/en.svg) |

### Shogi
| ja | en |
|---|---|
| ![](svg/shogi/ja.svg) | ![](svg/shogi/en.svg) |

### Vision
| ja | en |
|---|---|
| ![](svg/vision/ja.svg) | ![](svg/vision/en.svg) |

## 設計上のメモ

- `App.save_screenshot()` / `App.export_screenshot()` は Textual 標準機能、
  ターミナル非依存の SVG を生成
- LLM 呼び出しを必要とする scenario (chat / multimodal) は `MockBackend` 前提
- `--pause` (snapshot) / `--delay` (animated) は scenario が描画を開始するまでの時間
- 日本語の文字化け回避: `snapshot_scenario.py` の `_patch_cjk_fonts()` で
  Fira Code → CJK monospace fallback chain を SVG 内に injection
- 階層化前の flat ファイル (`out/snap-*-*.svg`) は手作業 review 資産として残置

## 関連

- `scripts/snapshot_scenario.py` — 単一 scenario × 言語
- `scripts/snapshot_all_scenarios.py` — 全 scenario × 全言語の wrapper
- `scripts/export_demo_anim_svg.py` — animated SVG (N frame 連結)
- `llove/demo/scenarios/` — 全 scenario の実装
- `llove/app.py` — `LoveApp` (Textual ベース TUI)
