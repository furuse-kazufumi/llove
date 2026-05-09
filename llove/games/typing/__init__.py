"""``llove.games.typing`` — F21 タイピングデモ.

LLM × 人間の協働シンプルデモ. ジャンル指定 → LLM (or mock 辞書) が
単語を流す → 人間がタイプ → 1 文字単位で色分け → 単語完了で次へ.

実装 ~200 行で済む llove ハンズオン最小サンプル.

公開 API:

    from llove.games.typing import (
        TypingEngine,
        WordSource, MockWordSource,
        TypingStats,
        BUILTIN_GENRES,
    )
"""

from __future__ import annotations

from llove.games.typing.engine import TypingEngine, TypingStats
from llove.games.typing.wordsource import (
    BUILTIN_GENRES,
    MockWordSource,
    WordSource,
)

__all__ = [
    "BUILTIN_GENRES",
    "MockWordSource",
    "TypingEngine",
    "TypingStats",
    "WordSource",
]
