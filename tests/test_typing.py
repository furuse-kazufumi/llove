"""F21 タイピングデモのテスト."""

from __future__ import annotations

import pytest

from llove.games.base import Move
from llove.games.typing import (
    BUILTIN_GENRES,
    MockWordSource,
    TypingEngine,
)

# ---------------------------------------------------------------------------
# TypingEngine
# ---------------------------------------------------------------------------


def test_engine_with_initial_words() -> None:
    e = TypingEngine(words=["fn", "let"])
    obs = e.observation_for("you")
    assert obs.public_state["current_word"] == "fn"
    assert obs.public_state["typed_prefix"] == ""
    assert obs.public_state["remaining"] == ["let"]


def test_correct_keystroke_advances_prefix() -> None:
    e = TypingEngine(words=["fn"])
    res = e.push(Move(notation="f"), "you")
    assert res.ok is True
    obs = e.observation_for("you")
    assert obs.public_state["typed_prefix"] == "f"


def test_wrong_keystroke_is_illegal_and_does_not_advance() -> None:
    e = TypingEngine(words=["fn"])
    res = e.push(Move(notation="x"), "you")
    assert res.ok is False
    assert "miss" in res.reason
    obs = e.observation_for("you")
    assert obs.public_state["typed_prefix"] == ""
    assert obs.public_state["miss"] == 1


def test_completing_a_word_loads_next() -> None:
    e = TypingEngine(words=["fn", "let"])
    e.push(Move(notation="f"), "you")
    e.push(Move(notation="n"), "you")
    obs = e.observation_for("you")
    assert obs.public_state["current_word"] == "let"
    assert obs.public_state["typed_prefix"] == ""
    assert obs.public_state["words_completed"] == 1


def test_target_words_terminates_game() -> None:
    e = TypingEngine(words=["a"], target_words=1)
    res = e.push(Move(notation="a"), "you")
    assert res.ok is True
    term = e.is_terminated()
    assert term is not None
    assert term.winner_id == "you"


def test_multi_char_keystroke_is_rejected() -> None:
    """1 文字単位のモデル — 'ab' のような複数文字は弾く."""
    e = TypingEngine(words=["fn"])
    res = e.push(Move(notation="fn"), "you")
    assert res.ok is False
    assert "1 character" in res.reason


def test_push_word_appends_to_queue() -> None:
    e = TypingEngine(words=[])
    e.push_word("alpha")
    obs = e.observation_for("you")
    assert obs.public_state["current_word"] == "alpha"
    e.push_word("beta")
    obs = e.observation_for("you")
    # current が空でないので beta は queue
    assert "beta" in obs.public_state["remaining"]


def test_stats_zero_on_start() -> None:
    e = TypingEngine(words=["fn"])
    s = e.stats()
    assert s.keystrokes == 0
    assert s.miss == 0
    assert s.accuracy == 1.0


def test_stats_after_one_correct_one_miss() -> None:
    e = TypingEngine(words=["fn"])
    e.push(Move(notation="f"), "you")
    e.push(Move(notation="x"), "you")
    s = e.stats()
    assert s.keystrokes == 2
    assert s.miss == 1
    assert s.accuracy == pytest.approx(0.5)


def test_engine_player_id_consistency() -> None:
    e = TypingEngine(words=["fn"], player_id="alice")
    assert e.player_ids() == ["alice"]
    assert e.current_player_id() == "alice"


# ---------------------------------------------------------------------------
# MockWordSource
# ---------------------------------------------------------------------------


def test_mock_word_source_with_genre() -> None:
    src = MockWordSource("programming-rust", seed=42, limit=3)
    assert src.genre_name == "programming-rust"


def test_mock_word_source_unknown_genre_raises() -> None:
    with pytest.raises(ValueError, match="unknown genre"):
        MockWordSource("nonexistent-genre")


def test_mock_word_source_custom_word_list() -> None:
    src = MockWordSource(["hello", "world"], seed=0, limit=2)
    assert src.genre_name == "custom"


def test_mock_word_source_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="at least 1 word"):
        MockWordSource([])


@pytest.mark.asyncio
async def test_mock_word_source_iterates_with_seed_determinism() -> None:
    """同じ seed なら同じ順序."""
    src1 = MockWordSource("programming-rust", seed=42, limit=5)
    src2 = MockWordSource("programming-rust", seed=42, limit=5)
    out1 = [w async for w in src1]
    out2 = [w async for w in src2]
    assert out1 == out2
    assert len(out1) == 5


@pytest.mark.asyncio
async def test_mock_word_source_respects_limit() -> None:
    src = MockWordSource("programming-rust", seed=0, limit=3)
    out = [w async for w in src]
    assert len(out) == 3


def test_builtin_genres_cover_all_planned_categories() -> None:
    """要件 F21 (d) に挙げたジャンルが揃っている (新ジャンル追加時に
    アラート)."""
    expected = {
        "programming-rust",
        "programming-llmesh-api",
        "shogi-koma",
        "llmesh-did",
        "multilingual-ja-en",
        "math-symbols",
        "unix-commands",
    }
    assert expected.issubset(BUILTIN_GENRES.keys())
    # 各ジャンル最低 5 単語
    for g, words in BUILTIN_GENRES.items():
        assert len(words) >= 5, f"genre {g!r} has only {len(words)} words"
