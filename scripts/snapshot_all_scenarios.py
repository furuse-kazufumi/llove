# SPDX-License-Identifier: Apache-2.0
"""Capture SVG snapshots for **all demo scenarios × all locales** to `out/`.

`scripts/snapshot_scenario.py` の core 関数 `_capture()` を再利用して、
全 scenario と全 locale (ja, en) の組合せを一気に生成する wrapper。
出力命名規則は既存 `snap-<scenario>-<lang>.svg` と整合。

Usage::

    py -3.11 scripts/snapshot_all_scenarios.py
    py -3.11 scripts/snapshot_all_scenarios.py --languages=ja,en,zh --out=out
    py -3.11 scripts/snapshot_all_scenarios.py --scenarios=cost,chat,shogi

注: out/ にある既存の手作業バージョン (`snap-cost-ja-v2.svg` 等) は
上書きしない。本 wrapper は **v サフィックス無し** のベースラインを
更新するだけ。手作業 v タグ付きは別途レビュー資産として残す方針。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from llove.demo.scenarios import SCENARIOS  # noqa: E402
from scripts.snapshot_scenario import _capture  # noqa: E402


def _parse_size(s: str) -> tuple[int, int]:
    w, h = s.lower().split("x", 1)
    return int(w), int(h)


def _parse_csv(s: str) -> list[str]:
    return [t.strip() for t in s.split(",") if t.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="out", help="output directory (default 'out')")
    parser.add_argument(
        "--languages",
        default="ja,en",
        help="comma-separated locales (default 'ja,en')",
    )
    parser.add_argument(
        "--scenarios",
        default="",
        help="comma-separated scenarios; omit to do all",
    )
    parser.add_argument("--pause", type=float, default=2.5, help="headless playback seconds (default 2.5)")
    parser.add_argument("--size", default="120x40", help="terminal size WxH (default 120x40)")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite existing baseline files (snap-<scenario>-<lang>.svg)",
    )
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    size = _parse_size(args.size)

    scenarios = _parse_csv(args.scenarios) if args.scenarios else sorted(SCENARIOS.keys())
    languages = _parse_csv(args.languages)

    print(f"snapshotting {len(scenarios)} scenario(s) × {len(languages)} locale(s) → {out_dir}")
    print(f"  size={size[0]}x{size[1]}, pause={args.pause}s, overwrite={args.overwrite}")
    print()

    written = 0
    skipped = 0
    failed = 0

    for name in scenarios:
        if name not in SCENARIOS:
            print(f"  ? unknown scenario: {name}", file=sys.stderr)
            failed += 1
            continue
        for lang in languages:
            out_path = out_dir / f"snap-{name}-{lang}.svg"
            if out_path.exists() and not args.overwrite:
                print(f"  - {out_path}  (exists, skip — use --overwrite to replace)")
                skipped += 1
                continue
            try:
                asyncio.run(_capture(name, lang, out_path, args.pause, size))
                print(f"  ✓ {out_path}")
                written += 1
            except Exception as e:
                print(f"  ✗ {name}/{lang}: {e}", file=sys.stderr)
                failed += 1

    print()
    print(f"{written} written / {skipped} skipped / {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
