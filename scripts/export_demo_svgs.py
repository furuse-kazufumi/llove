# SPDX-License-Identifier: Apache-2.0
"""Export Textual SVG screenshots of each demo scenario.

Usage::

    py -3.11 scripts/export_demo_svgs.py [--out=docs/scenarios/svg] [--delay=2.5]
                                          [--scenario=<name>] [--size=120x30]

書き出した SVG は `docs/scenarios/svg/<scenario>.svg` に置かれ、Jekyll の
GitHub Pages で公開ドキュメント (`https://furuse-kazufumi.github.io/llove/`)
からそのまま参照可能。

Textual の `App.save_screenshot()` を `run_test` (Pilot) ベースで非同期に
走らせる。LLM 呼び出しを必要とする scenario (chat / multimodal 等) は
mock backend 前提で **シミュレーションのみ** が画面に出る点に注意。

実行例::

    py -3.11 scripts/export_demo_svgs.py --scenario=firewall
    py -3.11 scripts/export_demo_svgs.py            # 全 scenario を順に
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Windows cp932 console issue: ✓ / ✗ などの非 ASCII を出すと UnicodeEncodeError.
# 環境変数 PYTHONIOENCODING に依存せず、ここで明示的に utf-8 に切替える.
for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

from llove.app import LoveApp
from llove.demo.scenarios import SCENARIOS, get_scenario


async def _export_one(name: str, *, out_dir: Path, size: tuple[int, int], delay: float) -> Path:
    scenario = get_scenario(name)
    app = LoveApp(source=scenario, with_narration=True)
    out_path = out_dir / f"{name}.svg"
    async with app.run_test(size=size) as pilot:
        # scenario が動き出すまで少し待つ
        await pilot.pause(delay=delay)
        # SVG export
        app.save_screenshot(str(out_path))
    return out_path


def _parse_size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x", 1)
    return int(w), int(h)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/scenarios/svg", help="output directory")
    parser.add_argument("--scenario", help="single scenario name; omit to export all")
    parser.add_argument("--size", default="120x30", help="terminal size, WxH")
    parser.add_argument("--delay", type=float, default=2.5, help="seconds to wait before capture")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    size = _parse_size(args.size)

    names = [args.scenario] if args.scenario else sorted(SCENARIOS.keys())
    if args.scenario and args.scenario not in SCENARIOS:
        print(f"unknown scenario: {args.scenario}", file=sys.stderr)
        print(f"available: {', '.join(sorted(SCENARIOS))}", file=sys.stderr)
        return 2

    print(f"exporting {len(names)} scenario(s) → {out_dir} (size={size[0]}x{size[1]}, delay={args.delay}s)")
    written: list[Path] = []
    for name in names:
        try:
            path = asyncio.run(_export_one(name, out_dir=out_dir, size=size, delay=args.delay))
            print(f"  ✓ {path}")
            written.append(path)
        except Exception as e:
            # 1 つ失敗しても他は続ける (scenario によっては外部依存がある)
            print(f"  ✗ {name}: {e}", file=sys.stderr)
    print(f"\n{len(written)} SVG file(s) written.")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
