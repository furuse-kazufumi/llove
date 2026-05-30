# llove TUI レイアウト凡例

> **かみ砕いた説明**: このページは、llove のデモ画面を撮った SVG スクリーンショットの「見方の地図」です。画面のどこがクリックできるボタンで、どこが表示専用のパネルなのかを枠線とアイコンで示し、各部品が何を表すかを一覧にしています。スクリーンショットを見ながら、どこを触れて何が読み取れるかを理解するための凡例(はんれい)です。
>
> 用語の詳しい説明は[用語集(GLOSSARY.md)](../GLOSSARY.md)を参照してください。

各シナリオ(scenario)の SVG スクリーンショット（`*-tui.svg`）は次の構造を持っています。
**何がクリックでき、何が表示専用か** を視覚的に分けることを最優先にしました。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header — 💗 llove · clock                                                   │  ← Textual 標準ヘッダ
├─────────────────────────────────────────────────────────────────────────────┤
│ [⏸ Pause] [⟲ Reset] [? Help] [✕ Quit]                                       │  ← クリック可能なボタン行
├─────────────────────────────────────────────────────────────────────────────┤
│ ↑ buttons = clickable controls · ↓ panes = read-only data displays         │  ← ヒントバー
├──────────────────────────────────────┬──────────────────────────────────────┤
│ 📡 SensorEvent stream  · view        │ 📊 SPC chart — CUSUM control · view  │
│   time      sensor      value        │   ● status: nominal (value=70.13)    │
│   12:34:56  bearing_07  70.13        │   Recent alarms:                     │
│   ...                                │     12:34:58  ALARM bearing_07       │
│   sparkline (last 40): ▁▂▃▄▅▆▇       │   ...                                │
├──────────────────────────────────────┴──────────────────────────────────────┤
│ 📋 Audit log — audit / LLM / RAG events  · view                             │
│   12:34:59  audit  cusum.alarm                                              │
│   12:34:59  llm_call  tokens=237  latency=412ms                             │
│   ...                                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ 💬 Narration — what's happening, in plain words  · view                     │
│   12:34:55  Phase 1                                                         │
│     Phase 1 — normal: reading hovers around 70 °C                          │
│   ...                                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ q Quit · r Reset · space Pause/Resume · h Help                              │  ← Footer（クリック可、各キーは下線付き）
└─────────────────────────────────────────────────────────────────────────────┘
```

## 識別ルール（凡例）

| 要素 | 見分け方 | 操作 |
|---|---|---|
| **Header** | 一番上の細い帯、時計付き | 表示のみ |
| **Button 行** | 角丸塗り潰しの矩形（Pause/Reset/Help/Quit） | **クリック可** |
| **Hint バー** | 1 行の薄文字 | 表示のみ |
| **囲み枠 + 📡/📊/📋/💬 アイコン + `· view` バッジ** | パネル | **表示のみ**（read-only） |
| **Footer** | 一番下の帯、`q Quit` のように key + label | キー押下 or **クリック可** |

## ペインごとの中身

### 📡 SensorEvent stream  · view
直近 12 件のセンサー読み取り(SensorEvent(センサーイベント))をストリーム(stream)として時系列で表示するビュー(view)。`time / sensor / value` の 3 列。
最下行に直近 40 件の sparkline。Subtitle: `<count> pts | latest <value>`。

### 📊 SPC chart — CUSUM control  · view
統計的工程管理(Statistical Process Control, SPC)チャートの状態バナー（**nominal** / **ALARM**）と直近 6 件の累積和(Cumulative Sum, CUSUM) alarm。
Subtitle: 累計 alarm 件数。

### 📋 Audit log — audit / LLM / RAG events  · view
監査証跡(Audit / AuditTrail)/ LLM call / 検索拡張生成(Retrieval-Augmented Generation, RAG) hit / info を新しい順に流すロール。
Subtitle: `audit:N · llm:N · rag:N` の小計。

### 💬 Narration — what's happening, in plain words  · view
demo シナリオ実行中のみ表示。Markdown 風（`**bold**` / `` `code` ``）。
Subtitle: `beat <n> · <latest title>`。

## キーボードとマウスの対応

| 操作 | キー | マウス |
|---|---|---|
| Pause / Resume | `space` | `[⏸ Pause]` ボタン |
| Reset | `r` | `[⟲ Reset]` ボタン |
| Help | `h` | `[? Help]` ボタン |
| Quit | `q` | `[✕ Quit]` ボタン |

Footer の `q Quit` のような key + label もクリックで発火します（Textual 標準）。

## SVG ファイル一覧

| シナリオ | ファイル | カバーする LLMesh 機能 |
|---|---|---|
| firewall | `firewall-tui.svg` | PromptFirewall L0/L1/L1.5/L2 |
| scada | `scada-tui.svg` | ExplainedCUSUM + LLMExplainer |
| multimodal | `multimodal-tui.svg` | UnifiedSPC + VLMFeatureExtractor |
| rag | `rag-tui.svg` | RAG 3 ストア比較 |
| backends | `backends-tui.svg` | LLM backend ABC |
| audit | `audit-tui.svg` | AuditTrail HMAC chain |
| reliability | `reliability-tui.svg` | MessageAssembler + ChunkSender |

各 SVG は GitHub 上で開けば実際のレイアウト（色付き）が確認できます。
