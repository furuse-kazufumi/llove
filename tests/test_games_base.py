"""F16(a) ``llove.games.base`` 共通骨格のテスト.

ここでは shogi に依存しない **トイゲーム** ("3 ply で終わるカウンター
ゲーム") を使って ABC + run_game + 署名 + 違法手投了の経路を検証する.
こうすることで python-shogi 不在環境でもテスト可能.
"""

from __future__ import annotations

import pytest

from llove.events import Event
from llove.games.base import (
    GameEngine,
    GameOutcome,
    GamePlayer,
    Move,
    Observation,
    TermReason,
    ThinkResult,
    run_game,
)
from llove.games.base.engine import LegalityResult, TermResult

# ---------------------------------------------------------------------------
# Toy game: counters
# ---------------------------------------------------------------------------
#
# ルール: 2 player ("a", "b") が交互に「increment」と打ち合う.
# 各 player は ``Move(notation="inc")`` を打つ. ``Move(notation="bad")`` は
# 違法手. ply が ``max_ply`` に達したら MAX_PLY で終局.


class CounterEngine(GameEngine):
    game = "counter"

    def __init__(self) -> None:
        self._counter = 0
        self._turn = "a"
        self._terminal: TermResult | None = None

    def player_ids(self) -> list[str]:
        return ["a", "b"]

    def current_player_id(self) -> str:
        return self._turn

    @property
    def ply(self) -> int:
        return self._counter

    def state_summary(self) -> str:
        return f"counter={self._counter}"

    def observation_for(self, player_id: str) -> Observation:
        return Observation(
            player_id=player_id,
            public_state={"counter": self._counter, "turn": self._turn},
            legal_moves=["inc"],
            metadata={"ply": self._counter},
        )

    def push(self, move: Move, player_id: str) -> LegalityResult:
        if move.notation != "inc":
            return LegalityResult(ok=False, reason=f"illegal: {move.notation}")
        if player_id != self._turn:
            return LegalityResult(ok=False, reason=f"illegal: not {player_id}'s turn")
        self._counter += 1
        self._turn = "b" if self._turn == "a" else "a"
        return LegalityResult(ok=True)

    def is_terminated(self) -> TermResult | None:
        return self._terminal

    def force_terminate(self, reason: TermReason, winner: str | None = None) -> None:
        """テスト用 — 任意の理由で終局フラグを立てる."""
        self._terminal = TermResult(reason=reason, winner_id=winner)


class _ScriptedPlayer(GamePlayer):
    """指定された (notation, resign?) リストを順に返す player."""

    def __init__(self, name: str, plays: list[tuple[str, bool]]) -> None:
        self.name = name
        self.provider = "test"
        self.model = "scripted"
        self._plays = plays
        self._cursor = 0

    async def think(self, observation: Observation) -> ThinkResult:
        if self._cursor >= len(self._plays):
            return ThinkResult(move=None, resign=True, resign_reason="script exhausted")
        notation, resign = self._plays[self._cursor]
        self._cursor += 1
        if resign:
            return ThinkResult(move=None, resign=True, resign_reason="scripted resign")
        return ThinkResult(move=Move(notation=notation, thinking_ms=0))


# ---------------------------------------------------------------------------
# Tests — types
# ---------------------------------------------------------------------------


def test_termreason_is_string_compatible() -> None:
    # JSONL シリアライズで使うので str() がキー名 ("checkmate" 等) と一致.
    assert str(TermReason.CHECKMATE) == "checkmate"
    assert TermReason.RESIGN_ILLEGAL == "resign_illegal"


def test_observation_defaults() -> None:
    obs = Observation(player_id="a")
    assert obs.public_state == {}
    assert obs.private_state == {}
    assert obs.legal_moves == []


def test_move_is_immutable() -> None:
    m = Move(notation="x")
    with pytest.raises(Exception):
        m.notation = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Tests — run_game
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_game_collects_legal_moves_and_signs_them() -> None:
    eng = CounterEngine()
    a = _ScriptedPlayer("A", [("inc", False), ("inc", False)])
    b = _ScriptedPlayer("B", [("inc", False)])
    events: list[Event] = []
    async for ev in run_game(eng, {"a": a, "b": b}, max_ply=3):
        events.append(ev)

    moves = [ev for ev in events if ev.payload.get("event") == "game.move"]
    # a → b → a の 3 着手
    assert len(moves) == 3
    # 全 move に signed_bytes が乗る
    for ev in moves:
        assert "signed_bytes" in ev.payload
        canonical = bytes.fromhex(ev.payload["signed_bytes"]).decode()
        # ``"counter|{ply}|{player}|inc|counter={ply+1}"`` の形
        assert canonical.startswith("counter|")
        assert "|inc|" in canonical


@pytest.mark.asyncio
async def test_run_game_resign_path_records_winner_in_1v1() -> None:
    eng = CounterEngine()
    a = _ScriptedPlayer("A", [])  # 即 resign
    b = _ScriptedPlayer("B", [("inc", False)])
    events = [ev async for ev in run_game(eng, {"a": a, "b": b})]
    end = events[-1]
    assert end.payload["event"] == "game.end"
    assert end.payload["term"] == "resign_player"
    assert end.payload["winner_id"] == "b"  # 1v1 で resign しなかった方が勝者


@pytest.mark.asyncio
async def test_run_game_illegal_strikes_force_forfeit() -> None:
    eng = CounterEngine()
    a = _ScriptedPlayer("A", [("bad", False), ("bad", False), ("bad", False)])
    b = _ScriptedPlayer("B", [])  # 来ない
    events = [ev async for ev in run_game(eng, {"a": a, "b": b}, illegal_strikes_allowed=3)]

    illegal = [ev for ev in events if ev.payload.get("event") == "game.illegal_attempt"]
    assert len(illegal) == 3
    end = events[-1]
    assert end.payload["term"] == "resign_illegal"
    assert end.payload["winner_id"] == "b"


@pytest.mark.asyncio
async def test_run_game_max_ply_safety_net() -> None:
    eng = CounterEngine()
    # 2 player で永遠に inc し続けるが max_ply で止まる
    a = _ScriptedPlayer("A", [("inc", False)] * 100)
    b = _ScriptedPlayer("B", [("inc", False)] * 100)
    events = [ev async for ev in run_game(eng, {"a": a, "b": b}, max_ply=4)]
    end = events[-1]
    assert end.payload["term"] == "max_ply"
    assert end.payload["plies"] == 4


@pytest.mark.asyncio
async def test_run_game_engine_self_termination_propagates() -> None:
    eng = CounterEngine()
    eng.force_terminate(TermReason.CHECKMATE, winner="a")
    a = _ScriptedPlayer("A", [])
    b = _ScriptedPlayer("B", [])
    events = [ev async for ev in run_game(eng, {"a": a, "b": b})]
    end = events[-1]
    assert end.payload["term"] == "checkmate"
    assert end.payload["winner_id"] == "a"


@pytest.mark.asyncio
async def test_run_game_missing_player_raises() -> None:
    eng = CounterEngine()
    a = _ScriptedPlayer("A", [("inc", False)])
    # b の player を渡し忘れる → fail-closed で ValueError.
    with pytest.raises(ValueError, match="missing player"):
        async for _ in run_game(eng, {"a": a}):
            pass


@pytest.mark.asyncio
async def test_run_game_start_event_lists_all_players() -> None:
    eng = CounterEngine()
    a = _ScriptedPlayer("A", [])
    b = _ScriptedPlayer("B", [])
    events = [ev async for ev in run_game(eng, {"a": a, "b": b})]
    start = events[0]
    assert start.payload["event"] == "game.start"
    assert start.payload["game"] == "counter"
    assert sorted(start.payload["player_ids"]) == ["a", "b"]
    assert "a" in start.payload["players"]
    assert start.payload["players"]["a"]["name"] == "A"


def test_game_outcome_serializes_to_json() -> None:
    o = GameOutcome(
        game="counter",
        term=TermReason.CHECKMATE,
        plies=3,
        winner_id="a",
        moves=[{"ply": 0, "notation": "inc"}],
    )
    js = o.to_json()
    assert "checkmate" in js
    assert "counter" in js
