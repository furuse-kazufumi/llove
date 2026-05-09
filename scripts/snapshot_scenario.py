"""Capture an SVG snapshot of one demo scenario via Textual's headless Pilot.

Used to review TUI presentation quality (narration readability, pane usage,
pacing) without launching a real terminal. Run from the repo root:

    python scripts/snapshot_scenario.py cost en out/snap-cost-en.svg
    python scripts/snapshot_scenario.py cost ja out/snap-cost-ja.svg
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from pathlib import Path

# Allow running as `python scripts/snapshot_scenario.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llove.app import LoveApp  # noqa: E402
from llove.demo.scenarios import get_scenario  # noqa: E402
from llove.i18n import set_locale  # noqa: E402


# Monospace fallback chain for Japanese / CJK characters.
#
# Important: only fixed-pitch (NOT "P"-suffixed = proportional) faces here.
#  - "BIZ UDPGothic"  has the *Plus Proportional* metrics — wrong, drop it
#  - "BIZ UDGothic"   is the fixed-pitch sibling — correct
#  - "Yu Gothic" / "Hiragino Sans" are proportional too — drop
#
# Textual's SVG export only declares "Fira Code"; CJK characters then fall
# back to whatever the viewer picks (often a *proportional* font), which
# squishes Japanese text and misaligns it with the monospace x-coordinates
# Rich computed. This chain keeps everything monospace across OSes.
_MONO_CJK_CHAIN = (
    '"Fira Code", "MS Gothic", "BIZ UDGothic", '
    '"Noto Sans Mono CJK JP", "HackGen", "PlemolJP", '
    '"Source Han Mono", "Osaka-Mono", "VL Gothic", monospace'
)


def _patch_cjk_fonts(svg: str) -> str:
    """Inject a CJK-aware monospace fallback chain *and* force every <text>
    to stretch its glyphs to its declared textLength so a proportional
    fallback font (if the user lacks any of our preferred fonts) still
    can't make characters overlap."""
    svg = (
        svg
        .replace('font-family: "Fira Code"', f"font-family: {_MONO_CJK_CHAIN}")
        .replace("font-family: Fira Code, monospace", f"font-family: {_MONO_CJK_CHAIN}")
    )
    # Add lengthAdjust="spacingAndGlyphs" to every <text ... textLength="…">
    # that does not already declare lengthAdjust. This lets the renderer
    # squeeze/stretch glyphs to honour textLength, defending against a
    # proportional-fallback last-resort.
    svg = re.sub(
        r'(<text\b[^>]*?textLength="[\d.]+")(?![^>]*\blengthAdjust=)',
        r'\1 lengthAdjust="spacingAndGlyphs"',
        svg,
    )
    return svg


async def _capture(name: str, lang: str, out_path: Path, pause_s: float, size: tuple[int, int]) -> None:
    set_locale(lang)
    scenario = get_scenario(name)
    scenario.default_pause = 0.05  # speed playback so we hit interesting state fast
    app = LoveApp(scenario, with_narration=True)
    async with app.run_test(size=size) as pilot:
        await pilot.pause(pause_s)
        svg = app.export_screenshot(title=f"llove · {name} · {lang}")
        svg = _patch_cjk_fonts(svg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(svg, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture an SVG snapshot of one llove scenario")
    parser.add_argument("scenario", help="scenario name, e.g. cost / chat / bench / drift / mcp_call / vision / pointcloud / mindmap")
    parser.add_argument("lang", choices=["en", "ja"], help="locale to render in")
    parser.add_argument("out", type=Path, help="output SVG path")
    parser.add_argument("--pause", type=float, default=2.5, help="seconds of headless playback before snap (default 2.5)")
    parser.add_argument("--size", default="120x40", help="terminal size as WIDTHxHEIGHT (default 120x40)")
    args = parser.parse_args()

    w, h = (int(x) for x in args.size.lower().split("x"))
    asyncio.run(_capture(args.scenario, args.lang, args.out, args.pause, (w, h)))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
