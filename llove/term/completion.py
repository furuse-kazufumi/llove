"""F20(c)③ Command Palette UI のための純粋関数群.

Widget (Textual ``Input``) は ``palette.py`` に置く. このモジュールは
UI 非依存のフィルタ計算 / 補完 / 履歴リングだけを提供する. すべて
純粋関数 / 小さな state machine なので, run_test() を使わない普通の
ユニットテストで挙動を完全カバーできる.

責務:

- ``filter_suggestions``  入力中の文字列に対する候補列を計算
- ``complete_prefix``     Tab 補完で確定できる「最大共通プレフィックス」
- ``HistoryRing``         上下キーで遡る履歴 (重複排除 + 上限つき)

設計参照:
- F20(c) Command Palette UI (memory project_llove.md)
- 2.1.1 「llmesh シンプル / llove で表示工夫」 — ロジックは llove 側で薄く
- ウィンドウ哲学 "do one thing well" — UI 計算は UI 非依存層に封じる
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable
from dataclasses import dataclass, field
from os import path as _ospath
from pathlib import Path

# ---------------------------------------------------------------------------
# Suggestion filter
# ---------------------------------------------------------------------------


def _strip_colon(text: str) -> str:
    s = text.lstrip()
    if s.startswith(":"):
        s = s[1:]
    return s


def filter_suggestions(
    text: str,
    names: Iterable[str],
    *,
    limit: int = 10,
    fuzzy_cutoff: float = 0.5,
) -> list[str]:
    """``text`` に対する候補名リストを返す.

    1. 入力先頭の ``:`` を 1 個まで剥がして実体を取り出す
    2. 空入力なら全候補を ``sorted`` で先頭 ``limit`` 件返す
    3. **前方一致** が 1 件以上あればそれを優先 (順序保持: 入力順 -> sorted)
    4. なければ ``difflib`` の fuzzy 近似で ``limit`` 件まで埋める

    順序: ``startswith`` 一致は ``sorted`` 順、fuzzy 一致は ``difflib`` の
    類似度順. これにより入力中の「補完候補」と未知入力時の「もしかして」が
    1 つの API で扱える.
    """
    needle = _strip_colon(text)
    pool = sorted(set(names))
    if not needle:
        return pool[:limit]
    prefix_hits = [n for n in pool if n.startswith(needle)]
    if prefix_hits:
        return prefix_hits[:limit]
    return difflib.get_close_matches(needle, pool, n=limit, cutoff=fuzzy_cutoff)


def complete_prefix(text: str, names: Iterable[str]) -> str:
    """Tab 補完: 候補の最大共通プレフィックスを返す.

    - 候補ゼロ: 元の ``text`` を返す
    - 候補 1 つ: その名前 (``:`` 接頭辞は元の text に合わせる)
    - 候補複数: 全候補の最大共通プレフィックス (``os.path.commonprefix`` 流用)
    """
    candidates = filter_suggestions(text, names, limit=64)
    if not candidates:
        return text
    keep_colon = text.lstrip().startswith(":")
    if len(candidates) == 1:
        head = candidates[0]
    else:
        head = _ospath.commonprefix(candidates)
        if not head:
            return text
    return f":{head}" if keep_colon else head


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


@dataclass
class HistoryRing:
    """上下キーで辿るコマンド履歴.

    - ``push`` で末尾に追加 (直前と同一なら無視: vim 流の uniq-adjacent)
    - ``up()`` で「次に古い」エントリ, ``down()`` で「次に新しい」エントリ
    - ``reset()`` で navigation 位置を末尾に戻す (Enter 後に呼ぶ)
    - ``maxlen`` 超過は古い順に dropoff

    位置インデックスは「末尾の 1 つ後ろ」を ``len(items)`` として持ち,
    ``up()`` で 1 つずつ前へ, ``down()`` で 1 つずつ後ろへ動く.
    末尾より後ろ (= 入力中文字列) には移動しない.
    """

    maxlen: int = 200
    items: list[str] = field(default_factory=list)
    _idx: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._idx = len(self.items)

    def push(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        if self.items and self.items[-1] == line:
            self._idx = len(self.items)
            return
        self.items.append(line)
        if len(self.items) > self.maxlen:
            self.items = self.items[-self.maxlen :]
        self._idx = len(self.items)

    def reset(self) -> None:
        self._idx = len(self.items)

    def up(self) -> str | None:
        """次に古いエントリへ. 末尾に居れば 1 つ手前へ. これ以上遡れない場合 None."""
        if not self.items:
            return None
        if self._idx == 0:
            return self.items[0]
        self._idx -= 1
        return self.items[self._idx]

    def down(self) -> str | None:
        """次に新しいエントリへ. 末尾に達したら空入力相当 ('') を返し reset 状態."""
        if not self.items:
            return None
        if self._idx >= len(self.items) - 1:
            self._idx = len(self.items)
            return ""
        self._idx += 1
        return self.items[self._idx]

    def at_end(self) -> bool:
        return self._idx >= len(self.items)


__all__ = [
    "HistoryRing",
    "complete_prefix",
    "filter_suggestions",
]
