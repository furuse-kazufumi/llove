"""llove.games — F16 マルチゲーム LLM 対局アリーナの共通骨格と各ゲーム実装.

llove は将来 chess / go / mahjong / poker / カードゲーム小品に対応する
(F16, ROADMAP v0.7.0)。それらのゲームは ``llove.games.base`` の共通
抽象 (Engine / Player / Loop / Move / Observation / GameOutcome) を継承
することで、CLI (`llove play <game>`)・観戦・棋譜署名・バッチ評価を
ゲーム横断で再利用できる。

shogi は MVP2a 段階では ``llove.shogi`` 直下に独立実装されているが
(MVP2a の 1 ファイル単位開発を優先したため)、MVP2b 完了後に
``llove.games.shogi`` へマイグレーションする予定 (手戻り許容)。

F18 Rust 移植時の Cargo workspace 境界 (``llove-core`` /
``llove-shogi`` / ``llove-chess`` / ...) を意識して、ここから先の
ディレクトリ階層は **1 ディレクトリ = 1 将来クレート** で切る。
"""

from __future__ import annotations
