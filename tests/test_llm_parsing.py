"""``llove.llm.parsing`` の単体テスト — chatty な LLM 応答から着手抽出."""

from __future__ import annotations

from llove.llm.parsing import extract_move, first_move_token


def test_extract_exact_single_token() -> None:
    assert extract_move("7g7f", ["7g7f", "2g2f"]) == "7g7f"


def test_extract_from_chatty_prose() -> None:
    text = "I think the best move here is 7g7f, opening the bishop's diagonal."
    assert extract_move(text, ["7g7f", "2g2f", "6i7h"]) == "7g7f"


def test_extract_ignores_substring_false_positive() -> None:
    # "e4" は "Ne4" の部分文字列だが, 境界が無いので拾わない.
    assert extract_move("Ne4 is a good developing move", ["e4", "d4"]) is None


def test_extract_prefers_earliest_occurrence() -> None:
    text = "Not 2g2f but rather 7g7f."
    # 2g2f が先に出る → それを採用 (最も早い位置).
    assert extract_move(text, ["7g7f", "2g2f"]) == "2g2f"


def test_extract_prefers_longer_move_at_same_position() -> None:
    # 成り接尾: "7g7f+" と "7g7f" が同位置で始まる → 長い方.
    assert extract_move("7g7f+", ["7g7f", "7g7f+"]) == "7g7f+"


def test_extract_handles_drop_notation() -> None:
    assert extract_move("Drop a pawn: P*5e looks strong.", ["P*5e", "7g7f"]) == "P*5e"


def test_extract_trailing_punctuation() -> None:
    assert extract_move("My move: e2e4.", ["e2e4", "d2d4"]) == "e2e4"


def test_extract_san_check_suffix() -> None:
    # SAN の王手/詰み接尾も 1 手として拾える (長い方優先).
    assert extract_move("Qh7#", ["Qh7", "Qh7#"]) == "Qh7#"


def test_extract_check_suffix_when_legal_list_has_no_suffix() -> None:
    # ★#4 の核心: chess の合法手は UCI (装飾なし "d1h5") だが, モデルは王手手を
    # "d1h5+" と書く。装飾 + を右境界として許容し, 合法手 d1h5 に一致させる
    # (許容しないと正しい手なのに resign してしまう).
    assert extract_move("d1h5+", ["e2e4", "g1f3", "d1h5"]) == "d1h5"
    assert extract_move("The move is d1h5#.", ["d1h5", "g1f3"]) == "d1h5"
    assert extract_move("I play e4!", ["e4", "d4"]) == "e4"


def test_extract_prefers_promotion_when_both_legal() -> None:
    # 将棋 USI: 成り "7g7f+" と不成 "7g7f" が両方合法なら, 装飾でなく手そのものと
    # して長い "7g7f+" を選ぶ (tie-break が生きる — 順序不問).
    assert extract_move("7g7f+", ["7g7f", "7g7f+"]) == "7g7f+"
    assert extract_move("7g7f+", ["7g7f+", "7g7f"]) == "7g7f+"


def test_extract_still_rejects_substring_after_suffix_relax() -> None:
    # 装飾許容後も左境界は厳格 — "Ne4" 中の "e4" は拾わない.
    assert extract_move("Ne4+", ["e4", "d4"]) is None
    # 連結された 2 手 "e4e5" から "e4" を拾わない (末尾 'e' は装飾でない).
    assert extract_move("e4e5", ["e4", "d4"]) is None


def test_extract_empty_legal_moves_returns_none() -> None:
    assert extract_move("7g7f", []) is None


def test_extract_no_match_returns_none() -> None:
    assert extract_move("I resign, this is hopeless.", ["7g7f", "2g2f"]) is None


def test_first_move_token_plain() -> None:
    assert first_move_token("7g7f") == "7g7f"


def test_first_move_token_strips_wrappers_and_takes_first() -> None:
    assert first_move_token("`7g7f` opens the bishop") == "7g7f"


def test_first_move_token_multiline_takes_first_line() -> None:
    assert first_move_token("2g2f\nthen 8h2b") == "2g2f"


def test_first_move_token_empty() -> None:
    assert first_move_token("   ") is None
