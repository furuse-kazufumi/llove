"""F20(c)③ Command Palette UI — 純粋関数 (filter / complete / history) テスト.

Widget 自体ではなく ``llove.term.completion`` の小ロジックを網羅する.
Widget 起動 (run_test) は ``test_command_palette_ui.py`` 側に分離.
"""

from __future__ import annotations

import pytest

from llove.term.completion import (
    HistoryRing,
    complete_prefix,
    filter_suggestions,
)

NAMES = [
    "alias",
    "demo",
    "get",
    "help",
    "identity",
    "layout",
    "macro",
    "open",
    "peer",
    "play",
    "set",
]


# ---------------------------------------------------------------------------
# filter_suggestions
# ---------------------------------------------------------------------------


class TestFilterSuggestions:
    def test_empty_returns_all_sorted(self) -> None:
        # default limit=10 で NAMES 11 件は先頭 10 件のみ. 全件は limit を渡す.
        assert filter_suggestions("", NAMES) == sorted(NAMES)[:10]
        assert filter_suggestions("", NAMES, limit=99) == sorted(NAMES)

    def test_strips_colon_prefix(self) -> None:
        assert filter_suggestions(":he", NAMES) == ["help"]
        assert filter_suggestions("he", NAMES) == ["help"]

    def test_prefix_match_priority(self) -> None:
        # "p" にマッチするのは peer / play
        assert filter_suggestions("p", NAMES) == ["peer", "play"]

    def test_fuzzy_fallback_when_no_prefix(self) -> None:
        # "identty" は前方一致なし → fuzzy で "identity"
        result = filter_suggestions("identty", NAMES)
        assert result == ["identity"]

    def test_no_match_returns_empty(self) -> None:
        assert filter_suggestions("xyzzy_unknown", NAMES) == []

    def test_limit_caps_results(self) -> None:
        result = filter_suggestions("", NAMES, limit=3)
        assert len(result) == 3

    def test_dedup(self) -> None:
        # 同じ名前が来ても 1 つ
        result = filter_suggestions("", ["a", "a", "b"])
        assert result == ["a", "b"]


# ---------------------------------------------------------------------------
# complete_prefix
# ---------------------------------------------------------------------------


class TestCompletePrefix:
    def test_unique_match_completes_full(self) -> None:
        assert complete_prefix(":he", NAMES) == ":help"
        assert complete_prefix("he", NAMES) == "help"

    def test_multi_match_returns_common_prefix(self) -> None:
        # peer / play → 共通 "p"
        assert complete_prefix(":p", NAMES) == ":p"
        # ma → macro しかないので :macro
        assert complete_prefix(":ma", NAMES) == ":macro"

    def test_no_match_keeps_input(self) -> None:
        assert complete_prefix(":zzz", NAMES) == ":zzz"

    def test_empty_returns_input(self) -> None:
        # 空入力で候補多数 → 共通プレフィックスは "" → 元の "" を返す
        assert complete_prefix("", NAMES) == ""

    def test_colon_preserved(self) -> None:
        assert complete_prefix(":id", NAMES).startswith(":")
        assert not complete_prefix("id", NAMES).startswith(":")


# ---------------------------------------------------------------------------
# HistoryRing
# ---------------------------------------------------------------------------


class TestHistoryRing:
    def test_push_and_up_down(self) -> None:
        h = HistoryRing()
        h.push(":help")
        h.push(":identity")
        # 末尾より後ろ → up() で最新が出る
        assert h.up() == ":identity"
        assert h.up() == ":help"
        # これ以上遡れない: 0 で頭打ち
        assert h.up() == ":help"
        assert h.down() == ":identity"
        # down() で末尾を超えると空入力相当
        assert h.down() == ""
        assert h.at_end() is True

    def test_uniq_adjacent(self) -> None:
        h = HistoryRing()
        h.push(":help")
        h.push(":help")
        assert h.items == [":help"]

    def test_reset_jumps_to_end(self) -> None:
        h = HistoryRing()
        h.push("a")
        h.push("b")
        h.up()
        h.up()
        assert h.at_end() is False
        h.reset()
        assert h.at_end() is True

    def test_empty_history_returns_none(self) -> None:
        h = HistoryRing()
        assert h.up() is None
        assert h.down() is None

    def test_blank_lines_ignored(self) -> None:
        h = HistoryRing()
        h.push("")
        h.push("   ")
        assert h.items == []

    def test_maxlen_drops_oldest(self) -> None:
        h = HistoryRing(maxlen=3)
        for s in ["a", "b", "c", "d"]:
            h.push(s)
        assert h.items == ["b", "c", "d"]

    def test_push_after_navigation_resets_index(self) -> None:
        h = HistoryRing()
        h.push("a")
        h.push("b")
        h.up()  # at "b"
        h.up()  # at "a"
        h.push("c")
        # push 後は末尾に居る → up で "c"
        assert h.up() == "c"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", sorted(NAMES)[:10]),
        (":i", ["identity"]),
        ("p", ["peer", "play"]),
        ("se", ["set"]),
    ],
)
def test_filter_parametrized(text: str, expected: list[str]) -> None:
    assert filter_suggestions(text, NAMES) == expected


class TestHistoryRingPersistence:
    def test_save_and_load_roundtrip(self, tmp_path: pytest.TempPathFactory) -> None:
        p = tmp_path / "history"
        h = HistoryRing()
        h.push(":help")
        h.push(":identity")
        h.save(p)

        h2 = HistoryRing()
        h2.load(p)
        assert h2.items == [":help", ":identity"]
        assert h2.at_end()

    def test_load_missing_file_is_noop(self, tmp_path: pytest.TempPathFactory) -> None:
        h = HistoryRing()
        h.load(tmp_path / "nonexistent")
        assert h.items == []

    def test_save_creates_parent_dir(self, tmp_path: pytest.TempPathFactory) -> None:
        p = tmp_path / "nested" / "dir" / "history"
        h = HistoryRing()
        h.push(":demo")
        h.save(p)
        assert p.exists()
        assert p.read_text(encoding="utf-8").strip() == ":demo"

    def test_load_respects_maxlen(self, tmp_path: pytest.TempPathFactory) -> None:
        p = tmp_path / "history"
        p.write_text("\n".join(str(i) for i in range(10)) + "\n", encoding="utf-8")
        h = HistoryRing(maxlen=5)
        h.load(p)
        assert h.items == ["5", "6", "7", "8", "9"]

    def test_save_trims_to_maxlen(self, tmp_path: pytest.TempPathFactory) -> None:
        p = tmp_path / "history"
        h = HistoryRing(maxlen=3)
        for s in ["a", "b", "c", "d"]:
            h.push(s)
        h.save(p)
        lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l]
        assert lines == ["b", "c", "d"]

    def test_blank_lines_skipped_on_load(self, tmp_path: pytest.TempPathFactory) -> None:
        p = tmp_path / "history"
        p.write_text(":help\n\n:identity\n  \n", encoding="utf-8")
        h = HistoryRing()
        h.load(p)
        assert h.items == [":help", ":identity"]
