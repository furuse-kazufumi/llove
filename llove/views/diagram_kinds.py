"""F15 (t2/t3) — Diagram kind registry.

5 種類の diagram (mermaid / svg / plantuml / dot / svgbob) を identify する
info-string、canonical kind 名、エイリアス、summary marker 形式を **1 ヶ所** に
集約するレジストリ。

これ以前は同じ情報が 4 箇所に分散していた:
- ``folding.find_code_block_regions`` — info-string → kind の正規化
- ``folding._summary_line`` — kind → summary marker (▶ ◇ ... 形式)
- ``folding._preset_prose`` — prose preset で畳む kind 集合
- ``markdown_view.make_markdown_fold_hook`` — `:fold by-tag` の valid kind 集合

新規 diagram kind 追加時はこのファイルに 1 行加えるだけで全箇所が連動する。
diagram 系以外の kind (heading / code / table) はこのレジストリの対象外
(専用の summary フォーマットを持つため)。

設計判断:
- ``aliases`` はタプル: 順序を保つことで「graphviz は dot に統一」のような
  正規化方向を明示できる (set ではこの方向が消える)。
- ``summary_marker`` は kind 名と同じ (▶ ◇ {name}: 形式は固定) ため、現状は
  kind name だけ持っておけば足りる。将来 marker をカスタマイズしたく
  なったら field を増やす。
- ``frozen=True`` で immutable。テストや別モジュールでの差し替えを禁止し、
  registry の単一性を担保する。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiagramKind:
    """A diagram block kind that folding / MarkdownView know about.

    Attributes
    ----------
    name
        Canonical kind name. ``find_code_block_regions`` が ``FoldRegion.kind``
        に格納する値であり、`:fold by-tag <name>` の引数でもある。
        downstream の renderer 辞書のキーにもなる
        (例: ``diagram_renderers={"dot": render_dot}``).
    aliases
        ``info_lower`` がここに含まれていても ``name`` に正規化される。
        例: ``("graphviz",)`` は ` ```graphviz ` を kind="dot" に倒すため。
    """

    name: str
    aliases: tuple[str, ...] = ()


# 5 種類の diagram kind を正規化順 (canonical → aliases) で列挙。
# 新規 diagram renderer を追加するときはこのタプルに 1 行加える。
DIAGRAM_KINDS: tuple[DiagramKind, ...] = (
    DiagramKind("mermaid"),
    DiagramKind("svg"),
    DiagramKind("plantuml"),
    DiagramKind("dot", aliases=("graphviz",)),
    DiagramKind("svgbob", aliases=("bob",)),
)


# Set 形式で公開 (頻繁にメンバーシップ判定するため)
DIAGRAM_KIND_NAMES: frozenset[str] = frozenset(k.name for k in DIAGRAM_KINDS)


def normalise_info_string(info_lower: str) -> str | None:
    """info-string から canonical diagram kind 名を引く. 非 diagram は None.

    Parameters
    ----------
    info_lower
        コードフェンスの info-string を **小文字化済** で渡す。
        ``find_code_block_regions`` 側で ``info_label.lower()`` してから
        この関数を呼ぶ。

    Returns
    -------
    canonical kind name (例: ``"dot"``) または ``None`` (diagram ではない場合)。
    """
    for kind in DIAGRAM_KINDS:
        if info_lower == kind.name:
            return kind.name
        if info_lower in kind.aliases:
            return kind.name
    return None


def diagram_summary_marker(kind: str, label: str, hidden: int) -> str | None:
    """``▶ ◇ <kind>: <label> (N lines)`` 形式の summary 行を返す.

    Returns
    -------
    summary 行、または ``kind`` が diagram でない場合 ``None``。
    """
    if kind not in DIAGRAM_KIND_NAMES:
        return None
    return f"▶ ◇ {kind}: {label} ({hidden} lines)"


__all__ = [
    "DIAGRAM_KINDS",
    "DIAGRAM_KIND_NAMES",
    "DiagramKind",
    "diagram_summary_marker",
    "normalise_info_string",
]
