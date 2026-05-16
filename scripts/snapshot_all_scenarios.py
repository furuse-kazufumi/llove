# SPDX-License-Identifier: Apache-2.0
"""Capture SVG snapshots for **all demo scenarios × all locales**.

`scripts/snapshot_scenario.py` の core 関数 `_capture()` を再利用して、
全 scenario と全 locale (ja, en) の組合せを一気に生成する wrapper。

**出力レイアウト (デフォルト、階層型)**::

    out/scenarios/
    ├── audit/
    │   ├── ja.svg
    │   └── en.svg
    ├── chat/
    │   ├── ja.svg
    │   └── en.svg
    ...

**旧 flat レイアウト** (互換用)::

    out/snap-<scenario>-<lang>.svg

`--legacy-naming` フラグで旧式に切替。デフォルトは新階層。

Usage::

    py -3.11 scripts/snapshot_all_scenarios.py                       # 新階層
    py -3.11 scripts/snapshot_all_scenarios.py --legacy-naming       # 旧 flat
    py -3.11 scripts/snapshot_all_scenarios.py --scenarios=cost,shogi
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
        help="overwrite existing baseline files",
    )
    parser.add_argument(
        "--legacy-naming",
        action="store_true",
        help="use legacy flat naming (out/snap-<scenario>-<lang>.svg) instead of out/scenarios/<scenario>/<lang>.svg",
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
            if args.legacy_naming:
                out_path = out_dir / f"snap-{name}-{lang}.svg"
            else:
                out_path = out_dir / "scenarios" / name / f"{lang}.svg"
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
