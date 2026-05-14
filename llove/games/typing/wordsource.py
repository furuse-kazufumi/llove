"""WordSource — F21 タイピングデモへの単語供給.

設計:
- ``WordSource`` ABC: ``async def __aiter__`` で単語を逐次返す
- ``MockWordSource``: ジャンル名 → 同梱辞書から決定論的に取り出す
  (オフライン、テスト用)
- ``LLMWordSource``: 次セッションで Anthropic / Ollama / llmesh:peer
  経由で単語を生成 (今は placeholder)

ジャンル例 (BUILTIN_GENRES):
- programming-rust       — Rust 予約語 / 型 / トレイト (F18 移行学習)
- programming-llmesh-api — llmesh の関数名 / MCP ツール名
- shogi-koma             — 駒名・棋譜 (F12 関連)
- llmesh-did             — did:key の写経 (識別子学習)
- multilingual-ja-en     — 日英混合
- math-symbols           — 数式・ギリシャ文字
- unix-commands          — bash コマンド
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

# ---------------------------------------------------------------------------
# 同梱辞書 (BUILTIN_GENRES)
# ---------------------------------------------------------------------------


BUILTIN_GENRES: dict[str, list[str]] = {
    "programming-rust": [
        "fn", "let", "mut", "pub", "use", "mod", "struct", "enum", "impl",
        "trait", "where", "Self", "self", "match", "async", "await", "move",
        "Box", "Rc", "Arc", "Vec", "String", "Option", "Result", "Some",
        "None", "Ok", "Err", "tokio", "serde", "pyo3", "ratatui",
    ],
    "programming-llmesh-api": [
        "NodeIdentity", "did_key", "node_id", "public_key_hex",
        "TrustedPeers", "RequestSigner", "verify_chain", "AuditTrail",
        "SensorEvent", "ExplainedCUSUM", "PromptFirewall", "MultivariateSPC",
        "DiscoveryClient", "register_node", "list_peers",
        "generate_code", "review_code", "critique_output",
    ],
    "shogi-koma": [
        "歩", "香", "桂", "銀", "金", "角", "飛", "玉", "王",
        "と", "杏", "圭", "全", "馬", "龍",
        "▲", "△", "成", "打", "上", "下", "右", "左", "寄", "引",
        "７六歩", "３四歩", "２六歩", "８四歩", "２五歩", "８五歩",
    ],
    "llmesh-did": [
        # 短めの did:key / peer ID 写経. 全文が長いので途中までを単語として
        # 区切る. 学習目的なので部分文字列でも有用.
        "did:key:z6Mkqc5UFB9UrhnJsNANV6cbt8hVP9xCySK2z6jneRHhb8ou",
        "peer:C9pRevu3XAHqksKfoXem339VZagMZZ4gJ5prp9Kgfv2X",
        "did:llmesh:1:z6Mkabc",
        "fingerprint=7c:5e:e7:3b",
        "ed25519",
    ],
    "multilingual-ja-en": [
        "hello", "こんにちは", "world", "世界",
        "love", "愛", "code", "コード", "data", "データ",
        "AI", "人工知能", "machine", "機械",
        "neural", "ニューロン", "brain", "脳",
    ],
    "math-symbols": [
        "alpha", "beta", "gamma", "delta", "epsilon",
        "lambda", "mu", "pi", "sigma", "phi", "psi", "omega",
        "infty", "partial", "nabla", "int", "sum", "prod",
        "f(x)", "y=ax+b", "e^x", "log(x)", "sqrt(x)",
    ],
    "unix-commands": [
        "ls", "cd", "pwd", "cp", "mv", "rm", "mkdir", "touch",
        "cat", "less", "grep", "find", "sed", "awk",
        "git", "vim", "ssh", "scp", "rsync", "tar",
        "ps", "top", "kill", "df", "du", "free",
        "curl", "wget", "ping", "nc",
    ],
    "common-english": [
        "the", "be", "to", "of", "and", "in", "that", "have",
        "for", "not", "with", "you", "this", "but", "his", "from",
        "they", "she", "or", "an", "will", "my", "one", "all",
    ],
}


# ---------------------------------------------------------------------------
# WordSource ABC
# ---------------------------------------------------------------------------


class WordSource(ABC):
    """単語を async に供給するソース."""

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[str]: ...


# ---------------------------------------------------------------------------
# MockWordSource — 同梱辞書から決定論的に
# ---------------------------------------------------------------------------


class MockWordSource(WordSource):
    """ジャンル指定で同梱辞書から単語を取り出すモック.

    Parameters
    ----------
    genre
        ``BUILTIN_GENRES`` のキー or カスタム単語リスト.
    seed
        乱数 seed. 同じ seed なら同じ順序 (テスト容易).
    limit
        いくつ単語を返したら停止するか. ``None`` で無限.
    """

    def __init__(
        self,
        genre: str | list[str],
        *,
        seed: int = 0,
        limit: int | None = None,
    ) -> None:
        if isinstance(genre, str):
            words = BUILTIN_GENRES.get(genre)
            if words is None:
                raise ValueError(
                    f"unknown genre {genre!r}. "
                    f"Available: {sorted(BUILTIN_GENRES)} or pass a list[str]."
                )
            self._words = list(words)
            self._genre_name = genre
        else:
            self._words = list(genre)
            self._genre_name = "custom"
        if not self._words:
            raise ValueError("WordSource needs at least 1 word")
        self._rng = random.Random(seed)
        self._limit = limit
        self._emitted = 0

    @property
    def genre_name(self) -> str:
        return self._genre_name

    async def __aiter__(self) -> AsyncIterator[str]:
        while self._limit is None or self._emitted < self._limit:
            self._emitted += 1
            yield self._rng.choice(self._words)
