"""F15 SVG export — data scene → animated SVG (SMIL).

llove TUI / llive 派生個体の表現を **GitHub README, Qiita 記事, ドキュメント
上で TUI を動かさず動きを見せる** ための export 経路 (skeleton).

設計判断:
- **SMIL のみ** (`<animateTransform>`, `<animate>` etc) を使う.
  `<script>` は GitHub Camo proxy で **剥がされる** ため一切使わない.
- **single self-contained file** (フォント / CSS は inline, no CDN).
- **dark/light テーマ対応** — GitHub の prefers-color-scheme に追従.
- 入力は **pure data structure** (e.g. list[float]). Textual app への
  依存を持たず, テスト容易性 + CI で動かしやすい.

最初の対象 (本セッション 2026-05-22):

- ``thought_factor_ring_svg(factors)`` — llive 10 思考因子 vector を
  rotating ring chart として animated SVG にする. 連載 #24-02 (思考因子)
  hero 用.

将来追加候補 (queue / project_github_animated_svg memory に登録済):

- ``chess_animated_svg(moves)`` — 1 局 30 手程度の board 遷移
- ``lineage_animated_svg(winners)`` — 世代進化 lineage
- ``approval_bus_flow_svg(events)`` — verdict flow ループ
- ``map_elites_grid_svg(cells)`` — 4 軸 grid heatmap
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

# llive 10 思考因子の canonical 順序 (llive.perf.evolutionary.persona.THOUGHT_FACTORS と一致).
# llove 単体で動作するよう, 値をコピー保持 (動的 import 無し).
THOUGHT_FACTOR_LABELS: tuple[str, ...] = (
    "structurize",
    "recompose",
    "closed_loop",
    "self_extend",
    "uncertainty",
    "exploration",
    "consistency",
    "provenance",
    "multiview",
    "reality_link",
)


@dataclass(frozen=True)
class SvgExportConfig:
    """SVG export の共通設定 (色 / size / duration)."""

    width: int = 480
    height: int = 480
    duration_s: float = 6.0
    # GitHub dark default (rgb 13,17,23). 明るい背景には white でも可.
    background: str = "#0d1117"
    foreground: str = "#e6edf3"
    # accent: factor 強度で透明度を補正する色 (foreground と同色推奨)
    accent: str = "#79c0ff"

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width / height must be > 0")
        if self.duration_s <= 0:
            raise ValueError("duration_s must be > 0")


def thought_factor_ring_svg(
    factors: Sequence[float],
    *,
    config: SvgExportConfig | None = None,
    labels: Sequence[str] = THOUGHT_FACTOR_LABELS,
) -> str:
    """10 因子 affinity vector を rotating ring chart として animated SVG.

    各 factor を center から放射方向に bar 表示, 全体が
    ``config.duration_s`` で 1 周回転 (SMIL ``<animateTransform>``).

    Parameters
    ----------
    factors : Sequence[float]
        各 factor の affinity [0, 1].
    config : SvgExportConfig | None
        色 / size / duration. None なら default.
    labels : Sequence[str]
        bar 端に表示するラベル. default は 10 因子 canonical 名.

    Returns
    -------
    str
        Single self-contained SVG XML string. ``<script>`` 不含, GitHub
        Camo proxy 互換.
    """
    cfg = config or SvgExportConfig()
    if len(factors) != len(labels):
        raise ValueError(
            f"factors len {len(factors)} != labels len {len(labels)}"
        )
    if len(factors) == 0:
        raise ValueError("factors must be non-empty")
    for i, f in enumerate(factors):
        if not 0.0 <= float(f) <= 1.0:
            raise ValueError(f"factors[{i}]={f} out of range [0, 1]")

    n = len(factors)
    cx = cfg.width / 2
    cy = cfg.height / 2
    max_radius = min(cx, cy) - 80  # label 用余白
    inner_radius = 28
    angle_step = 360.0 / n

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {cfg.width} {cfg.height}" '
            f'width="{cfg.width}" height="{cfg.height}" '
            'role="img" aria-label="llive 10 思考因子 ring chart">'
        ),
        (
            f'<rect width="100%" height="100%" fill="{cfg.background}"/>'
        ),
        f'<g transform="translate({cx} {cy})">',
        # 回転 group — 全 bars を 360° / duration_s で永久回転
        '<g>',
        (
            '<animateTransform attributeName="transform" type="rotate" '
            f'from="0" to="360" dur="{cfg.duration_s}s" '
            'repeatCount="indefinite"/>'
        ),
    ]

    for i, (factor, label) in enumerate(zip(factors, labels, strict=True)):
        angle = i * angle_step
        bar_length = inner_radius + (max_radius - inner_radius) * float(factor)
        opacity = 0.35 + float(factor) * 0.65  # 強い factor ほど高 opacity
        # bar 1 本 (rect, rotated to its angle, centered at origin)
        parts.append(
            f'<g transform="rotate({angle:.4f})">'
            f'<rect x="-6" y="-{bar_length:.4f}" width="12" '
            f'height="{(bar_length - inner_radius):.4f}" '
            f'fill="{cfg.accent}" opacity="{opacity:.3f}" rx="3"/>'
            f'<text y="-{(bar_length + 16):.4f}" text-anchor="middle" '
            f'fill="{cfg.foreground}" font-size="10" '
            f'font-family="ui-monospace, Menlo, monospace" '
            f'opacity="0.85">{_escape_svg(label)}</text>'
            f'</g>'
        )
    parts.append('</g>')  # rotation group close

    # center static label
    parts.append(
        f'<text text-anchor="middle" dy="0.35em" '
        f'fill="{cfg.foreground}" font-size="13" '
        f'font-family="ui-monospace, Menlo, monospace" '
        f'opacity="0.7">10-factor</text>'
    )

    parts.append('</g>')  # translate close
    parts.append('</svg>')
    return '\n'.join(parts)


def _escape_svg(s: str) -> str:
    """SVG text node 用最小 escape (&, <, >)."""
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


# ---------------------------------------------------------------------------
# Helper — 既知の persona 名 → factor vector mapping (デモ用)
# ---------------------------------------------------------------------------


# llive PERSONA_ONTOLOGY から手書きで 4 人分コピー (動的 import 避ける).
# 順: structurize / recompose / closed_loop / self_extend / uncertainty /
# exploration / consistency / provenance / multiview / reality_link.
_PERSONA_AFFINITY_SAMPLES: dict[str, tuple[float, ...]] = {
    "oka-kiyoshi": (0.7, 0.5, 0.8, 0.6, 0.8, 0.4, 0.9, 0.5, 0.6, 0.4),
    "feynman": (0.5, 0.6, 0.4, 0.5, 0.7, 0.95, 0.4, 0.4, 0.85, 0.95),
    "newton": (0.95, 0.4, 0.6, 0.3, 0.4, 0.5, 0.9, 0.6, 0.4, 0.8),
    "galois": (0.95, 0.85, 0.5, 0.4, 0.3, 0.5, 0.95, 0.3, 0.3, 0.2),
}


def sample_persona_factors(persona_id: str) -> tuple[float, ...]:
    """Demo 用: 既知 persona id → 10 factor affinity vector.

    full PERSONA_ONTOLOGY を参照したい場合は llive を import 経由で.
    本 helper は llove 単体で動くサンプル用途.
    """
    if persona_id not in _PERSONA_AFFINITY_SAMPLES:
        raise KeyError(
            f"unknown persona_id: {persona_id!r}. "
            f"available: {sorted(_PERSONA_AFFINITY_SAMPLES)}"
        )
    return _PERSONA_AFFINITY_SAMPLES[persona_id]


__all__ = [
    "THOUGHT_FACTOR_LABELS",
    "SvgExportConfig",
    "sample_persona_factors",
    "thought_factor_ring_svg",
]
