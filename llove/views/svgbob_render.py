"""F15 (t2/t3) — svgbob → SVG → ターミナル画像チェイン.

`mermaid_render.py` / `svg_render.py` / `plantuml_render.py` /
`dot_render.py` と並行する構造の薄い shim:

    svgbob ASCII art source
       │  (1) svgbob input.bob -o output.svg
       ▼
    SVG file
       │  (2) chafa / viu / timg / kitty +kitten icat / wezterm imgcat
       ▼
    ターミナル画像

svgbob は ASCII art (罫線・矢印・箱) を SVG 図に変換する Rust 製 CLI。
mermaid/dot/plantuml が DSL ベースなのに対し、svgbob は「コメント図を
そのまま絵にできる」のが特徴で、Markdown コードドキュメントでよく使われる
(rust-lang / bevy / servo 等)。

両ツールが揃わないか subprocess が失敗した場合は、ASCII フォールバックに
降りる。``MarkdownView`` の ``diagram_renderers={"svgbob": render_svgbob}``
に登録すれば、`folding.find_code_block_regions` が ``kind="svgbob"`` を
返した時点で自動展開される。

セキュリティ:
- subprocess は **list-based 引数のみ** (shell=True 禁止)
- 入力 svgbob source はテンポラリ ``.bob`` ファイルに書き出してから読ませる

Pure 関数 + 依存性注入で書いてあるので、svgbob / 画像ツール未インストール
の CI でもフルテスト可能。
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 — list-based argv only, no shell.
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from llove.browser.external import ExternalTool, available_tools

# ---------------------------------------------------------------------------
# 結果
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SvgbobRender:
    """``render_svgbob`` の戻り値.

    `MermaidRender` / `SVGRender` / `PlantUMLRender` / `DotRender` と
    同じ ``DiagramRenderResult`` shape (``kind`` / ``argv`` / ``ascii_text``)
    を満たす。MarkdownView の `ImageRenderPane` にそのまま流せる。
    """

    kind: Literal["image", "ascii"]
    argv: tuple[str, ...] = ()
    svg_path: Path | None = None
    ascii_text: str = ""
    image_tool: ExternalTool | None = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# 検出
# ---------------------------------------------------------------------------


def svgbob_available() -> bool:
    """``svgbob`` バイナリが PATH 上に存在するかを返す."""
    return shutil.which("svgbob") is not None


def find_image_tool() -> ExternalTool | None:
    """画像 scheme で利用可能な最優先ツールを返す (mermaid_render と共有方針)."""
    tools = available_tools("image")
    return tools[0] if tools else None


# ---------------------------------------------------------------------------
# svgbob 呼び出し
# ---------------------------------------------------------------------------

Runner = Callable[[list[str]], int]


def _default_runner(argv: list[str]) -> int:
    """``subprocess.run`` のデフォルト実装. 失敗時は非ゼロを返す."""
    try:
        proc = subprocess.run(  # nosec B603 — argv is fully controlled.
            argv,
            check=False,
            capture_output=True,
            timeout=30,
        )
        return proc.returncode
    except (OSError, subprocess.SubprocessError):
        raise


def render_svgbob_to_svg(
    source: str,
    output: Path,
    *,
    svgbob_path: str | None = None,
    runner: Runner | None = None,
) -> Path | None:
    """svgbob ASCII art source を svgbob で SVG に変換し、出力 Path を返す.

    svgbob CLI は ``input.bob -o output.svg`` のように出力ファイル名を
    直接指定できる。caller は output Path を自由に決められる。

    Parameters
    ----------
    source
        svgbob ASCII art 文字列 (罫線・矢印・箱を ASCII で書いたもの)。
    output
        SVG 出力先 Path。親ディレクトリは存在前提 (caller 側で確保)。
    svgbob_path
        ``svgbob`` 実行ファイルへの絶対パス。``None`` なら即座に失敗。
    runner
        テスト差し替え用の subprocess shim. ``None`` なら ``_default_runner``。

    Returns
    -------
    出力 SVG の Path、または失敗時 ``None``。
    """
    if not svgbob_path:
        return None
    run = runner or _default_runner

    src_path = output.with_suffix(".bob")
    try:
        src_path.write_text(source, encoding="utf-8")
    except OSError:
        return None

    argv = [svgbob_path, str(src_path), "-o", str(output)]
    try:
        rc = run(argv)
    except Exception:
        return None
    if rc != 0:
        return None
    if not output.exists():
        return None
    return output


# ---------------------------------------------------------------------------
# ASCII フォールバック
# ---------------------------------------------------------------------------


_FALLBACK_HEADER = (
    "◇ svgbob (ASCII fallback — install svgbob + chafa for image render)"
)
_FALLBACK_RULE = "─" * 60


def ascii_fallback(source: str) -> str:
    """画像レンダ不能時に表示する ASCII ブロック.

    svgbob ソースは元から ASCII art (人間可読) なので、罫線で囲んで
    そのまま出すのが情報量的に最大。SVG 抜粋とは違うアプローチ。
    """
    body = source.rstrip() if isinstance(source, str) else ""
    return f"{_FALLBACK_HEADER}\n{_FALLBACK_RULE}\n{body}\n{_FALLBACK_RULE}\n"


# ---------------------------------------------------------------------------
# 高レベル統合
# ---------------------------------------------------------------------------


def render_svgbob(
    source: str,
    *,
    output_dir: Path,
    svgbob_path: str | None = None,
    image_tool: ExternalTool | None = None,
    runner: Runner | None = None,
) -> SvgbobRender:
    """source を可能な限りターミナル画像化し、不可なら ASCII で返す.

    成功時:
        ``SvgbobRender(kind="image", argv=(...,), svg_path=Path(...))``

    失敗 / 未インストール時:
        ``SvgbobRender(kind="ascii", ascii_text="...")``
    """
    resolved_svgbob = (
        svgbob_path if svgbob_path else (shutil.which("svgbob") or None)
    )
    resolved_tool = image_tool if image_tool is not None else find_image_tool()

    if not resolved_svgbob or resolved_tool is None:
        return SvgbobRender(kind="ascii", ascii_text=ascii_fallback(source))

    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / "diagram.svg"
    rendered = render_svgbob_to_svg(
        source, svg_path, svgbob_path=resolved_svgbob, runner=runner
    )
    if rendered is None:
        return SvgbobRender(kind="ascii", ascii_text=ascii_fallback(source))

    argv = tuple(resolved_tool.build_argv(path=str(rendered)))
    return SvgbobRender(
        kind="image",
        argv=argv,
        svg_path=rendered,
        image_tool=resolved_tool,
    )


__all__ = [
    "SvgbobRender",
    "ascii_fallback",
    "available_tools",  # re-exported for monkeypatch convenience in tests
    "find_image_tool",
    "render_svgbob",
    "render_svgbob_to_svg",
    "shutil",  # re-exported for monkeypatch convenience in tests
    "svgbob_available",
]
