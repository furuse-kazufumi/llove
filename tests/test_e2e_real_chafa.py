"""ad-hoc E2E: mmdc + chafa が実インストールされている場合のみ動く統合確認.

CI ではバイナリ非依存なのでスキップ。手動 dev 環境での動作確認用。
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from llove.views.image_render_pane import ImageRenderPane
from llove.views.mermaid_render import render_mermaid_to_svg

# Windows winget でインストールされる chafa は PATH に乗らないので明示
_CHAFA_CANDIDATES = [
    shutil.which("chafa"),
    r"C:\Users\puruy\AppData\Local\Microsoft\WinGet\Links\Chafa.exe",
]


def _find_chafa() -> str | None:
    for c in _CHAFA_CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


@pytest.mark.skipif(
    not shutil.which("mmdc") or not _find_chafa(),
    reason="requires real mmdc + chafa binaries",
)
def test_real_e2e_mermaid_to_chafa_via_pane() -> None:
    """実 mmdc + chafa で SVG → ANSI の生成と pane への到達を検証."""
    chafa = _find_chafa()
    assert chafa is not None
    mmdc = shutil.which("mmdc")
    assert mmdc is not None

    with tempfile.TemporaryDirectory() as tmp:
        # 1) mermaid → SVG (real mmdc)
        svg = Path(tmp) / "real.svg"
        result = render_mermaid_to_svg(
            "flowchart LR\nA --> B\nB --> C\n",
            svg,
            mmdc_path=mmdc,
        )
        # mmdc が PATH 上に存在しても puppeteer / node のセットアップ
        # 不備で SVG 生成に失敗するケースがある (Windows でよく見る).
        # その場合は実機 E2E の前提が崩れているので skip する.
        if result is None:
            pytest.skip(f"mmdc at {mmdc} failed to generate SVG (env-specific)")
        assert result == svg
        assert svg.stat().st_size > 100  # 実 SVG のはず (~12 KB)

        # 2) SVG → ANSI via real chafa, fed through ImageRenderPane

        def real_runner(argv: list[str], *, timeout: int) -> tuple[int, bytes, bytes]:
            proc = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                timeout=timeout,
            )
            return proc.returncode, proc.stdout or b"", proc.stderr or b""

        pane = ImageRenderPane(runner=real_runner, timeout=30)

        # MermaidRender 互換の dataclass を直接渡してみる (svg_path は未使用でも OK)
        from llove.views.mermaid_render import MermaidRender

        mr = MermaidRender(
            kind="image",
            argv=(chafa, "--size", "40x10", str(svg)),
            svg_path=svg,
        )
        pane.set_render(mr)

        # ANSI を含む str が pane に届いたこと
        assert pane.last_render
        # ESC sequence (0x1b) が出力に含まれること = chafa が画像を ANSI 化した
        assert "\x1b" in pane.last_render
        # 最低限の長さがあること (空の placeholder ではない)
        assert len(pane.last_render) > 100

        print(f"E2E success: SVG {svg.stat().st_size}B -> ANSI {len(pane.last_render)}B")
