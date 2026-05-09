"""Compare span widths and colours between sente and gote pieces."""
from __future__ import annotations

import html as _h
import re
import sys
from pathlib import Path

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/snap-shogi-ja-v9.svg")
svg = path.read_text(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

# Find any class whose CSS body contains a red-ish fill.
print("--- red-ish CSS classes ---")
for cls, body in re.findall(r"(\.terminal-\d+-r\d+)\s*\{([^}]+)\}", svg):
    low = body.lower()
    if "ff0000" in low or "cc0000" in low or "ff5555" in low or "fill: #f" in low and "ff" in low.split("#")[1][:6]:
        print(f"  {cls.strip('.')} -> {body.strip()}")

print("\n--- piece spans ---")
spans = re.findall(r"<text\s+([^>]*)>([^<]+)</text>", svg)
piece = set("歩香桂銀金角飛玉と杏圭全馬龍")
shown = 0
for attrs, content in spans:
    txt = _h.unescape(content).strip()
    if not txt or len(txt) > 3:
        continue
    if not any(c in piece for c in txt):
        continue
    xm = re.search(r'x="([^"]+)"', attrs)
    ym = re.search(r'y="([^"]+)"', attrs)
    cm = re.search(r'class="([^"]+)"', attrs)
    tlm = re.search(r'textLength="([^"]+)"', attrs)
    x = xm.group(1) if xm else "?"
    y = ym.group(1) if ym else "?"
    cls = cm.group(1).split("-")[-1] if cm else "?"
    tl = tlm.group(1) if tlm else "?"
    print(f"  x={x:>6} y={y:>6} cls={cls:<4} tl={tl:<6} txt={txt!r}")
    shown += 1
    if shown >= 30:
        break
