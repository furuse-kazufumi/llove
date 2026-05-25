# llove — Project Instructions

> TUI dashboard / HITL workbench (Textual ベース)。SVG/Mermaid/Markdown を端末で再現。
> LLM 対局アリーナ (chess/go/mahjong/poker) 等の SNS 拡散性デモを内蔵。
> FullSense ファミリーの一員。

このファイルは Claude Code 等の AI 実装支援環境に対する指示書。

## FullSense プロジェクト優先度 (全 proj 共通)

本プロジェクトは FullSense (umbrella: llmesh / llive / llove + portal/記事) の構成要素。
全プロジェクト横断の優先度は **FullSense > llive > llmesh > llove > その他**
(2026-05-23 ユーザー確定)。FullSense=全 proj マスター進捗。進捗把握が曖昧な場合は
**FullSense 側を優先** (単一の真実)。プロジェクト間の結合 (要素統合) 判断はユーザーが
行い、勝手に結合しない。単一ソース: raptor `claude-projects.json` の `_priority` /
memory `feedback_fullsense_project_priority`。

## Project Identity

- **Name**: llove
- **PyPI**: `llmesh-llove`
- **Path**: `D:/projects/llove/`
- **役割 (FullSense 内)**: 表現の consumer (animated SVG / manga-SVG / llive panel /
  記事埋込)。FullSense 実装キュー #6 (llove animated SVG B/C/D)。

> product 固有の開発規約・アーキテクチャ詳細は今後ここに追記する (現状は優先度周知のみ)。
