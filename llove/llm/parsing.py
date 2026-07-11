"""LLM の自由記述応答から着手 (notation) を頑健に取り出す純粋関数.

ゲーム/プロバイダに依存しない文字列処理だけを置く (ここに game import を
持ち込まない). LLM は「7g7f が最善です」のように前置き付きで返すことが
多いので, 合法手リストとの **トークン一致** で拾う — 部分文字列一致だと
"Ne4" の中の "e4" を誤検出するため, 前後が着手文字でない (境界) ことを
確認する.
"""

from __future__ import annotations

from collections.abc import Sequence

#: 着手を構成しうる文字 (USI/SAN/SGF を横断的にカバー).
#: 英数字 + 成り/王手/詰み/持ち駒打ち/キャスリング等の記号.
_MOVE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+*-=#"
)

#: 応答の端に付きがちな飾り (fallback トークン抽出時に剥がす).
_WRAPPERS = "`\"'.,;:()[]{}<>!?　「」『』"

#: 着手の直後に付きうる装飾 (王手 +, 詰み #, 好手/疑問手 ! ?). これらは着手末尾の
#: 「境界」として許容する — チェスの合法手は UCI (装飾なし "d1h5") なのに, モデルは
#: 一般記法で "d1h5+" と王手注釈を付けることが多く, 装飾を境界と認めないと合法手に
#: 一致せず誤って resign してしまう。将棋 USI の成り "7g7f+" は装飾でなく手そのもので
#: 合法手リストにも現れるため, 「より長い合法手優先」の tie-break がそちらを選ぶ.
_END_DECORATIONS = frozenset("+#!?")


def _is_boundary(text: str, index: int) -> bool:
    """``index`` が範囲外, または着手文字でなければ境界とみなす (左境界用)."""
    if index < 0 or index >= len(text):
        return True
    return text[index] not in _MOVE_CHARS


def _is_end_boundary(text: str, index: int) -> bool:
    """右境界判定. 範囲外 / 非着手文字 / 装飾文字(+#!?) を境界とみなす."""
    if index < 0 or index >= len(text):
        return True
    ch = text[index]
    return ch not in _MOVE_CHARS or ch in _END_DECORATIONS


def extract_move(text: str, legal_moves: Sequence[str]) -> str | None:
    """``text`` 中に**トークンとして**現れる最初の合法手を返す (無ければ None).

    - 部分文字列でなく境界付き一致 ("Ne4" の "e4" は弾く).
    - 複数現れたら **text 中で最も早い位置** の手を採用. 同位置なら成り接尾等を
      拾うため **より長い手** を優先 ("7g7f+" が "7g7f" に勝つ).
    - ``legal_moves`` が空なら None (呼び出し側が :func:`first_move_token` で代替).
    """
    if not legal_moves:
        return None

    best_index: int | None = None
    best_move: str | None = None

    for lm in legal_moves:
        if not lm:
            continue
        start = 0
        while True:
            i = text.find(lm, start)
            if i < 0:
                break
            end = i + len(lm)
            if _is_boundary(text, i - 1) and _is_boundary(text, end):
                # このループ手の最初の「境界付き」出現のみ評価.
                if (
                    best_index is None
                    or i < best_index
                    or (i == best_index and best_move is not None and len(lm) > len(best_move))
                ):
                    best_index = i
                    best_move = lm
                break
            start = i + 1

    return best_move


def first_move_token(text: str) -> str | None:
    """先頭行の最初のトークンを飾りを剥がして返す (合法手リストが無い場合の代替).

    合法手が渡されない/どれも一致しなかったときに, モデルの生出力を engine へ
    渡して legality oracle に判定させるためのフォールバック. 空なら None.
    """
    stripped = text.strip().strip(_WRAPPERS).strip()
    if not stripped:
        return None
    first_line = stripped.splitlines()[0].strip()
    parts = first_line.split()
    if not parts:
        return None
    token = parts[0].strip(_WRAPPERS)
    return token or None


__all__ = ["extract_move", "first_move_token"]
