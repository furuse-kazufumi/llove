# SPDX-License-Identifier: Apache-2.0
"""Export an animated SVG of a demo scenario.

Textual の `App.save_screenshot()` は静的 SVG しか返さないので、本スクリプト
では `run_test` + `pilot.pause` を組合せて **複数フレーム** を取り、それらを
1 つの SVG に **SMIL** (`<set>` による display 切替) で結合する。

設計判断 (2026-05-23 普及ファネル即効):
- **SMIL のみ** (`<set attributeName="display" .../>`) を使う。経験的事実として
  SMIL は Qiita / GitHub の ``<img>`` 内で animate する (連載 #24 で実証済)。
  一方、SVG-in-``<img>`` 内の CSS ``@keyframes`` は GitHub Camo proxy で
  剥がされる可能性が高く未検証なので使わない。``<script>`` も使わない。
- **完全 self-contained** — Rich が埋め込む cdnjs の ``@font-face`` block を
  全 frame から除去し、``_patch_cjk_fonts`` で CJK monospace fallback chain を
  注入する。出力 SVG は外部 ``http`` / ``cdnjs`` 参照を一切持たない
  (root の xmlns 名前空間 URI を除く — これは fetch されない識別子)。
- **fail-closed validation** — 書き込み前に ``minidom.parseString`` で XML を
  検証し、malformed なら拒否する。

将棋 (shogi) / SCADA (scada) / mindmap / RAG など、時間軸を持つ scenario で
動きを伝えるのに有効。

Usage::

    py -3.11 scripts/export_demo_anim_svg.py --scenario=shogi --frames=8 \
        --frame-delay=1.5 --out=docs/scenarios/anim
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import tempfile
from pathlib import Path
from xml.dom import minidom

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

from llove.app import LoveApp
from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.i18n import set_locale

# _patch_cjk_fonts is defined alongside the static snapshot tool; reuse it so
# the CJK monospace fallback chain stays in one place.
from snapshot_scenario import _patch_cjk_fonts


SVG_OPEN_RE = re.compile(r"(<svg[^>]*>)", re.DOTALL)
SVG_CLOSE_RE = re.compile(r"</svg>\s*$", re.DOTALL)
VIEWBOX_RE = re.compile(r'viewBox="([^"]+)"')
# Rich embeds @font-face blocks that reference cdnjs.cloudflare.com. Each block
# has no nested braces, so a flat `{[^}]*}` match is safe.
FONT_FACE_RE = re.compile(r"@font-face\s*\{[^}]*\}", re.DOTALL)
# Rich's generator comment links to textualize.io — strip it to keep the file
# free of external http references.
GENERATOR_COMMENT_RE = re.compile(r"<!--\s*Generated with Rich[^>]*-->", re.DOTALL)


def _strip_svg_tags(svg_text: str) -> tuple[str, str]:
    """Return (open_tag, inner_xml) of <svg>...</svg>."""
    open_match = SVG_OPEN_RE.search(svg_text)
    if open_match is None:
        raise ValueError("no <svg> tag found")
    open_tag = open_match.group(1)
    inner_start = open_match.end()
    close_match = SVG_CLOSE_RE.search(svg_text)
    if close_match is None:
        raise ValueError("no </svg> close")
    return open_tag, svg_text[inner_start:close_match.start()]


def _self_contain(svg_text: str) -> str:
    """Make one captured frame fully self-contained.

    1. Drop every Rich ``@font-face`` block (they pull woff/woff2 from
       cdnjs.cloudflare.com — an external dependency that GitHub Camo proxy may
       strip and that breaks offline rendering).
    2. Drop the ``Generated with Rich`` comment (links to textualize.io).
    3. Apply ``_patch_cjk_fonts`` so glyphs render via a local CJK-aware
       monospace fallback chain instead of the now-removed CDN font.
    """
    svg_text = FONT_FACE_RE.sub("", svg_text)
    svg_text = GENERATOR_COMMENT_RE.sub("", svg_text)
    svg_text = _patch_cjk_fonts(svg_text)
    return svg_text


def _build_animated_svg(frames_svg: list[str], frame_duration_s: float) -> str:
    """Combine multiple static SVGs into a single animated SVG via **SMIL**.

    Each frame is wrapped in ``<g id="frame-i" display="none">`` and made
    visible only during its 1/n slice of the cycle through a SMIL
    ``<set attributeName="display" to="inline" begin=.. dur=.. .../>`` that
    repeats indefinitely. Frame 0 also keeps a static ``display="none"`` →
    its ``<set>`` flips it on at ``begin="0s"``, so the loop is seamless.

    No CSS ``animation`` / ``@keyframes`` and no ``<script>`` — only SMIL,
    which is the empirically-verified path for ``<img>`` embedding on
    Qiita / GitHub.
    """
    if not frames_svg:
        raise ValueError("no frames")
    open_tag, _ = _strip_svg_tags(frames_svg[0])
    viewbox_match = VIEWBOX_RE.search(open_tag)
    viewbox = viewbox_match.group(1) if viewbox_match else "0 0 1280 768"
    n = len(frames_svg)
    total_duration = frame_duration_s * n

    inner_groups: list[str] = []
    for i, svg in enumerate(frames_svg):
        _, inner = _strip_svg_tags(_self_contain(svg))
        begin = i * frame_duration_s
        # Frame visible for one slice, then hidden, looping over the whole
        # cycle. Two <set> elements per frame keep state crisp (snap in / out)
        # and self-restoring at the start of each loop.
        set_on = (
            f'<set attributeName="display" to="inline" '
            f'begin="{begin:.4f}s" dur="{frame_duration_s:.4f}s" '
            f'repeatCount="indefinite"/>'
        )
        # Hide again at the end of this frame's slice (i.e. when the next frame
        # begins). The last frame hides at the cycle boundary.
        hide_begin = (i + 1) * frame_duration_s % total_duration
        set_off = (
            f'<set attributeName="display" to="none" '
            f'begin="{hide_begin:.4f}s" '
            f'repeatCount="indefinite"/>'
        )
        inner_groups.append(
            f'<g id="frame-{i}" display="none">{set_on}{set_off}{inner}</g>'
        )

    # Compose final SVG. The xmlns URI is a namespace identifier (never
    # fetched), the only remaining http-prefixed token by design.
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet">'
        + "".join(inner_groups)
        + "</svg>"
    )


def _validate_svg(svg_text: str) -> None:
    """Fail-closed: refuse to write malformed XML.

    Mirrors ``manga-md-poc/mangamd_poc.py``'s ``minidom.parseString`` gate.
    """
    minidom.parseString(svg_text.encode("utf-8"))


async def _capture_frames(name: str, *, lang: str, size: tuple[int, int], frames: int, frame_delay: float) -> list[str]:
    set_locale(lang)
    scenario = get_scenario(name)
    app = LoveApp(source=scenario, with_narration=True)
    frame_texts: list[str] = []
    tmpdir = Path(tempfile.mkdtemp(prefix=f"anim-{name}-{lang}-"))
    async with app.run_test(size=size) as pilot:
        # 初期描画安定化
        await pilot.pause(delay=0.5)
        for i in range(frames):
            await pilot.pause(delay=frame_delay)
            f = tmpdir / f"frame-{i:03d}.svg"
            app.save_screenshot(str(f))
            frame_texts.append(f.read_text(encoding="utf-8"))
    return frame_texts


def _parse_size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x", 1)
    return int(w), int(h)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True, help="scenario name (e.g. shogi)")
    parser.add_argument("--lang", default="ja", help="locale (default 'ja')")
    parser.add_argument("--frames", type=int, default=6, help="number of frames")
    parser.add_argument("--frame-delay", type=float, default=1.5, help="seconds between frames")
    parser.add_argument("--size", default="120x30", help="terminal size, WxH")
    parser.add_argument(
        "--out",
        default="docs/scenarios/anim",
        help="output base. File written to <out>/<scenario>/<lang>.svg",
    )
    parser.add_argument(
        "--legacy-naming",
        action="store_true",
        help="write to <out>/<scenario>.svg without lang subpath (legacy)",
    )
    args = parser.parse_args(argv)

    if args.scenario not in SCENARIOS:
        print(f"unknown scenario: {args.scenario}", file=sys.stderr)
        print(f"available: {', '.join(sorted(SCENARIOS))}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    size = _parse_size(args.size)

    print(f"capturing {args.frames} frame(s) of {args.scenario}/{args.lang} (size={size[0]}x{size[1]}, delay={args.frame_delay}s)")
    frames_svg = asyncio.run(_capture_frames(args.scenario, lang=args.lang, size=size, frames=args.frames, frame_delay=args.frame_delay))
    print(f"  captured {len(frames_svg)} frame(s)")

    animated = _build_animated_svg(frames_svg, frame_duration_s=args.frame_delay)

    # fail-closed: validate XML before touching disk.
    try:
        _validate_svg(animated)
    except Exception as exc:  # noqa: BLE001 — surface any parse failure
        print(f"  ✗ refusing to write malformed SVG: {exc}", file=sys.stderr)
        return 1

    if args.legacy_naming:
        out_path = out_dir / f"{args.scenario}.svg"
    else:
        out_path = out_dir / args.scenario / f"{args.lang}.svg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(animated, encoding="utf-8")
    print(f"  ✓ {out_path}  ({out_path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
