"""TypingEngine — F21 タイピングデモのコア.

F16 GameEngine 抽象を継承する 1-player 版. Move.notation は **入力された
1 文字** (キーストローク) を表す. push が 1 文字単位で current_word の
prefix と照合し、合っていれば typed_prefix を伸ばす、間違っていれば
miss を 1 増やす + Engine 状態は変えない (illegal 扱い).

設計上の要点:
- F16 抽象は「合法手 / 違法手 + 終局判定」を要求するだけなので、
  タイピングのような連続入力にもそのまま乗る. 違法手 = ミスタイプ.
  ループ側の illegal 連続 N 回 forfeit は MAX_INT に設定して無効化する
  か、典型的にはミスタイプ何回までで「失格」にするかをポリシー化可.
- Player は人間が直接打つので ``HumanTypingPlayer`` (Textual Input から
  キーイベントをひろう) を別ファイルで実装. 本ファイルは Engine のみ.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

from llove.games.base import (
    GameEngine,
    LegalityResult,
    Move,
    Observation,
    TermReason,
)
from llove.games.base.engine import TermResult


@dataclass(frozen=True)
class TypingStats:
    """統計スナップショット — SensorStream / SPC ペインに流す."""

    words_completed: int
    keystrokes: int
    miss: int
    elapsed_s: float
    wpm: float           # words per minute (5-char/word 規約)
    accuracy: float      # 0.0–1.0


class TypingEngine(GameEngine):
    """1-player のタイピングゲーム.

    Parameters
    ----------
    words
        最初に並んでいる単語列. ``WordSource`` が動的に補充できる.
    player_id
        単独 player の ID. デフォルト ``"you"``.
    target_words
        終局条件 (このウィンドウ数を完走したら ``checkmate`` 扱いで終局).
        ``None`` ならエンドレス (``MAX_PLY`` で外側から止める).
    """

    game = "typing"

    def __init__(
        self,
        words: list[str] | None = None,
        *,
        player_id: str = "you",
        target_words: int | None = 10,
    ) -> None:
        self._player_id = player_id
        self._queue: deque[str] = deque(words or [])
        self._current_word: str = self._queue.popleft() if self._queue else ""
        self._typed_prefix: str = ""
        self._miss: int = 0
        self._keystrokes: int = 0
        self._words_completed: int = 0
        self._target = target_words
        self._terminated: TermResult | None = None
        self._started_at: float | None = None
        self._finished_at: float | None = None

    # ---- WordSource からの補充 ---------------------------------------
    def push_word(self, word: str) -> None:
        """次の単語を末尾に追加 (WordSource が逐次呼ぶ)."""
        if not self._current_word:
            self._current_word = word
        else:
            self._queue.append(word)

    # ---- GameEngine 実装 -----------------------------------------------
    def player_ids(self) -> list[str]:
        return [self._player_id]

    def current_player_id(self) -> str:
        return self._player_id

    @property
    def ply(self) -> int:
        # ply = 完了した単語数 (失格はカウントせず)
        return self._words_completed

    def state_summary(self) -> str:
        return (
            f"word={self._current_word!r} typed={self._typed_prefix!r} "
            f"miss={self._miss} done={self._words_completed}"
        )

    def observation_for(self, player_id: str) -> Observation:
        return Observation(
            player_id=player_id,
            public_state={
                "current_word": self._current_word,
                "typed_prefix": self._typed_prefix,
                "remaining": list(self._queue),
                "miss": self._miss,
                "words_completed": self._words_completed,
            },
            legal_moves=[],  # 動的入力 — 静的な合法手リストは持たない
            metadata={
                "ply": self.ply,
                "target_words": self._target,
            },
        )

    def push(self, move: Move, player_id: str) -> LegalityResult:
        """1 keystroke を反映する.

        ``move.notation`` は **1 文字** であることを期待 (1 文字ずつ
        逐次プッシュされるモデル). 複数文字は禁止.
        """
        if player_id != self._player_id:
            return LegalityResult(ok=False, reason=f"illegal: not {player_id}'s turn")
        if len(move.notation) != 1:
            return LegalityResult(
                ok=False,
                reason=f"illegal: keystroke must be 1 character, got {len(move.notation)}",
            )
        if not self._current_word:
            return LegalityResult(ok=False, reason="illegal: no current word")

        # 開始時刻を最初の打鍵で固定
        if self._started_at is None:
            self._started_at = time.monotonic()

        ch = move.notation
        expected = self._current_word[len(self._typed_prefix)]
        self._keystrokes += 1
        if ch != expected:
            self._miss += 1
            # ミスタイプは「違法手」として返す — 状態は進めない
            return LegalityResult(ok=False, reason=f"miss: expected {expected!r}, got {ch!r}")

        # 正解 — prefix を伸ばす
        self._typed_prefix += ch

        # 単語完了?
        if self._typed_prefix == self._current_word:
            self._words_completed += 1
            self._typed_prefix = ""
            if self._queue:
                self._current_word = self._queue.popleft()
            else:
                self._current_word = ""
            # 目標数到達なら終局
            if self._target is not None and self._words_completed >= self._target:
                self._finished_at = time.monotonic()
                self._terminated = TermResult(
                    reason=TermReason.SCORE,
                    winner_id=self._player_id,
                    detail=f"completed {self._words_completed} words",
                )

        return LegalityResult(ok=True)

    def is_terminated(self) -> TermResult | None:
        return self._terminated

    # ---- 統計 --------------------------------------------------------
    def stats(self, *, now: float | None = None) -> TypingStats:
        """現在の統計を返す. SensorStream / SPC ペインへのフィード用."""
        end = self._finished_at or now or time.monotonic()
        elapsed = (end - self._started_at) if self._started_at else 0.0
        # WPM は 5 文字を 1 単語と数える業界標準
        wpm = (self._keystrokes / 5) / (elapsed / 60.0) if elapsed > 0 else 0.0
        total = self._keystrokes
        # accuracy は (correct / total). correct = total - miss.
        # ただし miss は keystrokes に既に加算されている (試行は数える)
        # ので total が分母になる.
        accuracy = (total - self._miss) / total if total > 0 else 1.0
        return TypingStats(
            words_completed=self._words_completed,
            keystrokes=self._keystrokes,
            miss=self._miss,
            elapsed_s=elapsed,
            wpm=wpm,
            accuracy=accuracy,
        )
