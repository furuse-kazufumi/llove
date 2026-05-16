# SPDX-License-Identifier: Apache-2.0
"""Export an animated SVG of a demo scenario.

Textual の `App.save_screenshot()` は静的 SVG しか返さないので、本スクリプト
では `run_test` + `pilot.pause` を組合せて **複数フレーム** を取り、それらを
1 つの SVG に CSS keyframes で結合する。

将棋 (shogi) / mindmap / RAG など、時間軸を持つ scenario で動きを伝えるの
に有効。

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

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

from llove.app import LoveApp
from llove.demo.scenarios import SCENARIOS, get_scenario
from llove.i18n import set_locale


SVG_OPEN_RE = re.compile(r"(<svg[^>]*>)", re.DOTALL)
SVG_CLOSE_RE = re.compile(r"</svg>\s*$", re.DOTALL)
VIEWBOX_RE = re.compile(r'viewBox="([^"]+)"')


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


def _build_animated_svg(frames_svg: list[str], frame_duration_s: float) -> str:
    """Combine multiple static SVGs into a single animated SVG via CSS keyframes."""
    if not frames_svg:
        raise ValueError("no frames")
    open_tag, _ = _strip_svg_tags(frames_svg[0])
    viewbox_match = VIEWBOX_RE.search(open_tag)
    viewbox = viewbox_match.group(1) if viewbox_match else "0 0 1280 768"
    n = len(frames_svg)
    total_duration = frame_duration_s * n
    # Per-frame visible window = 1/n of the cycle. Slight cross-fade omitted
    # for simplicity (each frame snaps in).
    keyframes_parts: list[str] = []
    css_rules: list[str] = []
    for i in range(n):
        start_pct = (i / n) * 100
        end_pct = ((i + 1) / n) * 100
        slightly_before_end_pct = max(start_pct, end_pct - 0.01)
        # Each frame: visible during its window, hidden otherwise.
        css_rules.append(f"#frame-{i} {{ opacity: 0; animation: f{i} {total_duration}s steps(1) infinite; }}")
        keyframes_parts.append(
            f"@keyframes f{i} {{"
            f" 0% {{ opacity: 0; }}"
            f" {start_pct:.4f}% {{ opacity: 1; }}"
            f" {slightly_before_end_pct:.4f}% {{ opacity: 1; }}"
            f" {end_pct:.4f}% {{ opacity: 0; }}"
            f" 100% {{ opacity: 0; }} }}"
        )
    style_block = "<style>" + "".join(css_rules) + "".join(keyframes_parts) + "</style>"

    inner_groups: list[str] = []
    for i, svg in enumerate(frames_svg):
        _, inner = _strip_svg_tags(svg)
        inner_groups.append(f'<g id="frame-{i}">{inner}</g>')

    # Compose final SVG
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" '
        f'width="100%" preserveAspectRatio="xMidYMid meet">'
        f"{style_block}"
        + "".join(inner_groups)
        + "</svg>"
    )


async def _capture_frames(name: str, *, size: tuple[int, int], frames: int, frame_delay: float) -> list[str]:
    scenario = get_scenario(name)
    app = LoveApp(source=scenario, with_narration=True)
    frame_texts: list[str] = []
    tmpdir = Path(tempfile.mkdtemp(prefix=f"anim-{name}-"))
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
    parser.add_argument("--frames", type=int, default=6, help="number of frames")
    parser.add_argument("--frame-delay", type=float, default=1.5, help="seconds between frames")
    parser.add_argument("--size", default="120x30", help="terminal size, WxH")
    parser.add_argument("--out", default="docs/scenarios/anim", help="output directory")
    args = parser.parse_args(argv)

    if args.scenario not in SCENARIOS:
        print(f"unknown scenario: {args.scenario}", file=sys.stderr)
        print(f"available: {', '.join(sorted(SCENARIOS))}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    size = _parse_size(args.size)

    print(f"capturing {args.frames} frame(s) of {args.scenario} (size={size[0]}x{size[1]}, delay={args.frame_delay}s)")
    frames_svg = asyncio.run(_capture_frames(args.scenario, size=size, frames=args.frames, frame_delay=args.frame_delay))
    print(f"  captured {len(frames_svg)} frame(s)")

    animated = _build_animated_svg(frames_svg, frame_duration_s=args.frame_delay)
    out_path = out_dir / f"{args.scenario}.svg"
    out_path.write_text(animated, encoding="utf-8")
    print(f"  ✓ {out_path}  ({out_path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
