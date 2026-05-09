"""Quick diagnostic: dump x/y positions of <text> spans in a snapshot SVG."""
from __future__ import annotations

import html as _h
import re
import sys
import unicodedata
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/snap-coin_toss-ja-v3.svg")
svg = path.read_text(encoding="utf-8")

spans = re.findall(
    r'<text\s+x="([\d.]+)"\s+y="([\d.]+)"[^>]*>([^<]+)</text>',
    svg,
)
print(f"matched <text> spans: {len(spans)}")

# East Asian Width summary on the first CJK-bearing span.
for x, y, content in spans:
    txt = _h.unescape(content)
    if any(unicodedata.east_asian_width(c) in ("W", "F") for c in txt):
        print(f"\nfirst CJK span:  x={x}  y={y}  text={txt[:40]!r}")
        for c in txt[:10]:
            eaw = unicodedata.east_asian_width(c)
            print(f"   {c!r}   EAW={eaw}")
        break

# Walk same-line spans and compute consecutive x deltas.
print("\nadjacent x deltas (same y):")
prev = None
shown = 0
for x, y, content in spans:
    txt = _h.unescape(content).strip()
    if not txt:
        continue
    if prev is not None and prev[1] == y:
        dx = float(x) - float(prev[0])
        prev_w = sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in prev[2][:6])
        print(f"  {prev[2][:10]!r:24} (cells~{prev_w}) -> {txt[:10]!r:24}  dx={dx:.1f}")
        shown += 1
    prev = (x, y, txt)
    if shown >= 25:
        break
